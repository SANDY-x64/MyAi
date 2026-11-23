"""
MyAI Advanced Personal AI Assistant - Main Application Server
Full-Stack FastAPI Backend integrating:
- Dynamic Multi-Model Local Ollama Engine
- Hybrid Persistent Memory (ChromaDB + SQLite)
- Semantic RAG Document Intelligence (.pdf, .docx, .txt, .md, code)
- Multimodal Vision & Image Understanding
- Autonomous Tool-Calling Agent with Human Approval
- Live Web Search & Citations
- Multi-Persona Reasoning & Context Management
"""

import uuid
import json
import sqlite3
import time
import os
import signal
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

from backend.personality import get_personality, list_personas, SYSTEM_PERSONALITY
from backend.context_manager import trim_history_by_tokens
from backend.reasoning import (
    analyze_question,
    get_response_format,
    get_quality_instructions,
    detect_multiple_tasks,
    evaluate_response_quality
)
from backend.conversation_memory import (
    init_conversation_memory_table,
    get_conversation_summary_state,
    save_conversation_summary,
    generate_conversation_summary
)
from backend.memory import (
    init_memory_table,
    save_memory,
    get_all_memories,
    delete_memory,
    extract_and_save_memories,
    retrieve_relevant_memories
)
from backend.rag import (
    KNOWLEDGE_DIR,
    SUPPORTED_EXTENSIONS,
    build_knowledge_index,
    index_single_document,
    retrieve_context
)
from backend.vector_store import vector_store
from backend.model_manager import (
    OLLAMA_BASE_URL,
    DEFAULT_CHAT_MODEL,
    get_installed_models,
    get_available_chat_models,
    resolve_model,
    check_ollama_status,
    RECOMMENDED_MODELS
)
from backend.multimodal import (
    is_image_file,
    encode_image_to_base64,
    get_available_vision_models,
    analyze_image_with_ollama
)
from backend.web_search import search_web, format_search_results
from backend.agent import (
    propose_action,
    execute_action,
    get_pending_actions,
    plan_and_execute_agent_task,
    TOOLS
)
from backend.auth import (
    register_user,
    authenticate_user,
    validate_session,
    invalidate_session
)

# ----------------------------------------------------
# DIRECTORY & DATABASE CONFIGURATION
# ----------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "myai.db"
FRONTEND_DIR = BASE_DIR / "frontend"

DATA_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


def get_connection():
    """Return SQLite connection with dictionary-like row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    """Ensure database schema is up-to-date with non-destructive migrations."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model TEXT DEFAULT 'llama3.2:1b',
                image_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check and add columns safely if missing
        cursor.execute("PRAGMA table_info(messages)")
        cols = [c[1] for c in cursor.fetchall()]
        if "model" not in cols:
            cursor.execute("ALTER TABLE messages ADD COLUMN model TEXT DEFAULT 'llama3.2:1b'")
        if "image_data" not in cols:
            cursor.execute("ALTER TABLE messages ADD COLUMN image_data TEXT")

        # Conversation metadata table for titles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_metadata (
                conversation_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                persona TEXT DEFAULT 'default',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    init_memory_table()
    init_conversation_memory_table()


initialize_database()

# Build and verify knowledge index in ChromaDB
knowledge_index = build_knowledge_index()

# ----------------------------------------------------
# FASTAPI APPLICATION & MIDDLEWARE
# ----------------------------------------------------

app = FastAPI(
    title="MyAI Advanced Personal AI Platform",
    description="Next-generation locally powered personal intelligence engine",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-ID", "X-Model-Used"]
)

# Performance monitoring metrics
REQUEST_METRICS = {
    "total_requests": 0,
    "start_time": time.time(),
    "last_response_time_ms": 0
}

# ----------------------------------------------------
# REQUEST / RESPONSE MODELS
# ----------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    model: Optional[str] = None
    persona: Optional[str] = "default"
    web_search_enabled: Optional[bool] = False
    image_data: Optional[str] = None
    image_name: Optional[str] = None


class RenameConversationRequest(BaseModel):
    title: str


class ActionExecutionRequest(BaseModel):
    action_id: str
    approved: bool = True


class AuthRequest(BaseModel):
    username: str
    password: str


# ----------------------------------------------------
# SYSTEM & HEALTH ENDPOINTS
# ----------------------------------------------------

