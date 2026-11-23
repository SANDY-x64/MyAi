
import sqlite3
import requests
from pathlib import Path


DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "myai.db"
)


def init_conversation_memory_table():

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                conversation_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                last_summarized_message_id INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Upgrade an existing table if the column is missing
        columns = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(conversation_summaries)"
            ).fetchall()
        ]

        if "last_summarized_message_id" not in columns:

            conn.execute("""
                ALTER TABLE conversation_summaries
                ADD COLUMN last_summarized_message_id
                INTEGER DEFAULT 0
            """)


def get_conversation_summary_state(conversation_id):

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute("""
            SELECT summary, last_summarized_message_id
            FROM conversation_summaries
            WHERE conversation_id = ?
        """, (conversation_id,))

        result = cursor.fetchone()

    if result:
        return result[0], result[1] or 0

    return "", 0


def get_conversation_summary(conversation_id):

    summary, _ = get_conversation_summary_state(
        conversation_id
    )

    return summary


def save_conversation_summary(
    conversation_id,
    summary,
    last_message_id=0
):

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute("""
            INSERT INTO conversation_summaries (
                conversation_id,
                summary,
                last_summarized_message_id
            )
            VALUES (?, ?, ?)

            ON CONFLICT(conversation_id)
            DO UPDATE SET
                summary = excluded.summary,
                last_summarized_message_id =
                    excluded.last_summarized_message_id,
                updated_at = CURRENT_TIMESTAMP
        """, (
            conversation_id,
            summary,
            last_message_id
        ))


def generate_conversation_summary(
    messages,
    ollama_url=None,
    model=None
):
    from backend.model_manager import resolve_model, OLLAMA_BASE_URL
    if not ollama_url:
        ollama_url = f"{OLLAMA_BASE_URL}/api/chat"
    if not model:
        model = resolve_model(None)

    conversation_text = ""

    for message in messages:

        role = message["role"]
        content = message["content"]

        conversation_text += f"{role}: {content}\n"

    prompt = f"""
    Summarize this conversation.

    Preserve:
    1. Important facts and decisions.
    2. Relevant user goals and preferences.
    3. Important project progress.
    4. Unfinished tasks and next steps.

    Keep the summary clear and concise.
    Do not invent information.

    Conversation:
    {conversation_text}
    """

    response = requests.post(
        ollama_url,
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()["message"]["content"].strip()
