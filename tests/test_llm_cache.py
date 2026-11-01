"""Unit tests for LLM caching and mock responses."""

from trustlayer.llm import _get_cache, _set_cache, get_embedding

def test_cache_set_and_get():
    """Verify disk cache stores and retrieves values."""
    test_key = "test_key_12345"
    test_val = "cached_response_text"
    _set_cache(test_key, test_val, "test-model")
    retrieved = _get_cache(test_key)
    assert retrieved == test_val

def test_embedding_dimension():
    """Verify embedding function returns standard 1536 float list."""
    vec = get_embedding("Nova Bank savings account")
    assert isinstance(vec, list)
    assert len(vec) == 1536
    assert isinstance(vec[0], float)

