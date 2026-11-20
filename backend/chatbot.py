
import requests
import json
import os

URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"

# Persistent memory file
HISTORY_FILE = "backend/chat_history.json"

# System instructions
system_message = {
    "role": "system",
    "content": (
        "You are MyAI, a helpful personal AI assistant. "
        "Answer clearly and remember the conversation context."
    )
}

# Load previous conversations
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            messages = json.load(file)

        if not isinstance(messages, list):
            raise ValueError("Invalid chat history")

        messages = [system_message] + [
            m for m in messages
            if isinstance(m, dict)
            and m.get("role") in ("user", "assistant")
            and isinstance(m.get("content"), str)
        ]

        print("Previous conversation loaded!")

    except (json.JSONDecodeError, ValueError):
        messages = [system_message]
        print("History file invalid. Starting fresh.")

else:
    messages = [system_message]
    print("Starting a new conversation!")

print("\n========== WELCOME TO MYAI ==========")
print("Commands: /exit | /clear")

while True:

    user_input = input("\nYou: ").strip()

    if user_input.lower() == "/exit":
        print("MyAI: Conversation saved. Goodbye!")
        break

    if user_input.lower() == "/clear":
        messages = [system_message]

        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            json.dump([], file, indent=4)

        print("MyAI: Conversation history cleared!")
        continue

    if not user_input:
        continue

    messages.append({
        "role": "user",
        "content": user_input
    })

    try:
        response = requests.post(
            URL,
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False
            },
            timeout=180
        )

        response.raise_for_status()

        result = response.json()
        ai_reply = result["message"]["content"]

        messages.append({
            "role": "assistant",
            "content": ai_reply
        })

        # Save conversation permanently
        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            json.dump(
                messages[1:],
                file,
                indent=4,
                ensure_ascii=False
            )

        print("\nMyAI:", ai_reply)

    except (requests.exceptions.RequestException,
            KeyError,
            ValueError) as error:

        print("Error:", error)

        messages.pop()
