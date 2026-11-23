"""
Live Server Smoke Test
Starts FastAPI server on localhost:8000, probes endpoints, and terminates.
"""

import time
import requests
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Launch server subprocess
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=str(BASE_DIR),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

try:
    print("Waiting for server to start...")
    online = False
    for _ in range(20):
        time.sleep(1)
        try:
            res = requests.get("http://127.0.0.1:8000/health", timeout=2)
            if res.status_code == 200:
                online = True
                print("✓ Server online on http://127.0.0.1:8000")
                break
        except Exception:
            continue

    if not online:
        print("Server failed to come online in 20s.")
        sys.exit(1)

    # 1. Test /models
    res = requests.get("http://127.0.0.1:8000/models", timeout=5)
    assert res.status_code == 200, f"/models failed: {res.status_code}"
    print(f"✓ /models: {len(res.json().get('installed_models', []))} installed models")

    # 2. Test /personas
    res = requests.get("http://127.0.0.1:8000/personas", timeout=5)
    assert res.status_code == 200, f"/personas failed: {res.status_code}"
    print(f"✓ /personas: {len(res.json().get('personas', []))} personas")

    # 3. Test /documents
    res = requests.get("http://127.0.0.1:8000/documents", timeout=5)
    assert res.status_code == 200, f"/documents failed: {res.status_code}"
    print(f"✓ /documents: {res.json().get('total')} documents ({res.json().get('total_chunks')} chunks in ChromaDB)")

    # 4. Test /memories
    res = requests.get("http://127.0.0.1:8000/memories", timeout=5)
    assert res.status_code == 200, f"/memories failed: {res.status_code}"
    print(f"✓ /memories: {res.json().get('total')} memories")

    # 5. Test /conversations
    res = requests.get("http://127.0.0.1:8000/conversations", timeout=5)
    assert res.status_code == 200, f"/conversations failed: {res.status_code}"
    print(f"✓ /conversations: {len(res.json().get('conversations', []))} conversations")

    # 6. Test /chat
    res = requests.post(
        "http://127.0.0.1:8000/chat",
        json={"message": "What is 2 + 2?", "persona": "concise"},
        timeout=60
    )
    assert res.status_code == 200, f"/chat failed: {res.status_code} - {res.text}"
    chat_data = res.json()
    print(f"✓ /chat replied: {chat_data.get('reply')[:60]}... (Model: {chat_data.get('model_used')})")

    print("\nALL SERVER ENDPOINTS VERIFIED SUCCESSFULLY!")

finally:
    proc.terminate()
    proc.wait()
    print("Server cleanly shut down.")