@app.get("/")
def home():
    """Serve the unified single-page web application."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "app": "MyAI Advanced Assistant",
        "version": "2.0.0",
        "status": "online"
    }


@app.get("/api")
def api_info():
    return {
        "app": "MyAI Advanced Assistant API",
        "version": "2.0.0",
        "status": "online",
        "docs_url": "/docs"
    }


@app.get("/health")
def health():
    ollama_info = check_ollama_status()
    stats = vector_store.get_stats()
    return {
        "status": "healthy",
        "ollama": ollama_info,
        "chromadb": stats,
        "uptime_seconds": round(time.time() - REQUEST_METRICS["start_time"], 1)
    }


@app.post("/system/shutdown")
def shutdown_server():
    """Gracefully stop the server process from the Web UI."""
    def delayed_exit():
        time.sleep(0.8)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=delayed_exit, daemon=True).start()
    return {"status": "shutting_down", "message": "MyAI server is stopping..."}


@app.get("/stats")
def get_system_stats():
    """Provides hardware, vector store, and performance statistics."""
    ollama_info = check_ollama_status()
    vector_stats = vector_store.get_stats()
    all_memories = get_all_memories()

    with get_connection() as conn:
        total_msgs = conn.execute("SELECT count(*) FROM messages").fetchone()[0]
        total_convs = conn.execute("SELECT count(DISTINCT conversation_id) FROM messages").fetchone()[0]

    return {
        "ollama": ollama_info,
        "total_conversations": total_convs,
        "total_messages": total_msgs,
        "total_memories": len(all_memories),
        "vector_store": vector_stats,
        "metrics": REQUEST_METRICS
    }


# ----------------------------------------------------
# MODEL & PERSONA ENDPOINTS
# ----------------------------------------------------

@app.get("/models")
def get_models():
    """List all installed Ollama models and recommended models."""
    installed = get_installed_models()
    chat_models = get_available_chat_models()
    return {
        "installed_models": installed,
        "chat_models": chat_models,
        "recommended_models": RECOMMENDED_MODELS,
        "default_model": resolve_model(None)
    }


@app.get("/personas")
def get_personas():
    """List available AI personas with descriptions."""
    return {"personas": list_personas()}


# ----------------------------------------------------
# CORE CHAT & STREAMING LOGIC
# ----------------------------------------------------

def build_chat_context(
    message: str,
    conversation_id: str,
    persona_key: str = "default",
    web_search_enabled: bool = False
) -> Dict[str, Any]:
    """
    Assembles long-term memories, conversation summaries, RAG context,
    web search citations, and system reasoning guidance into a unified prompt.
    """
    # 1. Fetch conversation history
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,)
        ).fetchall()

    all_history = [{"id": r["id"], "role": r["role"], "content": r["content"]} for r in rows]

    # 2. Conversation Summarization (Triggered above 20 messages)
    conversation_summary, last_summarized_id = get_conversation_summary_state(conversation_id)
    history = all_history

    if len(all_history) > 20:
        recent_history = all_history[-10:]
        old_messages = [m for m in all_history[:-10] if m["id"] > last_summarized_id]
        if len(old_messages) >= 8:
            summary_input = []
            if conversation_summary:
                summary_input.append({
                    "role": "user",
                    "content": f"Previous conversation summary:\n{conversation_summary}"
                })
            summary_input.extend([{"role": m["role"], "content": m["content"]} for m in old_messages])

            try:
                new_summary = generate_conversation_summary(summary_input)
                if new_summary:
                    last_id = old_messages[-1]["id"]
                    save_conversation_summary(conversation_id, new_summary, last_id)
                    conversation_summary = new_summary
            except Exception as exc:
                print(f"[Chat] Summarization error: {exc}")

        history = recent_history

    # Token trim history
    history = trim_history_by_tokens(history, max_tokens=3000)
    history_clean = [{"role": m["role"], "content": m["content"]} for m in history]

    # 3. Retrieve Long-Term Memories
    memories = retrieve_relevant_memories(message, top_k=5, threshold=0.38)
    if memories:
        memory_context = "\n".join([f"- [{m['category']}] {m['content']}" for m in memories])
    else:
        memory_context = "No previous user memories relevant to this prompt."

    # 4. Retrieve RAG Document Knowledge
    rag_chunks = retrieve_context(message, top_k=4, threshold=0.38)
    if rag_chunks:
        doc_context = "\n\n".join([
            f"[Document Source: {c['source']} | Relevance: {int(c['score'] * 100)}%]\n{c['text']}"
            for c in rag_chunks
        ])
    else:
        doc_context = "No uploaded documents match this query."

    # 5. Optional Web Search Context
    web_context = ""
    if web_search_enabled or any(k in message.lower() for k in ["search web", "latest news", "current price", "search for"]):
        try:
            search_hits = search_web(message, max_results=3)
            if search_hits:
                web_context = format_search_results(search_hits)
        except Exception as exc:
            print(f"[Chat] Web search error: {exc}")

    # 6. Question Analysis & Reasoning
    reasoning = analyze_question(message)
    reasoning_type = reasoning["type"]
    reasoning_instruction = reasoning["instruction"]
    response_format = get_response_format(reasoning_type)
    quality_instructions = get_quality_instructions()

    persona_prompt = get_personality(persona_key)

    system_prompt = f"""
{persona_prompt}

