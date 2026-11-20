
# --------------------------------
# IMPORTS
# --------------------------------

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from backend.personality import SYSTEM_PERSONALITY
from backend.context_manager import trim_history_by_tokens


from backend.reasoning import (
    analyze_question,
    get_response_format,
    get_quality_instructions,
    detect_multiple_tasks
)

from backend.conversation_memory import (
    init_conversation_memory_table,
    get_conversation_summary,
    save_conversation_summary
)

from backend.conversation_memory import (
    get_conversation_summary_state,
    save_conversation_summary,
    generate_conversation_summary
)

from backend.memory import (
    init_memory_table,
    extract_and_save_memories,
    get_all_memories,
    delete_memory
)

from backend.rag import (
    KNOWLEDGE_DIR,
    build_knowledge_index,
    retrieve_context
)
#retrieve_relavant_memories
from backend.memory import (
    init_memory_table,
    save_memory,
    get_all_memories,
    delete_memory,
    extract_and_save_memories,
    retrieve_relevant_memories
)


import requests
import sqlite3
import uuid
import json


# --------------------------------
# PROJECT CONFIGURATION
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "myai.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------
# OLLAMA CONFIGURATION
# --------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = "llama3.2:1b"

# AI MODEL SETTINGS

TEMPERATURE = 0.7

TOP_P = 0.9

MAX_TOKENS = 1024
MAX_CONTEXT_TOKENS = 3000


# --------------------------------
# RAG CONFIGURATION
# --------------------------------

SIMILARITY_THRESHOLD = 0.45

MAX_RETRIEVED_CHUNKS = 3


# --------------------------------
# CONVERSATION CONFIGURATION
# --------------------------------

MAX_HISTORY_MESSAGES = 20
SUMMARY_TRIGGER_MESSAGES = 20
RECENT_MESSAGES = 10

# --------------------------------
# LOAD KNOWLEDGE DOCUMENTS
# --------------------------------

knowledge_index = build_knowledge_index()

print(
    "MyAI knowledge loaded:",
    len(knowledge_index),
    "chunks"
)


# --------------------------------
# FASTAPI APPLICATION
# --------------------------------

app = FastAPI(title="MyAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-ID"],
)


# --------------------------------
# DATABASE CONFIGURATION
# --------------------------------

