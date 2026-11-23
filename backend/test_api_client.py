"""
MyAI API TestClient Verification
Tests all HTTP and streaming endpoints in-process.
"""

from fastapi.testclient import TestClient
from backend.main import app
import time

client = TestClient(app)

print("\n--- Testing MyAI API Endpoints ---")

# 1. Health
r = client.get("/health")
assert r.status_code == 200, f"Health failed: {r.text}"
print("✓ GET /health: 200 OK")

# 2. Models
r = client.get("/models")
assert r.status_code == 200
data = r.json()
assert "installed_models" in data
print(f"✓ GET /models: 200 OK ({len(data['installed_models'])} models)")

# 3. Personas
r = client.get("/personas")
assert r.status_code == 200
data = r.json()
assert len(data.get("personas", [])) >= 5
print(f"✓ GET /personas: 200 OK ({len(data['personas'])} personas)")

# 4. Documents
r = client.get("/documents")
assert r.status_code == 200
data = r.json()
print(f"✓ GET /documents: 200 OK ({data['total']} documents, {data['total_chunks']} chunks in ChromaDB)")

# 5. Memories
r = client.get("/memories")
assert r.status_code == 200
data = r.json()
print(f"✓ GET /memories: 200 OK ({data['total']} memories)")

# 6. Conversations
r = client.get("/conversations")
assert r.status_code == 200
data = r.json()
print(f"✓ GET /conversations: 200 OK ({len(data['conversations'])} conversations)")

# 7. Agent Tools
r = client.get("/agent/tools")
assert r.status_code == 200
data = r.json()
print(f"✓ GET /agent/tools: 200 OK ({len(data['tools'])} tools registered)")

# 8. Auth Flow
uname = f"api_user_{int(time.time())}"
pwd = "SecurePassword123!"
reg_res = client.post("/auth/register", json={"username": uname, "password": pwd})
assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"

login_res = client.post("/auth/login", json={"username": uname, "password": pwd})
assert login_res.status_code == 200, f"Login failed: {login_res.text}"
token = login_res.json().get("token")

me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
assert me_res.status_code == 200 and me_res.json().get("authenticated") is True
print("✓ Auth flow (Register, Login, Session Validate): 200 OK")

# 9. Chat Endpoint (Testing model inference)
chat_res = client.post("/chat", json={
    "message": "Hello MyAI, confirm you are operational in one short sentence.",
    "persona": "concise"
})
assert chat_res.status_code == 200, f"Chat failed: {chat_res.text}"
reply = chat_res.json().get("reply", "")
print(f"✓ POST /chat: 200 OK -> \"{reply.strip()[:60]}...\"")

# 10. Streaming Chat Endpoint
stream_res = client.post("/chat/stream", json={
    "message": "Count from 1 to 3.",
    "persona": "concise"
})
assert stream_res.status_code == 200, f"Stream failed: {stream_res.text}"
streamed_content = stream_res.text
assert len(streamed_content) > 0
print(f"✓ POST /chat/stream: 200 OK -> Streamed {len(streamed_content)} characters")

print("\n🎉 ALL API ENDPOINTS VERIFIED AND PASSING SUCCESSFULLY!")