PERSISTENT USER MEMORIES:
{memory_context}

CONVERSATION SUMMARY:
{conversation_summary or "No previous summary."}

DOCUMENT KNOWLEDGE BASE (Cite these sources when applicable):
{doc_context}

{web_context}

REASONING DIRECTIVES:
- Primary domain: {reasoning_type.upper()}
- Task guidance: {reasoning_instruction}
- Recommended format:
{response_format}

{quality_instructions}
""".strip()

    messages = [{"role": "system", "content": system_prompt}] + history_clean

    return {
        "messages": messages,
        "conversation_id": conversation_id,
        "memories_used": memories,
        "docs_used": rag_chunks,
        "reasoning": reasoning
    }


@app.post("/chat")
def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """Standard non-streaming chat endpoint with full RAG and memory synthesis."""
    REQUEST_METRICS["total_requests"] += 1
    t0 = time.time()

    conversation_id = request.conversation_id or str(uuid.uuid4())
    if not request.message.strip() and not request.image_data:
        raise HTTPException(status_code=400, detail="Message or image cannot be empty.")

    selected_model = resolve_model(request.model)

    # 1. Save user message
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, model, image_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, "user", request.message, selected_model, request.image_data)
        )
        # Record metadata title if first message
        conn.execute(
            """
            INSERT OR IGNORE INTO conversation_metadata (conversation_id, title, persona)
            VALUES (?, ?, ?)
            """,
            (conversation_id, request.message[:40] if request.message else "Image Query", request.persona or "default")
        )

    # 2. Extract memories asynchronously in background
    if request.message.strip():
        background_tasks.add_task(extract_and_save_memories, request.message)

    # 3. Handle Multimodal Vision query if image is attached
    if request.image_data:
        vision_result = analyze_image_with_ollama(
            prompt=request.message,
            image_base64=request.image_data,
            model=selected_model
        )
        if vision_result.get("success"):
            reply = vision_result["analysis"]
        else:
            reply = f"Image Analysis Notice: {vision_result.get('error', 'Unable to process image.')}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, model) VALUES (?, ?, ?, ?)",
                (conversation_id, "assistant", reply, selected_model)
            )
        return {
            "conversation_id": conversation_id,
            "reply": reply,
            "model_used": selected_model
        }

    # 4. Build text chat context
    context_bundle = build_chat_context(
        message=request.message,
        conversation_id=conversation_id,
        persona_key=request.persona or "default",
        web_search_enabled=request.web_search_enabled or False
    )

    # 5. Send to Ollama
    try:
        res = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": selected_model,
                "messages": context_bundle["messages"],
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 1024
                }
            },
            timeout=120
        )
        res.raise_for_status()
        reply = res.json().get("message", {}).get("content", "")
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="MyAI took too long to respond. Please try again.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ollama communication error: {exc}")

    # 6. Store AI response
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, model) VALUES (?, ?, ?, ?)",
            (conversation_id, "assistant", reply, selected_model)
        )

    REQUEST_METRICS["last_response_time_ms"] = round((time.time() - t0) * 1000, 1)

    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "model_used": selected_model,
        "memories_count": len(context_bundle["memories_used"]),
        "docs_count": len(context_bundle["docs_used"])
    }


@app.post("/chat/stream")
def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """High-performance streaming chat endpoint with live token yield and DB saving."""
    REQUEST_METRICS["total_requests"] += 1

    conversation_id = request.conversation_id or str(uuid.uuid4())
    if not request.message.strip() and not request.image_data:
        raise HTTPException(status_code=400, detail="Message or image cannot be empty.")

    selected_model = resolve_model(request.model)

    # 1. Save user message
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, model, image_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, "user", request.message, selected_model, request.image_data)
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO conversation_metadata (conversation_id, title, persona)
            VALUES (?, ?, ?)
            """,
            (conversation_id, request.message[:40] if request.message else "Image Query", request.persona or "default")
        )

    # 2. Extract memories asynchronously in background
    if request.message.strip():
        background_tasks.add_task(extract_and_save_memories, request.message)

    # 3. Vision check
    if request.image_data:
        vision_result = analyze_image_with_ollama(
            prompt=request.message,
            image_base64=request.image_data,
            model=selected_model
        )
        reply = vision_result.get("analysis") if vision_result.get("success") else vision_result.get("error", "Vision error")

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, model) VALUES (?, ?, ?, ?)",
                (conversation_id, "assistant", reply, selected_model)
            )

        def stream_single():
            yield reply

        return StreamingResponse(
            stream_single(),
            media_type="text/plain",
            headers={"X-Conversation-ID": conversation_id, "X-Model-Used": selected_model}
        )

    # 4. Context bundle
    context_bundle = build_chat_context(
        message=request.message,
        conversation_id=conversation_id,
        persona_key=request.persona or "default",
        web_search_enabled=request.web_search_enabled or False
    )

    def stream_and_persist():
        collected_chunks = []
        try:
            with requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": selected_model,
                    "messages": context_bundle["messages"],
                    "stream": True,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 1200
                    }
                },
                stream=True,
                timeout=(10, 180)
            ) as res:
                res.raise_for_status()
                for line in res.iter_lines():
                    if line:
                        try:
                            payload = json.loads(line)
                            chunk = payload.get("message", {}).get("content", "")
                            if chunk:
                                collected_chunks.append(chunk)
                                yield chunk
                        except json.JSONDecodeError:
                            continue

            full_reply = "".join(collected_chunks)
            if full_reply.strip():
                with get_connection() as conn:
                    conn.execute(
                        "INSERT INTO messages (conversation_id, role, content, model) VALUES (?, ?, ?, ?)",
                        (conversation_id, "assistant", full_reply, selected_model)
                    )
        except requests.Timeout:
            yield "\n[MyAI Alert: Model stream timed out. Please check your system workload.]"
        except requests.RequestException as exc:
            yield f"\n[MyAI Alert: Connection to Ollama failed ({exc}). Verify that Ollama is running.]"
        except Exception as exc:
            yield f"\n[MyAI Alert: Internal streaming error: {exc}]"

    return StreamingResponse(
        stream_and_persist(),
        media_type="text/plain",
        headers={
            "X-Conversation-ID": conversation_id,
            "X-Model-Used": selected_model
        }
    )


