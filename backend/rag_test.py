
from rag import build_knowledge_index, retrieve_context

print("Building knowledge index...")

index = build_knowledge_index()

print("Documents indexed:", len(index))

question = input("\nAsk a question: ")

results = retrieve_context(question, index)

print("\nRelevant information:\n")

for result in results:
    print("Source:", result["source"])
    print("Similarity:", round(result["score"], 3))
    print(result["text"])
    print("-" * 40)
