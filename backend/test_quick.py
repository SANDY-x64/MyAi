from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("[1] Testing /health...")
r = client.get("/health")
print("Status:", r.status_code, r.json())

print("[2] Testing /models...")
r = client.get("/models")
print("Installed models:", len(r.json().get("installed_models", [])))

print("[3] Testing /documents...")
r = client.get("/documents")
print("Documents:", r.json().get("total"), "Chunks:", r.json().get("total_chunks"))

print("[4] Testing /memories...")
r = client.get("/memories")
print("Memories count:", r.json().get("total"))

print("[5] Testing /personas...")
r = client.get("/personas")
print("Personas:", len(r.json().get("personas", [])))

print("[6] Testing /agent/tools...")
r = client.get("/agent/tools")
print("Tools:", len(r.json().get("tools", [])))

print("\nAll instant endpoints verified successfully!")
