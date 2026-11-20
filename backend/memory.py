
import requests
import json
import sqlite3
from pathlib import Path
from backend.rag import get_embedding, cosine_similarity



# --------------------------------
# DATABASE CONFIGURATION
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

DB_PATH = DATA_DIR / "myai.db"

DATA_DIR.mkdir(exist_ok=True)


# --------------------------------
# CREATE MEMORY TABLE
# --------------------------------


def init_memory_table():

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                embedding TEXT
            )
        """)

        # Check whether the embedding column already exists
        cursor.execute("PRAGMA table_info(memories)")
        columns = [column[1] for column in cursor.fetchall()]

        # Add it without deleting existing memories
        if "embedding" not in columns:
            cursor.execute("""
                ALTER TABLE memories
                ADD COLUMN embedding TEXT
            """)


# --------------------------------
# SAVE MEMORY
# --------------------------------


def save_memory(content, category="general"):

    content = content.strip()
    category = category.lower().strip()

    allowed_categories = [
        "learning",
        "goals",
        "preferences",
        "projects",
        "general"
    ]

    if not content:
        return False

    if category not in allowed_categories:
        category = "general"

    # Generate embedding only once when saving
    try:
        embedding = get_embedding(content)
        embedding_json = json.dumps(embedding)
    except Exception as error:
        print("Memory embedding error:", error)
        return False

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id FROM memories
            WHERE LOWER(content) = LOWER(?)
            """,
            (content,)
        )

        if cursor.fetchone():
            return False

        cursor.execute(
            """
            INSERT INTO memories (content, category, embedding)
            VALUES (?, ?, ?)
            """,
            (content, category, embedding_json)
        )

    return True




# --------------------------------
# GET ALL MEMORIES
# --------------------------------

def get_all_memories():

    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, content, category, created_at
        FROM memories
        ORDER BY id DESC
    """)

    memories = cursor.fetchall()

    connection.close()

    return memories

# --------------------------------
# SEMANTIC MEMORY RETRIEVAL
# --------------------------------

def retrieve_relevant_memories(
    question,
    top_k=5,
    threshold=0.40
):

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, content, category, embedding
            FROM memories
            WHERE embedding IS NOT NULL
        """)

        memories = cursor.fetchall()

    if not memories:
        return []

    # Generate embedding only for the new question
    question_embedding = get_embedding(question)

    results = []

    for memory in memories:

        memory_id = memory[0]
        content = memory[1]
        category = memory[2]

        try:
            memory_embedding = json.loads(memory[3])
        except (json.JSONDecodeError, TypeError):
            continue

        score = cosine_similarity(
            question_embedding,
            memory_embedding
        )

        if score >= threshold:

            results.append({
                "id": memory_id,
                "content": content,
                "category": category,
                "score": score
            })

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results[:top_k]

#-------------------------------
# BACKFILL MEMORY EMBEDDINGS    
#-------------------------------

def backfill_memory_embeddings():

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, content
            FROM memories
            WHERE embedding IS NULL
        """)

        memories = cursor.fetchall()

        updated_count = 0

        for memory_id, content in memories:

            try:
                embedding = get_embedding(content)

                embedding_json = json.dumps(embedding)

                cursor.execute("""
                    UPDATE memories
                    SET embedding = ?
                    WHERE id = ?
                """, (embedding_json, memory_id))

                updated_count += 1

            except Exception as error:
                print(
                    f"Embedding failed for memory {memory_id}:",
                    error
                )

    print(f"Updated {updated_count} existing memories.")

    return updated_count


# --------------------------------
# DELETE MEMORY
# --------------------------------

def delete_memory(memory_id):

    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM memories
        WHERE id = ?
    """, (memory_id,))

    connection.commit()

    deleted = cursor.rowcount

    connection.close()

    return deleted

# --------------------------------
# EXTRACT MEMORIES USING OLLAMA
# --------------------------------


# --------------------------------
# EXTRACT MEMORIES USING OLLAMA
# --------------------------------

def extract_and_save_memories(user_message):

   
    prompt = f"""
Analyze the user's message and extract useful
long-term memories.

Allowed categories:
- learning
- goals
- preferences
- projects
- general

Rules:
1. Save only useful information for future conversations.
2. Avoid temporary questions and one-time requests.
3. Do not save passwords or private credentials.
4. Do not save sensitive personal information.
5. Do not invent facts.
6. Maximum 5 memories.
7. Keep each memory short and clear.

Return ONLY valid JSON in this format:

{{
    "memories": [
        {{
            "content": "User is learning Python",
            "category": "learning"
        }}
    ]
}}

If nothing is useful, return:

{{"memories": []}}

User message:
{user_message}
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3", "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        response_text = response.json().get("response", "")

        data = json.loads(response_text)

        memories = data.get("memories", [])

        saved_count = 0

        for memory in memories[:5]:

            content = memory.get("content", "").strip()
            category = memory.get("category", "general")

            if content:

                saved = save_memory(content, category)

                if saved:
                    saved_count += 1

        return saved_count

    except (requests.RequestException, json.JSONDecodeError, AttributeError, TypeError):
        return 0
