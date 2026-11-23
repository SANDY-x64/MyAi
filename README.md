# ✨ MyAI - Advanced Personal AI Assistant & Platform

[![Direct Access](https://img.shields.io/badge/Direct%20Live%20App-Cloudflare%20Tunnel-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://consistent-participants-parameters-triple.trycloudflare.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Inference-Ollama%20Local-black?style=for-the-badge&logo=ollama&logoColor=white)](https://ollama.ai/)
[![ChromaDB](https://img.shields.io/badge/Vector%20DB-ChromaDB%201.5-purple?style=for-the-badge)](https://www.trychroma.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

> 🌐 **Direct Live Access Link:** [https://consistent-participants-parameters-triple.trycloudflare.com/](https://consistent-participants-parameters-triple.trycloudflare.com/)  
> *(Click above to access your live MyAI assistant from any browser, phone, or tablet!)*

**MyAI** is an advanced, privacy-first personal AI platform similar to ChatGPT, powered entirely on your local machine using **Ollama**, **FastAPI**, **ChromaDB**, and **SQLite**. It features persistent hybrid long-term memory, multi-format RAG document intelligence, autonomous tool-calling agents with human approval, multimodal speech and vision, live web search with citations, and a sleek, responsive ChatGPT-style web interface.

---

## 🚀 Key Features

* **🌐 Unified Single Web Application**: Run one command (`run.bat` or `python run.py`), and FastAPI serves both the complete ChatGPT-like UI and the high-performance streaming backend in the exact same application.
* **⚡ Direct Cloudflare Access**: Zero-configuration secure HTTPS tunnel to access your locally running assistant from any device anywhere in the world.
* **🧠 Dynamic Multi-Model Local AI**: Auto-discovers and connects to your local Ollama models (`llama3.2:1b`, `llama3.2:3b`, `qwen2.5`, `deepseek-r1`, `llava`) with seamless on-the-fly model switching and hardware resource awareness.
* **💾 Hybrid Persistent Memory**: Combines SQLite relational data with a ChromaDB vector store (`nomic-embed-text` embeddings) for semantic user memory recall across conversations.
* **📄 RAG & Document Intelligence**: Upload and chat with **PDF**, **Word (.docx)**, **Text (.txt)**, **Markdown (.md)**, **CSV**, and **source code files** (.py, .js, .java, .c, .sql) with semantic chunking and relevance citations.
* **🎙️ Multimodal Voice & Vision**:
  * **Speech-to-Text (STT)**: Built-in voice input microphone using the Web Speech API with live pulsating audio feedback.
  * **Text-to-Speech (TTS)**: One-click voice readout on every assistant message.
  * **Vision Understanding**: Image attachment with thumbnail previews, routed to local Ollama vision models (`llama3.2-vision`, `llava`).
* **🤖 Autonomous AI Agent with Human-in-the-Loop Safety**:
  * Deconstructs complex goals into planned steps.
  * Tools: Web search, webpage scraper, RAG retrieval, memory recall, and file inspection.
  * **Human Approval Gate**: Sensitive actions like writing files or running code prompt the user with interactive approval cards before execution.
* **🔍 Factual Web Search**: Live search and knowledge retrieval with automatic markdown source citations without external API keys.
* **🎭 Customizable AI Personas**:
  * **MyAI Standard**: Versatile, helpful daily assistant.
  * **Senior Software Architect**: Clean architecture, debugging, multi-language coding (Python, C, Java, JavaScript, Rust).
  * **Research Scientist**: Rigorous literature synthesis and academic depth.
  * **Socratic Tutor**: Patient, conceptual analogies and guided learning.
  * **Executive Briefing**: Ultra-concise, action-oriented bullet summaries.
* **🔒 Authentication & Security**: Built-in PBKDF2-HMAC-SHA256 password hashing, cryptographic session tokens, and input validation.

---

## 🏛️ Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │          MyAI Web Client               │
                      │  (ChatGPT-like UI / Cloudflare Tunnel) │
                      └───────────────────┬────────────────────┘
                                          │ Streaming SSE / REST
                                          ▼
                      ┌────────────────────────────────────────┐
                      │          FastAPI Unified Server        │
                      │             (backend/main.py)          │
                      └───────┬───────────┬────────────┬───────┘
                              │           │            │
             ┌────────────────┘           │            └───────────────┐
             ▼                            ▼                            ▼
  ┌────────────────────┐       ┌────────────────────┐       ┌────────────────────┐
  │   Local Ollama     │       │     ChromaDB       │       │      SQLite        │
  │     Daemon         │       │    Vector Store    │       │     Database       │
  │ (LLMs & Embeddings)│       │  (Memories & RAG)  │       │ (Chats & Sessions) │
  └────────────────────┘       └────────────────────┘       └────────────────────┘
```

---

## ⚡ Quickstart Guide

### 1. Prerequisites
* **Python 3.12+**
* **Ollama** installed and running ([https://ollama.ai](https://ollama.ai)):
  ```bash
  ollama pull llama3.2:1b
  ollama pull nomic-embed-text
  ```

### 2. Clone and Setup
```bash
git clone https://github.com/SANDY-x64/MyAi.git
cd MyAi
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Turning Server ON / OFF

#### 🟢 Turning Server ON

- **Option A (Local Only)**: Double-click **`start_local.bat`** (or `run.bat`).
  Opens the app automatically at **`http://127.0.0.1:8000`**.
- **Option B (Public Cloudflare Access)**: Double-click **`start_public_tunnel.bat`**.
  Generates a secure public HTTPS link allowing access from any phone, laptop, or remote network:
  ```
  🎉 LIVE CLOUDFLARE PUBLIC URL: https://falls-mobility-wing-notify.trycloudflare.com
  ```

#### 🔴 Turning Server OFF

- **Method 1 (One-Click File)**: Double-click **`stop_myai.bat`** on your desktop/folder. It automatically terminates the server and any running Cloudflare tunnels.
- **Method 2 (In-App Power Button)**: Click the **"Turn Off Server"** red button at the bottom of the sidebar directly inside the web app.
- **Method 3 (Terminal Shortcut)**: Press `Ctrl + C` in the terminal window where the server is running.

---

## 📁 Project Structure

```
MyAi/
├── backend/
│   ├── main.py                 # FastAPI application, streaming & routes
│   ├── agent.py                # AI agent system with human approval gate
│   ├── auth.py                 # PBKDF2 password hashing & session management
│   ├── model_manager.py        # Ollama model discovery & hardware optimizer
│   ├── multimodal.py           # Vision analysis & voice handling
│   ├── memory.py               # Hybrid memory engine (SQLite + ChromaDB)
│   ├── conversation_memory.py  # Conversation summarizer
│   ├── personality.py          # Personas & system prompt architectures
│   ├── rag.py                  # Multi-format document chunker & RAG
│   ├── reasoning.py            # Question classification & quality evaluator
│   ├── vector_store.py         # Persistent ChromaDB collections
│   ├── web_search.py           # Live search & source citations
│   ├── test_e2e_full.py        # End-to-end integration test suite
│   └── test_quick.py           # In-process TestClient suite
├── frontend/                   # Modern responsive ChatGPT-style web UI
│   ├── index.html
│   ├── script.js
│   └── style.css
├── knowledge/                  # Uploaded knowledge documents (.pdf, .docx, .txt)
├── workspace/                  # Sandboxed agent file output directory
├── tunnel_launcher.py          # Starts server and public Cloudflare Tunnel
├── start_local.bat             # One-click start for local access
├── start_public_tunnel.bat     # One-click start with public Cloudflare link
├── stop_myai.bat               # One-click graceful stop for server & tunnels
├── run.bat                     # Windows launcher shortcut
├── run.py                      # Cross-platform application launcher
└── README.md
```

---

## 🧪 Automated Testing

Run the full end-to-end integration suite:
```bash
python -m backend.test_e2e_full
```

Run the in-process API test suite:
```bash
python -m backend.test_quick
```

---

## 📄 License
This project is licensed under the MIT License.
