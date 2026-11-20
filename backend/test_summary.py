from backend.conversation_memory import (
    init_conversation_memory_table,
    generate_conversation_summary,
    save_conversation_summary,
    get_conversation_summary
)
init_conversation_memory_table()
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"

messages = [
    {
        "role": "user",
        "content": "I am building a personal AI chatbot called MyAI."
    },
    {
        "role": "assistant",
        "content": "That's a great project. We can build it using Python and Ollama."
    },
    {
        "role": "user",
        "content": "I want it to remember conversations and uploaded documents."
    },
    {
        "role": "assistant",
        "content": "We can use SQLite for memory and RAG for document retrieval."
    }
]

conversation_id = "summary_test_001"

summary = generate_conversation_summary(
    messages,
    OLLAMA_URL,
    MODEL
)

save_conversation_summary(conversation_id, summary)

saved_summary = get_conversation_summary(conversation_id)

print("\nGenerated Summary:")
print(summary)

print("\nRetrieved Summary from SQLite:")
print(saved_summary)
