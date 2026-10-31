import hashlib
import json
from typing import Optional, List, Dict, Any
from database.db import get_db_connection

def compute_query_hash(query: str, top_k: int, doc_filter: Optional[str] = None) -> str:
    key_str = f"{query.strip().lower()}_{top_k}_{doc_filter or 'all'}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

def get_cached_retrieval(query: str, top_k: int, doc_filter: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    cache_key = compute_query_hash(query, top_k, doc_filter)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT result_json FROM retrieval_cache WHERE cache_key = ?", (cache_key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["result_json"])
        except Exception:
            return None
    return None

def set_cached_retrieval(query: str, top_k: int, results: List[Dict[str, Any]], doc_filter: Optional[str] = None):
    cache_key = compute_query_hash(query, top_k, doc_filter)
    conn = get_db_connection()
    cursor = conn.cursor()
    result_str = json.dumps(results, ensure_ascii=False)
    cursor.execute("""
    INSERT OR REPLACE INTO retrieval_cache (cache_key, result_json)
    VALUES (?, ?)
    """, (cache_key, result_str))
    conn.commit()
    conn.close()

def clear_retrieval_cache():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM retrieval_cache")
    conn.commit()
    conn.close()

