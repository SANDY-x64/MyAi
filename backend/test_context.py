
from backend.context_manager import (
    estimate_tokens,
    trim_history_by_tokens
)

messages = [
    {"role": "user", "content": "Hello MyAI"},
    {"role": "assistant", "content": "Hello! How can I help you?"},
    {"role": "user", "content": "Explain Python programming."},
    {"role": "assistant", "content": "Python is a programming language."},
    {"role": "user", "content": "Explain artificial intelligence."},
    {"role": "assistant", "content": "AI enables machines to perform intelligent tasks."}
]

print("Original messages:", len(messages))

print(
    "Estimated tokens:",
    sum(estimate_tokens(m["content"]) for m in messages)
)

trimmed = trim_history_by_tokens(
    messages,
    max_tokens=15
)

print("\nMessages after trimming:")

for message in trimmed:
    print(message["role"], ":", message["content"])

print("\nRemaining messages:", len(trimmed))