def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():

    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                conversation_id TEXT NOT NULL,

                role TEXT NOT NULL,

                content TEXT NOT NULL,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            )
        """)


initialize_database()

# Initialize long-term memory database
init_memory_table()
init_conversation_memory_table()

# --------------------------------
# REQUEST MODEL
# --------------------------------

class ChatRequest(BaseModel):

    message: str

    conversation_id: str | None = None


# --------------------------------
# BASIC API ROUTES
# --------------------------------

@app.get("/")
def home():

    return {
        "message": "Welcome to MyAI!"
    }


@app.get("/health")
def health():

    return {
        "status": "MyAI is running"
    }


# --------------------------------
# MAIN CHAT ROUTE WITH RAG + MEMORY
# --------------------------------


@app.post("/chat")
def chat(request: ChatRequest):

    conversation_id = (
        request.conversation_id or str(uuid.uuid4())
    )

    if not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )

    # --------------------------------
    # STEP 1: STORE USER MESSAGE
    # --------------------------------

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO messages
            (conversation_id, role, content)
            VALUES (?, ?, ?)
            """,
            (conversation_id, "user", request.message)
        )

    # --------------------------------
    # STEP 2: GET FULL CONVERSATION
    # --------------------------------

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT id, role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,)
        ).fetchall()

    all_history = [
        {
            "id": row[0],
            "role": row[1],
            "content": row[2]
        }
        for row in rows
    ]

    # --------------------------------
    # STEP 3: CONVERSATION SUMMARIZATION
    # --------------------------------

    conversation_summary, last_summarized_id = (
        get_conversation_summary_state(conversation_id)
    )

    history = all_history

    if len(all_history) > SUMMARY_TRIGGER_MESSAGES:

        recent_history = all_history[-RECENT_MESSAGES:]

        old_messages = [
            message
            for message in all_history[:-RECENT_MESSAGES]
            if message["id"] > last_summarized_id
        ]

        if old_messages:

            summary_input = []

            if conversation_summary:
                summary_input.append({
                    "role": "user",
                    "content": (
                        "Previous conversation summary:\n"
                        + conversation_summary
                    )
                })

            summary_input.extend([
                {
                    "role": message["role"],
                    "content": message["content"]
                }
                for message in old_messages
            ])

            try:

                new_summary = generate_conversation_summary(
                    summary_input,
                    OLLAMA_URL,
                    MODEL
                )

                if new_summary:

                    last_message_id = old_messages[-1]["id"]

                    save_conversation_summary(
                        conversation_id,
                        new_summary,
                        last_message_id
                    )

                    conversation_summary = new_summary

                    print("\n--- CONVERSATION SUMMARY UPDATED ---")
                    print(conversation_summary)

            except Exception as error:

                print(
                    "Conversation summarization failed:",
                    error
                )

        history = recent_history

    else:

        history = all_history

    # Limit conversation history by token budget
    history = trim_history_by_tokens(
        history,
        MAX_CONTEXT_TOKENS
    )

    # Remove internal database IDs before sending history to Ollama

    history = [
        {
            "role": message["role"],
            "content": message["content"]
        }
        for message in history
    ]

    # --------------------------------
    # STEP 4: EXTRACT LONG-TERM MEMORIES
    # --------------------------------

    try:

        saved_count = extract_and_save_memories(
            request.message
        )

        print("\nNew memories saved:", saved_count)

    except Exception as error:

        print("Memory extraction failed:", error)


    # --------------------------------
    # STEP 5: RETRIEVE SAVED MEMORIES
    # --------------------------------

    memories = retrieve_relevant_memories(
        request.message,
        top_k=5,
        threshold=0.40
    )

    memory_context = "\n".join(
        [
            f"- [{memory['category']}] {memory['content']}"
            for memory in memories
        ]
    )

    if not memory_context:
        memory_context = "No long-term memories available."

    # --------------------------------
    # STEP 6: RETRIEVE RAG KNOWLEDGE
    # --------------------------------

    try:

        results = retrieve_context(
            request.message,
            knowledge_index,
            top_k=MAX_RETRIEVED_CHUNKS,
            threshold=SIMILARITY_THRESHOLD
        )

    except requests.RequestException as error:

        raise HTTPException(
            status_code=502,
            detail=f"Knowledge retrieval failed: {error}"
        )

    # --------------------------------
    # STEP 7: PREPARE DOCUMENT CONTEXT
    # --------------------------------

    if results:

        context = "\n\n".join(
            [
                f"Source: {item['source']}\n{item['text']}"
                for item in results
            ]
        )

    else:

        context = (
            "No sufficiently relevant document information "
            "was found. Answer using general knowledge when possible."
        )

    # --------------------------------
    # STEP 8: CREATE SYSTEM PROMPT
    # --------------------------------

    if not conversation_summary:
        conversation_summary = "No previous conversation summary available."

    # Analyze the user's question
    reasoning = analyze_question(request.message)

    reasoning_instruction = reasoning["instruction"]
    reasoning_type = reasoning["type"]
    response_format = get_response_format(reasoning_type)
    quality_instructions = get_quality_instructions()

    multiple_tasks = detect_multiple_tasks(request.message)

    task_instruction = ""

    if multiple_tasks["is_multiple"]:
        task_instruction = """
        MULTI-TASK QUESTION:
        Identify and answer every requested task.
        Organize the answer clearly.
        Do not skip any part of the request.
        """
    
    
    system_prompt = f"""
    {SYSTEM_PERSONALITY}

    LONG-TERM MEMORY:

    {memory_context}

    PREVIOUS CONVERSATION SUMMARY:

    {conversation_summary}

    DOCUMENT KNOWLEDGE:

    {context}

    IMPORTANT RULES:

    1. Use relevant saved memories.
    2. Use the previous conversation summary when relevant.
    3. Understand follow-up questions using recent conversation history.
    4. Use uploaded documents when relevant.
    5. Never invent personal information.
    6. Admit when you don't know something.

    REASONING GUIDANCE:
    MULTI-TASK GUIDANCE:

    {task_instruction}
    Question type: {reasoning_type}

    Instructions:
    {reasoning_instruction}

    - Solve the user's problem carefully.
    - Check the accuracy of your answer.
    - Explain important steps clearly.
    - Provide a concise explanation, not hidden internal reasoning.

    RESPONSE QUALITY:

    {quality_instructions}

        """
    multiple_tasks = detect_multiple_tasks(request.message)

    task_instruction = ""

    if multiple_tasks["is_multiple"]:
        task_instruction = """
        MULTI-TASK QUESTION:
        The user has asked a question containing multiple tasks.
        Identify and answer every requested task.
        Organize the answer clearly.
        Do not skip any part of the request.
        """
 # --------------------------------
 # STEP 9: BUILD OLLAMA MESSAGES