# ----------------------------------------------------
# CONVERSATION MANAGEMENT ENDPOINTS
# ----------------------------------------------------

@app.get("/conversations")
def get_conversations():
    """Returns conversation list with custom titles and timestamps."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                m.conversation_id,
                COALESCE(cm.title, SUBSTR(m.content, 1, 40)) AS title,
                MIN(m.created_at) AS created_at,
                MAX(m.id) AS last_message_id,
                COALESCE(cm.persona, 'default') AS persona
            FROM messages m
            LEFT JOIN conversation_metadata cm ON m.conversation_id = cm.conversation_id
            GROUP BY m.conversation_id
            ORDER BY last_message_id DESC
        """).fetchall()

        conversations = []
        for r in rows:
            preview_row = conn.execute(
                "SELECT content FROM messages WHERE id = ?",
                (r["last_message_id"],)
            ).fetchone()
            conversations.append({
                "conversation_id": r["conversation_id"],
                "title": r["title"] or "Conversation",
                "created_at": r["created_at"],
                "persona": r["persona"],
                "preview": preview_row["content"] if preview_row else ""
            })

    return {"conversations": conversations}


@app.get("/history/{conversation_id}")
def get_history(conversation_id: str):
    """Retrieve full message history for a conversation."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, model, image_data, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,)
        ).fetchall()

    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "role": r["role"],
                "content": r["content"],
                "model": r["model"],
                "image_data": r["image_data"],
                "created_at": r["created_at"]
            }
            for r in rows
        ]
    }


@app.put("/conversations/{conversation_id}/rename")
def rename_conversation(conversation_id: str, req: RenameConversationRequest):
    """Rename a conversation."""
    clean_title = req.title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversation_metadata (conversation_id, title)
            VALUES (?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET title = excluded.title
            """,
            (conversation_id, clean_title)
        )
    return {"success": True, "title": clean_title}


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    """Delete a conversation, summary, and metadata."""
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversation_summaries WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversation_metadata WHERE conversation_id = ?", (conversation_id,))
    return {"message": "Conversation deleted successfully", "conversation_id": conversation_id}


