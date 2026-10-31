import os
import chromadb
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.schemas import RetrievedChunk
from retrieval.cache import get_cached_retrieval, set_cached_retrieval, clear_retrieval_cache

class PolicyRetriever:
    def __init__(self):
        os.makedirs(settings.CHROMA_PATH, exist_ok=True)
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        self.collection = self.client.get_or_create_collection(
            name="trustlayer_policies",
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        if not chunks:
            return
        
        ids = [c["chunk_id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [
            {
                "document_name": c["document_name"],
                "page_number": c["page_number"],
                "chunk_id": c["chunk_id"]
            }
            for c in chunks
        ]
        
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        clear_retrieval_cache()

    def delete_document(self, document_name: str):
        self.collection.delete(where={"document_name": document_name})
        clear_retrieval_cache()

    def count_chunks(self) -> int:
        return self.collection.count()

    def retrieve(self, query: str, top_k: int = 3, use_cache: bool = True) -> List[RetrievedChunk]:
        if not query.strip():
            return []
        
        total_in_db = self.collection.count()
        if total_in_db == 0:
            return []

        # Check cache
        if use_cache:
            cached = get_cached_retrieval(query, top_k)
            if cached is not None:
                return [RetrievedChunk(**item) for item in cached]

        actual_k = min(top_k, total_in_db)
        results = self.collection.query(
            query_texts=[query],
            n_results=actual_k
        )

        retrieved_chunks: List[RetrievedChunk] = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            ids = results["ids"][0]
            distances = results.get("distances", [[0.0] * len(docs)])[0]

            for doc_text, meta, cid, dist in zip(docs, metas, ids, distances):
                # Cosine distance to similarity: 1.0 - dist
                sim_score = max(0.0, round(1.0 - float(dist), 4))
                chunk = RetrievedChunk(
                    chunk_id=cid,
                    document_name=meta.get("document_name", "Unknown"),
                    page_number=int(meta.get("page_number", 1)),
                    text=doc_text,
                    score=sim_score,
                    metadata=meta
                )
                retrieved_chunks.append(chunk)

        # Cache results
        if use_cache and retrieved_chunks:
            set_cached_retrieval(query, top_k, [c.model_dump() for c in retrieved_chunks])

        return retrieved_chunks

retriever = PolicyRetriever()

