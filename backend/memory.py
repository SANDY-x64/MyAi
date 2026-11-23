"""
MyAI Hybrid Memory Engine
Combines SQLite relational storage with ChromaDB vector search.
Provides automatic memory extraction, deduplication, categorization, and semantic retrieval.
"""

import sqlite3
import json
import requests
from pathlib import Path
from backend.rag import get_embedding, cosine_similarity
from backend.vector_store import vector_store
from backend.model_manager import resolve_model, OLLAMA_BASE_URL

# --------------------------------
# DATABASE CONFIGURATION
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "myai.db"
DATA_DIR.mkdir(exist_ok=True)

ALLOWED_CATEGORIES = [
    "learning",
    "goals",
    "preferences",
    "projects",
    "career",
    "personal",
    "general"
]


# --------------------------------
# CREATE MEMORY TABLE
# --------------------------------

def init_memory_table():
    """Ensure memories table exists and sync with vector store."""
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

        # Add embedding column if absent
        cursor.execute("PRAGMA table_info(memories)")
        columns = [column[1] for column in cursor.fetchall()]
        if "embedding" not in columns:
            cursor.execute("ALTER TABLE memories ADD COLUMN embedding TEXT")

    # Sync ChromaDB with existing SQLite memories
    sync_chroma_memories()


def sync_chroma_memories():
    """Ensure all existing SQLite memories are indexed in ChromaDB without redundant re-indexing."""
    try:
        memories = get_all_memories()
        chroma_count = vector_store.memory_col.count()
        if chroma_count >= len(memories):
            return  # Already synchronized

        for mem in memories:
            mid, content, category, _ = mem
            vector_store.upsert_memory(mid, content, category)
    except Exception as exc:
        print(f"[Memory] Chroma sync error: {exc}")


# --------------------------------
# SAVE MEMORY
# --------------------------------

def save_memory(content: str, category: str = "general") -> bool:
    """Save memory into SQLite and ChromaDB vector store."""
    content = content.strip()
    category = category.lower().strip()

    if not content:
        return False

    if category not in ALLOWED_CATEGORIES:
        category = "general"

    # Compute embedding for SQLite backward compatibility
    embedding_json = None
    try:
        embedding = get_embedding(content)
        embedding_json = json.dumps(embedding)
    except Exception as error:
        print("[Memory] Embedding generation error:", error)

    inserted_id = None
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM memories WHERE LOWER(content) = LOWER(?)",
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
        inserted_id = cursor.lastrowid

    # Index in ChromaDB
    if inserted_id:
        vector_store.upsert_memory(inserted_id, content, category)
        return True

    return False


# --------------------------------
# GET ALL MEMORIES
# --------------------------------

def get_all_memories():
    """Fetch all memories ordered by newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, content, category, created_at
            FROM memories
            ORDER BY id DESC
        """)
        return cursor.fetchall()


# --------------------------------
# SEMANTIC MEMORY RETRIEVAL (HYBRID)
# --------------------------------

def retrieve_relevant_memories(question: str, top_k: int = 5, threshold: float = 0.40):
    """
    Retrieve memories matching user question.
    Primary: ChromaDB semantic search.
    Fallback: SQLite cosine similarity search.
    """
    # 1. Attempt ChromaDB vector retrieval
    try:
        chroma_hits = vector_store.search_memories(question, top_k=top_k, threshold=threshold)
        if chroma_hits:
            return chroma_hits
    except Exception as exc:
        print(f"[Memory] ChromaDB retrieval failed, falling back to SQLite: {exc}")

    # 2. Resilient SQLite fallback
    try:
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

        question_embedding = get_embedding(question)
        results = []

        for memory in memories:
            memory_id, content, category, emb_str = memory
            try:
                memory_embedding = json.loads(emb_str)
            except (json.JSONDecodeError, TypeError):
                continue

            score = cosine_similarity(question_embedding, memory_embedding)
            if score >= threshold:
                results.append({
                    "id": memory_id,
                    "content": content,
                    "category": category,
                    "score": round(score, 3)
                })

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]
    except Exception as exc:
        print(f"[Memory] SQLite fallback retrieval error: {exc}")
        return []


# --------------------------------
# DELETE MEMORY
# --------------------------------

def delete_memory(memory_id: int):
    """Delete memory from both SQLite and ChromaDB."""
    deleted = 0
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        deleted = cursor.rowcount

    # Delete from ChromaDB
    vector_store.delete_memory(memory_id)
    return deleted


# --------------------------------
# AUTOMATIC MEMORY EXTRACTION
# --------------------------------

def extract_and_save_memories(user_message: str) -> int:
    """
    Analyzes the user's message using the local model to extract durable user facts.
    Uses dynamic model resolution rather than hardcoding legacy models.
    """
    cleaned_msg = user_message.strip()
    # Filter trivial questions or small talk
    if len(cleaned_msg.split()) < 3 or cleaned_msg.lower() in ["hi", "hello", "hey", "who are you"]:
        return 0

    model_name = resolve_model(None)

    prompt = f"""
Analyze the user's message and extract permanent, useful facts about the user.

Categories:
- learning: skills, technologies, topics the user is studying or wants to learn
- goals: short-term or long-term career, project, or personal objectives
- preferences: communication style, coding styles, favorite tools, likes/dislikes
- projects: projects the user is currently working on or planning
- career: profession, job role, background, industry
- personal: general background facts the user explicitly shared

Rules:
1. Save only permanent facts about the user for future conversations.
2. Do NOT save temporary questions, current commands, or one-time code requests.
3. Do NOT save sensitive passwords, tokens, API keys, or private identity numbers.
4. Maximum 3 memories per turn. Keep each memory one clear, concise sentence.
5. Return ONLY valid JSON in this schema:
{{
    "memories": [
        {{
            "content": "User prefers concise Python code with type annotations",
            "category": "preferences"
        }}
    ]
}}
If nothing worth saving permanently is present, return: {{"memories": []}}

User message:
{cleaned_msg}
"""

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2}
            },
            timeout=45
        )
        response.raise_for_status()
        response_text = response.json().get("response", "").strip()

        # Extract JSON from potential code block
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        data = json.loads(response_text)
        memories = data.get("memories", [])
        saved_count = 0

        for mem in memories[:3]:
            content = mem.get("content", "").strip()
            category = mem.get("category", "general")
            if content and len(content) > 5:
                if save_memory(content, category):
                    saved_count += 1

        return saved_count
    except Exception as exc:
        print(f"[Memory] Memory extraction exception: {exc}")
        return 0
