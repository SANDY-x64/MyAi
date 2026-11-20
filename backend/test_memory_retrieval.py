from backend.memory import retrieve_relevant_memories

question = "Help me learn Python programming"

print("Question:", question)

results = retrieve_relevant_memories(
    question,
    top_k=5,
    threshold=0.40
)

print("\nRelevant memories:")

if results:
    for memory in results:
        print(
            f"\nCategory: {memory['category']}"
            f"\nMemory: {memory['content']}"
            f"\nSimilarity: {memory['score']:.3f}"
        )
else:
    print("No relevant memories found.")