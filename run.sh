#!/usr/bin/env bash
# TrustLayer execution script
set -e

echo "=== TrustLayer Setup & Run Script ==="

# 1. Install dependencies
echo "[1/4] Installing dependencies..."
pip install -r requirements.txt

# 2. Ingest corpus and build ChromaDB vector store
echo "[2/4] Indexing Nova Bank & Nova Shield Insurance policy corpus..."
python scripts/ingest.py

# 3. Run test suite
echo "[3/4] Running pytest suite..."
python -m pytest -v

# 4. Launch Streamlit UI
echo "[4/4] Starting Streamlit UI..."
streamlit run app.py

