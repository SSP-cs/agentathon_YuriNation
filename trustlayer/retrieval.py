"""Retrieval engine using ChromaDB with tiered expansion, query rewriting, and MMR."""

import math
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

from trustlayer.config import CHROMA_PATH, COLLECTION_NAME
from trustlayer.schemas import EvidenceChunk
from trustlayer.llm import get_embedding

_client: Optional[chromadb.PersistentClient] = None
_collection = None

def get_collection():
    """Retrieve or initialize persistent ChromaDB collection."""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False))
        _collection = _client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    return _collection

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm1 * norm2)))

def maximal_marginal_relevance(
    query_embedding: List[float],
    candidate_embeddings: List[List[float]],
    candidate_indices: List[int],
    k: int = 12,
    lambda_param: float = 0.65,
) -> List[int]:
    """Calculate Maximal Marginal Relevance (MMR) indices to maximize diversity."""
    if not candidate_indices:
        return []

    selected_indices: List[int] = []
    unselected = list(candidate_indices)

    # Initial best candidate
    best_sim = -1.0
    best_idx = unselected[0]
    for idx in unselected:
        sim = cosine_similarity(query_embedding, candidate_embeddings[idx])
        if sim > best_sim:
            best_sim = sim
            best_idx = idx

    selected_indices.append(best_idx)
    unselected.remove(best_idx)

    # Greedily pick up to k candidates
    while len(selected_indices) < min(k, len(candidate_indices)) and unselected:
        best_mmr = -1e9
        best_next_idx = unselected[0]

        for idx in unselected:
            sim_to_query = cosine_similarity(query_embedding, candidate_embeddings[idx])
            sim_to_selected = max(cosine_similarity(candidate_embeddings[idx], candidate_embeddings[s]) for s in selected_indices)
            mmr_score = lambda_param * sim_to_query - (1.0 - lambda_param) * sim_to_selected

            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_next_idx = idx

        selected_indices.append(best_next_idx)
        unselected.remove(best_next_idx)

    return selected_indices

def retrieve_evidence(
    query: str,
    attempt: int = 0,
    unsupported_claims: Optional[List[str]] = None,
    use_mmr: bool = False,
    k: Optional[int] = None,
) -> List[EvidenceChunk]:
    """
    Tiered retrieval function:
    - Attempt 0: k=4 standard top-k similarity
    - Attempt 1: k=8 with query rewritten/expanded from unsupported claims
    - Attempt 2: k=12 with MMR diversification
    """
    col = get_collection()
    count = col.count()
    if count == 0:
        return []

    # Configure k and effective query according to attempt and flags
    if attempt == 0:
        eff_k = k or 4
        effective_query = query
        eff_mmr = use_mmr
    elif attempt == 1:
        eff_k = k or 8
        expansion = " ".join(unsupported_claims or [])
        effective_query = f"{query} {expansion}".strip()
        eff_mmr = use_mmr
    else:  # attempt >= 2
        eff_k = k or 12
        effective_query = query
        eff_mmr = True

    eff_k = min(eff_k, count)
    query_vec = get_embedding(effective_query)

    if not eff_mmr:
        # Standard top-k search
        results = col.query(
            query_embeddings=[query_vec],
            n_results=eff_k,
            include=["documents", "metadatas", "distances"]
        )

        chunks: List[EvidenceChunk] = []
        if results and results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

            for cid, doc, meta, dist in zip(ids, docs, metas, dists):
                # Chroma cosine distance: dist = 1 - cos_sim, so cos_sim = 1 - dist
                score = max(0.0, min(1.0, 1.0 - float(dist)))
                chunks.append(EvidenceChunk(
                    id=meta.get("chunk_id", cid),
                    content=doc,
                    source=meta.get("source", "unknown"),
                    section=meta.get("section", "unknown"),
                    score=round(score, 4)
                ))
        return chunks

    else:
        # MMR retrieval: fetch candidate pool first
        pool_size = min(max(eff_k * 3, 20), count)
        results = col.query(
            query_embeddings=[query_vec],
            n_results=pool_size,
            include=["documents", "metadatas", "distances", "embeddings"]
        )

        if not results or not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0] if results.get("distances") else [0.0] * len(ids)
        cand_embeds = results["embeddings"][0]

        candidate_indices = list(range(len(ids)))
        selected_indices = maximal_marginal_relevance(
            query_embedding=query_vec,
            candidate_embeddings=cand_embeds,
            candidate_indices=candidate_indices,
            k=eff_k,
            lambda_param=0.65
        )

        chunks: List[EvidenceChunk] = []
        for idx in selected_indices:
            dist = dists[idx]
            score = max(0.0, min(1.0, 1.0 - float(dist)))
            chunks.append(EvidenceChunk(
                id=metas[idx].get("chunk_id", ids[idx]),
                content=docs[idx],
                source=metas[idx].get("source", "unknown"),
                section=metas[idx].get("section", "unknown"),
                score=round(score, 4)
            ))
        return chunks

def format_evidence_block(chunks: List[EvidenceChunk]) -> str:
    """Format chunks into a clean prompt context block with IDs."""
    if not chunks:
        return "NO RELEVANT EVIDENCE RETRIEVED."
    lines = []
    for c in chunks:
        lines.append(f"[{c.id}] (Source: {c.source} | Section: {c.section} | Sim: {c.score:.2f})\n{c.content}\n")
    return "\n".join(lines)