# ----------------------------------------------------
# DOCUMENT & RAG MANAGEMENT ENDPOINTS
# ----------------------------------------------------

@app.post("/upload-document")
@app.post("/upload-pdf")
async def upload_document(file: UploadFile = File(...)):
    """Upload and index documents (PDF, DOCX, TXT, MD, Code) into ChromaDB."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:  # 25 MB limit
        raise HTTPException(status_code=413, detail="File exceeds 25 MB limit.")

    # Generate safe unique filename
    safe_name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    file_path = KNOWLEDGE_DIR / safe_name
    file_path.write_bytes(content)

    # Index into ChromaDB
    chunks_indexed = index_single_document(file_path)

    return {
        "message": f"Document '{Path(file.filename).name}' indexed successfully.",
        "filename": safe_name,
        "original_name": file.filename,
        "chunks_indexed": chunks_indexed,
        "total_knowledge_chunks": vector_store.doc_col.count()
    }


@app.get("/documents")
def get_documents():
    """List all documents currently in the knowledge repository."""
    docs = []
    for f in KNOWLEDGE_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            docs.append({
                "filename": f.name,
                "type": f.suffix.lower(),
                "size_kb": round(f.stat().st_size / 1024, 1)
            })
    return {
        "documents": docs,
        "total": len(docs),
        "total_chunks": vector_store.doc_col.count()
    }


@app.delete("/documents/{filename}")
def delete_document(filename: str):
    """Remove a document from storage and delete all associated vector chunks."""
    safe_name = Path(filename).name
    file_path = KNOWLEDGE_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")

    file_path.unlink()
    vector_store.delete_document(safe_name)

    return {
        "message": f"Document '{safe_name}' deleted.",
        "remaining_chunks": vector_store.doc_col.count()
    }


# ----------------------------------------------------
# MEMORY MANAGEMENT ENDPOINTS
# ----------------------------------------------------

@app.get("/memories")
def get_memories():
    """Fetch all saved long-term memories."""
    memories = get_all_memories()
    return {
        "total": len(memories),
        "memories": [
            {
                "id": m[0],
                "content": m[1],
                "category": m[2],
                "created_at": m[3]
            }
            for m in memories
        ]
    }


@app.delete("/memories/{memory_id}")
def remove_memory(memory_id: int):
    """Delete a specific memory by ID."""
    deleted = delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"message": "Memory deleted successfully", "memory_id": memory_id}


# ----------------------------------------------------
# AI AGENT & APPROVAL ENDPOINTS
# ----------------------------------------------------

@app.get("/agent/tools")
def list_agent_tools():
    """List available agent tools and safety requirements."""
    return {
        "tools": [
            {
                "name": name,
                "description": info["description"],
                "requires_approval": info["requires_approval"]
            }
            for name, info in TOOLS.items()
        ]
    }


@app.get("/agent/pending-actions")
def pending_agent_actions():
    """Retrieve all tool actions awaiting user approval."""
    return {"pending_actions": get_pending_actions()}


@app.post("/agent/execute-action")
def execute_agent_action(req: ActionExecutionRequest):
    """Execute or reject a human-in-the-loop tool action."""
    res = execute_action(req.action_id, approved=req.approved)
    return res


# ----------------------------------------------------
# AUTHENTICATION & SESSION ENDPOINTS
# ----------------------------------------------------

@app.post("/auth/register")
def api_register(req: AuthRequest):
    res = register_user(req.username, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Registration failed"))
    return res


@app.post("/auth/login")
def api_login(req: AuthRequest):
    res = authenticate_user(req.username, req.password)
    if not res.get("success"):
        raise HTTPException(status_code=401, detail=res.get("error", "Authentication failed"))
    return res


@app.get("/auth/me")
def api_me(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user = validate_session(token)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}


@app.post("/auth/logout")
def api_logout(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    if token:
        invalidate_session(token)
    return {"message": "Logged out successfully"}


# ----------------------------------------------------
# SERVE UNIFIED FRONTEND SINGLE-PAGE APPLICATION
# ----------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ----------------------------------------------------
# RUNTIME ENTRY POINT
# ----------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    print("\n[MyAI] Starting MyAI Platform Server on http://127.0.0.1:8000...")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
