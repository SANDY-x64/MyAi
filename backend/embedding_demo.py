
import requests
import math

URL = "http://localhost:11434/api/embed"

sentences = [
    "Python is a programming language.",
    "Java is used for software development.",
    "The weather is sunny today."
]

response = requests.post(
    URL,
    json={
        "model": "nomic-embed-text",
        "input": sentences
    },
    timeout=120
)

response.raise_for_status()

embeddings = response.json()["embeddings"]

for sentence, vector in zip(sentences, embeddings):
    print("\nSentence:", sentence)
    print("Vector dimensions:", len(vector))
    print("First 5 numbers:", vector[:5])


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))

    norm_a = math.sqrt(sum(x*x for x in a))
    norm_b = math.sqrt(sum(x*x for x in b))

    return dot / (norm_a * norm_b)


print("\nSimilarity results:")

print(
    "Python vs Java:",
    cosine_similarity(embeddings[0], embeddings[1])
)

print(
    "Python vs Weather:",
    cosine_similarity(embeddings[0], embeddings[2])
)
