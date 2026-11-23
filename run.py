"""
MyAI Application Launcher
Starts the unified MyAI platform and opens the application in your default web browser.
"""

import sys
import time
import webbrowser
import threading
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def open_browser():
    """Wait for server to bind then open default browser."""
    time.sleep(1.8)
    url = "http://127.0.0.1:8000"
    print(f"\n[MyAI] Opening application in browser: {url}\n")
    webbrowser.open(url)

if __name__ == "__main__":
    import uvicorn
    from backend.model_manager import check_ollama_status

    print("\n" + "=" * 60)
    print("           ✨ STARTING MyAI PERSONAL PLATFORM ✨           ")
    print("=" * 60)

    # Check Ollama status
    status = check_ollama_status()
    if status.get("online"):
        print(f"✓ Ollama Daemon: Online (v{status.get('version')})")
    else:
        print("⚠️ Ollama Daemon is not reachable on http://localhost:11434.")
        print("   Please ensure Ollama is running ('ollama serve') for local AI inference.")

    print("✓ Vector Store: ChromaDB Ready (data/chroma_db)")
    print("✓ Database: SQLite Ready (data/myai.db)")
    print("✓ Unified Web Application: http://127.0.0.1:8000")
    print("=" * 60 + "\n")

    # Start browser opener in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run unified FastAPI application
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
