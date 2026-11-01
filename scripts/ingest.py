"""Corpus ingestion script: parses markdown policies, chunks them, and stores in ChromaDB."""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import chromadb
from chromadb.config import Settings

from trustlayer.config import (
    CHROMA_PATH,
    COLLECTION_NAME,
    POLICIES_DIR,
    EMBED_MODEL,
    MOCK_LLM,
)
from trustlayer.llm import get_embedding

def parse_markdown_sections(file_path: Path) -> List[Dict[str, Any]]:
    """Split a markdown file into logical sections based on headings."""
    text = file_path.read_text(encoding="utf-8")
    filename = file_path.name
    
    # Extract main title (# Title)
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filename

    # Split by section headers (## or ###)
    sections = []
    lines = text.split("\n")
    current_heading = "Overview"
    current_lines: List[str] = []

    for line in lines:
        if line.startswith("# "):
            continue
        elif line.startswith("## ") or line.startswith("### "):
            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                if sec_text:
                    sections.append({
                        "source": filename,
                        "title": title,
                        "section": current_heading,
                        "text": sec_text
                    })
                current_lines = []
            current_heading = line.lstrip("#").strip()
        else:
            current_lines.append(line)

    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        if sec_text:
            sections.append({
                "source": filename,
                "title": title,
                "section": current_heading,
                "text": sec_text
            })

    return sections

def parse_plain_sections(fp: Path) -> List[Dict[str, Any]]:
    """Load .txt or .pdf (one section per page) so real bank/insurer documents can be added."""
    if fp.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        pages = [(f"Page {i + 1}", pg.extract_text() or "") for i, pg in enumerate(PdfReader(str(fp)).pages)]
    else:
        pages = [("Overview", fp.read_text(encoding="utf-8"))]
    out = []
    for head, t in pages:
        w = t.split()
        if w:
            body = "\n\n".join(" ".join(w[i:i + 150]) for i in range(0, len(w), 150))
            out.append({"source": fp.name, "title": fp.stem.replace("_", " ").title(), "section": head, "text": body})
    return out

def chunk_section(section: Dict[str, Any], max_words: int = 250, overlap_words: int = 40) -> List[Dict[str, Any]]:
    """Chunk a section text into ~300-400 token (approx 200-250 words) overlapping passages."""
    text = section["text"]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    chunks = []
    current_chunk: List[str] = []
    current_word_count = 0

    for para in paragraphs:
        p_words = para.split()
        if current_word_count + len(p_words) > max_words and current_chunk:
            chunk_str = "\n\n".join(current_chunk)
            chunks.append({
                "source": section["source"],
                "title": section["title"],
                "section": section["section"],
                "text": chunk_str
            })
            # Overlap: keep the last paragraph or part of words
            overlap = " ".join(chunk_str.split()[-overlap_words:])
            current_chunk = [overlap, para]
            current_word_count = len(overlap.split()) + len(p_words)
        else:
            current_chunk.append(para)
            current_word_count += len(p_words)

    if current_chunk:
        chunk_str = "\n\n".join(current_chunk).strip()
        if chunk_str:
            chunks.append({
                "source": section["source"],
                "title": section["title"],
                "section": section["section"],
                "text": chunk_str
            })

    return chunks

def build_vector_store():
    """Ingest all policy files into ChromaDB."""
    policies_path = Path(POLICIES_DIR)
    if not policies_path.exists():
        raise FileNotFoundError(f"Policies directory not found at {policies_path}")

    files = sorted(f for f in policies_path.iterdir() if f.suffix.lower() in {".md", ".txt", ".pdf"})
    if not files:
        raise ValueError(f"No .md policy files found in {policies_path}")

    print(f"[*] Found {len(files)} policy documents in {policies_path}")

    all_chunks: List[Dict[str, Any]] = []
    for f in files:
        sections = parse_markdown_sections(f) if f.suffix.lower() == ".md" else parse_plain_sections(f)
        for sec in sections:
            sec_chunks = chunk_section(sec)
            all_chunks.extend(sec_chunks)

    print(f"[*] Generated {len(all_chunks)} semantic chunks. Creating IDs S1..S{len(all_chunks)}...")

    # Assign IDs like S1, S2, ...
    for idx, c in enumerate(all_chunks, start=1):
        c["chunk_id"] = f"S{idx}"

    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False))
    
    # Delete existing collection if any to allow clean re-ingest
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    ids = []
    documents = []
    metadatas = []
    embeddings = []

    print("[*] Computing embeddings and storing in ChromaDB...")
    for c in all_chunks:
        # Full content includes context title and section heading
        header = f"[{c['title']} > {c['section']}]"
        full_text = f"{header}\n{c['text']}"

        vec = get_embedding(full_text)

        ids.append(c["chunk_id"])
        documents.append(full_text)
        metadatas.append({
            "chunk_id": c["chunk_id"],
            "source": c["source"],
            "title": c["title"],
            "section": c["section"],
        })
        embeddings.append(vec)

    # Add to ChromaDB in batches of 50
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
            embeddings=embeddings[i:end]
        )

    print(f"[+] Successfully indexed {len(ids)} chunks into ChromaDB collection '{COLLECTION_NAME}' at {CHROMA_PATH}")

if __name__ == "__main__":
    build_vector_store()
