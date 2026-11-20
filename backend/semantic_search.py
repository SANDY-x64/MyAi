
import requests
import math
from pathlib import Path

# Ollama embedding API
URL = "http://localhost:11434/api/embed"
MODEL = "nomic-embed-text"

# Locate knowledge folder from project root
KNOWLEDGE_DIR = Path("knowledge")

# Read documents
documents = []

for file_path in KNOWLEDGE_DIR.glob("*.txt"):
    content = file_path.read_text(encoding="utf-8")

    documents.append({
        "filename": file_path.name,
        "content": content
    })

if not documents:
    raise RuntimeError("No text documents found in knowledge/")

# Generate embeddings for all documents
texts = [doc["content"] for doc in documents]

response = requests.post(
    URL,
    json={
        "model": MODEL,
        "input": texts
    },
    timeout=180
)

response.raise_for_status()

vectors = response.json()["embeddings"]

# Calculate cosine similarity
def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))

    norm_a = math.sqrt(sum(x*x for x in a))
    norm_b = math.sqrt(sum(x*x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0

    return dot / (norm_a * norm_b)


print("MYAI SEMANTIC SEARCH")
print("--------------------")

while True:

    query = input("\nAsk a question (exit to stop): ")

    if query.lower() == "exit":
        break

    # Convert question into embedding
    result = requests.post(
        URL,
        json={
            "model": MODEL,
            "input": [query]
        },
        timeout=120
    )

    result.raise_for_status()

    query_vector = result.json()["embeddings"][0]

    # Compare query with documents
    scores = []

    for doc, vector in zip(documents, vectors):
        score = cosine_similarity(query_vector, vector)

        scores.append({
            "filename": doc["filename"],
            "content": doc["content"],
            "score": score
        })

    # Sort by similarity
    scores.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    print("\nMOST RELEVANT DOCUMENTS:")

    for item in scores[:2]:
        print("\nFile:", item["filename"])
        print("Similarity:", round(item["score"], 4))
        print("Content:", item["content"])
