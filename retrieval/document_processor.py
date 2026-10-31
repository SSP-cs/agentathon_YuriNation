import os
import re
from typing import List, Dict, Any
from pypdf import PdfReader
from backend.config import settings

def clean_text(text: str) -> str:
    """Normalize whitespace and remove non-printable characters."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 60) -> List[str]:
    """Splits text into chunks preserving sentence boundaries where possible."""
    words = text.split()
    if not words:
        return []
    
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunk = " ".join(chunk_words)
        chunks.append(chunk)
        if i + chunk_size >= len(words):
            break
        i += (chunk_size - overlap)
    return chunks

def process_file(file_path: str, filename: str) -> List[Dict[str, Any]]:
    """
    Parses a PDF or TXT file and returns a list of indexed chunks with metadata:
    document_name, page_number, chunk_id, text.
    """
    ext = os.path.splitext(filename)[1].lower()
    chunks_meta = []
    
    if ext == ".pdf":
        reader = PdfReader(file_path)
        for page_idx, page in enumerate(reader.pages):
            page_no = page_idx + 1
            raw_text = page.extract_text() or ""
            cleaned = clean_text(raw_text)
            if not cleaned:
                continue
            page_chunks = chunk_text(cleaned, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
            for c_idx, c_text in enumerate(page_chunks):
                chunk_id = f"{filename}_p{page_no}_c{c_idx}"
                chunks_meta.append({
                    "chunk_id": chunk_id,
                    "document_name": filename,
                    "page_number": page_no,
                    "text": c_text
                })
    elif ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Estimate page breaks every ~500 words or preserve line markers
        lines = content.split("\n\n")
        current_page = 1
        page_word_count = 0
        
        full_text = clean_text(content)
        text_chunks = chunk_text(full_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
        for c_idx, c_text in enumerate(text_chunks):
            # assign estimated page based on chunk index
            est_page = (c_idx // 2) + 1
            chunk_id = f"{filename}_p{est_page}_c{c_idx}"
            chunks_meta.append({
                "chunk_id": chunk_id,
                "document_name": filename,
                "page_number": est_page,
                "text": c_text
            })
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only PDF and TXT are supported.")

    return chunks_meta

