import os
import sys
import subprocess
import argparse
import time

def run_backend():
    print("[TrustLayer] Starting FastAPI Backend on http://127.0.0.1:8000 ...")
    cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
    return subprocess.Popen(cmd)

def run_frontend():
    print("[TrustLayer] Starting Streamlit Frontend on http://127.0.0.1:8501 ...")
    cmd = [sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.port", "8501", "--server.address", "127.0.0.1"]
    return subprocess.Popen(cmd)

def main():
    parser = argparse.ArgumentParser(description="TrustLayer — AI Policy Verification System Runner")
    parser.add_argument("--backend", action="store_true", help="Launch FastAPI backend only")
    parser.add_argument("--frontend", action="store_true", help="Launch Streamlit frontend only")
    parser.add_argument("--all", action="store_true", default=True, help="Launch both backend and frontend")
    args = parser.parse_args()

    procs = []

    if args.backend or args.all:
        p_be = run_backend()
        procs.append(p_be)
        time.sleep(1.5)

    if args.frontend or args.all:
        p_fe = run_frontend()
        procs.append(p_fe)

    print("\n" + "="*60)
    print("🛡️ TRUSTLAYER IS RUNNING")
    print(" - Streamlit Web Dashboard: http://127.0.0.1:8501")
    print(" - FastAPI REST API Docs:   http://127.0.0.1:8000/docs")
    print("="*60 + "\n")

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n[TrustLayer] Shutting down services...")
        for p in procs:
            p.terminate()

if __name__ == "__main__":
    main()