# --------------------------------

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ] + history

    # --------------------------------
    # STEP 10: SEND TO OLLAMA
    # --------------------------------

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": TEMPERATURE,
                    "top_p": TOP_P,
                    "num_predict": MAX_TOKENS
                }
            },
            timeout=120
        )

        response.raise_for_status()

        reply = response.json()["message"]["content"]

    except requests.Timeout:

        raise HTTPException(
            status_code=504,
            detail="MyAI took too long to respond. Please try again."
        )

    except requests.RequestException:

        raise HTTPException(
            status_code=502,
            detail="Unable to connect to Ollama. Please check whether Ollama is running."
        )

    except (ValueError, KeyError, TypeError):

        raise HTTPException(
        status_code=502,
        detail="Ollama returned an invalid response. Please try again."
    )

    # --------------------------------
    # STEP 11: STORE AI RESPONSE
    # --------------------------------

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO messages
            (conversation_id, role, content)
            VALUES (?, ?, ?)
            """,
            (conversation_id, "assistant", reply)
        )

    # --------------------------------
    # STEP 12: RETURN RESPONSE
    # --------------------------------

    return {
        "conversation_id": conversation_id,
        "reply": reply
    }


# --------------------------------
# STREAMING CHAT ENDPOINT
# --------------------------------

@app.post("/chat/stream")
def chat_stream(request: ChatRequest):

    conversation_id = (
        request.conversation_id or str(uuid.uuid4())
    )

    if not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )

    # --------------------------------
    # STEP 1: STORE USER MESSAGE
    # --------------------------------

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO messages
            (conversation_id, role, content)
            VALUES (?, ?, ?)
            """,
            (conversation_id, "user", request.message)
        )

    # --------------------------------
    # STEP 2: GET FULL CONVERSATION
    # --------------------------------

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT id, role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,)
        ).fetchall()

    all_history = [
        {
            "id": row[0],
            "role": row[1],
            "content": row[2]
        }
        for row in rows
    ]

    # --------------------------------
    # STEP 3: CONVERSATION SUMMARIZATION
    # --------------------------------

    conversation_summary, last_summarized_id = (
        get_conversation_summary_state(conversation_id)
    )

    history = all_history

    if len(all_history) > SUMMARY_TRIGGER_MESSAGES:

        recent_history = all_history[-RECENT_MESSAGES:]

        old_messages = [
            message
            for message in all_history[:-RECENT_MESSAGES]
            if message["id"] > last_summarized_id
        ]

        # Summarize only when a new batch is ready
        if len(old_messages) >= RECENT_MESSAGES:

            summary_input = []

            if conversation_summary:
                summary_input.append({
                    "role": "user",
                    "content": (
                        "Previous conversation summary:\n"
                        + conversation_summary
                    )
                })

            summary_input.extend([
                {
                    "role": message["role"],
                    "content": message["content"]
                }
                for message in old_messages
            ])

            try:

                new_summary = generate_conversation_summary(
                    summary_input,
                    OLLAMA_URL,
                    MODEL
                )

                if new_summary:

                    last_message_id = old_messages[-1]["id"]

                    save_conversation_summary(
                        conversation_id,
                        new_summary,
                        last_message_id
                    )

                    conversation_summary = new_summary

                    print("\n--- CONVERSATION SUMMARY UPDATED ---")
                    print(conversation_summary)

            except Exception as error:

                print("Conversation summarization failed:", error)

        history = recent_history

    else:

        history = all_history

    # Limit conversation history by token budget
    history = trim_history_by_tokens(
        history,
        MAX_CONTEXT_TOKENS
    )

    # Remove internal database IDs

    history = [
        {
            "role": message["role"],
            "content": message["content"]
        }
        for message in history
    ]

    # --------------------------------
    # STEP 4: EXTRACT MEMORIES
    # --------------------------------

    try:

        extract_and_save_memories(request.message)

    except Exception as error:

        print("Memory extraction failed:", error)
    # --------------------------------
    # STEP 5: GET LONG-TERM MEMORIES
    # --------------------------------

    memories = retrieve_relevant_memories(
        request.message, 
        top_k=5,
        threshold=0.40
    )

    memory_context = "\n".join(
        [
            f"- [{memory['category']}] {memory['content']}"
            for memory in memories
        ]
    )

    if not memory_context:
        memory_context = "No long-term memories available."

    # --------------------------------
    # STEP 6: RETRIEVE DOCUMENT KNOWLEDGE
    # --------------------------------

    try:

        results = retrieve_context(
            request.message,
            knowledge_index,
            top_k=MAX_RETRIEVED_CHUNKS,
            threshold=SIMILARITY_THRESHOLD
        )

    except requests.RequestException as error:

        raise HTTPException(
            status_code=502,
            detail=f"Knowledge retrieval failed: {error}"
        )

    # --------------------------------
    # STEP 7: PREPARE DOCUMENT CONTEXT
    # --------------------------------

    if results:

        context = "\n\n".join(
            [
                f"Source: {item['source']}\n{item['text']}"
                for item in results
            ]
        )

    else:

        context = (
            "No relevant document information found. "
            "Use general knowledge when possible."
        )

    # --------------------------------
    # STEP 8: SYSTEM PROMPT
    # --------------------------------

    if not conversation_summary:
        conversation_summary = (
            "No previous conversation summary available."
        )
        # Analyze the user's question
    reasoning = analyze_question(request.message)

    reasoning_instruction = reasoning["instruction"]
    reasoning_type = reasoning["type"]
    response_format = get_response_format(reasoning_type)
    quality_instructions = get_quality_instructions()

    multiple_tasks = detect_multiple_tasks(request.message)

    task_instruction = ""

    if multiple_tasks["is_multiple"]:
        task_instruction = """
        MULTI-TASK QUESTION:
        Identify and answer every requested task.
        Organize the answer clearly.
        Do not skip any part of the request.
        """

    system_prompt = f"""
    {SYSTEM_PERSONALITY}

    LONG-TERM MEMORY:

    {memory_context}

    PREVIOUS CONVERSATION SUMMARY:

    {conversation_summary}

    DOCUMENT KNOWLEDGE:

    {context}

    IMPORTANT RULES:

    1. Use relevant saved memories.
    2. Use the previous conversation summary when relevant.
    3. Understand follow-up questions using recent conversation history.
    4. Use uploaded documents when relevant.
    5. Never invent personal information.
    6. Admit when you don't know something.

    REASONING GUIDANCE:

    Question type: {reasoning_type}

    Instructions:
    {reasoning_instruction}

    - Solve the user's problem carefully.
    - Check the accuracy of your answer.
    - Explain important steps clearly.
    - Provide a concise explanation, not hidden internal reasoning.

    RESPONSE FORMAT:

    {response_format}

    Follow this structure when it is appropriate.
    Do not force unnecessary sections into simple answers.

    RESPONSE QUALITY:

    {quality_instructions}

    """

    # --------------------------------
    # STEP 9: BUILD OLLAMA MESSAGES
    # --------------------------------

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ] + history

    # --------------------------------
    # STEP 10: STREAM AND SAVE RESPONSE
    # --------------------------------

    def stream_and_save():

        collected_chunks = []

        try:

            for chunk in generate_stream(messages):

                collected_chunks.append(chunk)

                yield chunk

            full_reply = "".join(collected_chunks)

            with get_connection() as connection:

                connection.execute(
                    """
                    INSERT INTO messages
                    (conversation_id, role, content)
                    VALUES (?, ?, ?)
                    """,
                    (
                        conversation_id,
                        "assistant",
                        full_reply
                    )
                )

            print("\nStreaming response saved successfully.")

        except Exception as error:

            print("\nStreaming response failed:", error)
            raise

    return StreamingResponse(
        stream_and_save(),
        media_type="text/plain",
        headers={
            "X-Conversation-ID": conversation_id
        }
    )


# --------------------------------
# LIST ALL CONVERSATIONS
# --------------------------------

@app.get("/conversations")
def get_conversations():

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                conversation_id,
                MIN(created_at) AS created_at,
                MAX(id) AS last_message_id
            FROM messages
            GROUP BY conversation_id
            ORDER BY last_message_id DESC
            """
        ).fetchall()


        conversations = []

        for conversation_id, created_at, last_id in rows:

            preview = connection.execute(
                """
                SELECT content
                FROM messages
                WHERE id = ?
                """,
                (last_id,)
            ).fetchone()


            conversations.append({

                "conversation_id": conversation_id,

                "created_at": created_at,

                "preview": preview[0] if preview else ""

            })


    return {
        "conversations": conversations
    }


# --------------------------------
# UPLOAD PDF / DOCX
# --------------------------------

@app.post("/upload-pdf")
@app.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):

    global knowledge_index

    extension = Path(file.filename or "").suffix.lower()

    if extension not in [".pdf", ".docx"]:

        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are allowed"
        )


    content = await file.read()


    if len(content) > 10 * 1024 * 1024:

        raise HTTPException(
            status_code=413,
            detail="File must be smaller than 10 MB"
        )


    # Basic file validation

    if extension == ".pdf" and not content.startswith(b"%PDF-"):

        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file"
        )


    if extension == ".docx" and not content.startswith(b"PK"):

        raise HTTPException(
            status_code=400,
            detail="Invalid DOCX file"
        )


    filename = f"{uuid.uuid4()}{extension}"

    file_path = KNOWLEDGE_DIR / filename

    file_path.write_bytes(content)


    # Rebuild RAG index

    knowledge_index = build_knowledge_index()


    return {
        "message": "Document uploaded and indexed successfully",
        "filename": filename,
        "total_chunks": len(knowledge_index)
    }


# --------------------------------
# LIST DOCUMENTS
# --------------------------------

@app.get("/documents")
def get_documents():

    documents = []

    for file_path in KNOWLEDGE_DIR.iterdir():

        if file_path.suffix.lower() in [
            ".pdf",
            ".docx",
            ".txt"
        ]:

            documents.append({

                "filename": file_path.name,

                "type": file_path.suffix.lower()

            })


    return {
        "documents": documents,
        "total": len(documents)
    }


# --------------------------------
# DELETE DOCUMENT
# --------------------------------

@app.delete("/documents/{filename}")
def delete_document(filename: str):

    global knowledge_index

    if Path(filename).name != filename:

        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )


    file_path = KNOWLEDGE_DIR / filename


    if file_path.suffix.lower() not in [
        ".pdf",
        ".docx",
        ".txt"
    ]:

        raise HTTPException(
            status_code=400,
            detail="Unsupported document format"
        )


    if not file_path.is_file():

        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )


    file_path.unlink()


    # Rebuild RAG knowledge index

    knowledge_index = build_knowledge_index()


    return {
        "message": "Document deleted successfully",
        "filename": filename,
        "remaining_chunks": len(knowledge_index)
    }


# --------------------------------
# MEMORY MANAGEMENT
# --------------------------------

@app.get("/memories")
def get_memories():

    memories = get_all_memories()

    return {

        "total": len(memories),

        "memories": [

            {
                "id": memory[0],
                "content": memory[1],
                "category": memory[2],
                "created_at": memory[3]
            }

            for memory in memories

        ]
    }


# --------------------------------
# DELETE MEMORY
# --------------------------------

@app.delete("/memories/{memory_id}")
def remove_memory(memory_id: int):

    deleted = delete_memory(memory_id)


    if deleted == 0:

        raise HTTPException(
            status_code=404,
            detail="Memory not found"
        )


    return {
        "message": "Memory deleted successfully",
        "memory_id": memory_id
    }


# --------------------------------
# DELETE CONVERSATION
# --------------------------------

@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):

    with get_connection() as connection:

        cursor = connection.execute(
            """
            DELETE FROM messages
            WHERE conversation_id = ?
            """,
            (conversation_id,)
        )

        deleted_count = cursor.rowcount


    if deleted_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )


    return {
        "message": "Conversation deleted successfully",
        "conversation_id": conversation_id
    }


# --------------------------------
# GET CONVERSATION HISTORY
# --------------------------------

@app.get("/history/{conversation_id}")
def get_history(conversation_id: str):

    with get_connection() as connection:

        messages = connection.execute(
            """
            SELECT role, content, created_at
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
                "role": row[0],
                "content": row[1],
                "created_at": row[2]
            }

            for row in messages

        ]
    }

def generate_stream(messages):

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": messages,
                "stream": True,

                "options": {
                    "temperature": TEMPERATURE,
                    "top_p": TOP_P,
                    "num_predict": MAX_TOKENS
                }
            },
            stream=True,
            timeout=(10, 120)
        )

        response.raise_for_status()

        for line in response.iter_lines():

            if line:
                data = json.loads(line)

                content = data.get("message", {}).get("content", "")

                if content:
                    yield content

    except requests.Timeout:
        yield "\n[MyAI Error: Response timed out. Please try again.]"

    except requests.RequestException:
        yield "\n[MyAI Error: Unable to connect to Ollama.]"

    except (ValueError, KeyError, TypeError):
        yield "\n[MyAI Error: Invalid response from Ollama.]"
