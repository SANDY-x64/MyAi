"""
MyAI Model Management Engine
Discovers, validates, and manages local Ollama language and embedding models.
Optimized for the local hardware profile (16 GB RAM, AMD Ryzen 7).
"""

import requests
from typing import Optional

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_CHAT_MODEL = "llama3.2:1b"
DEFAULT_EMBED_MODEL = "nomic-embed-text"

# Hardware-optimized recommendations for 16GB RAM
RECOMMENDED_MODELS = [
    {
        "name": "llama3.2:1b",
        "category": "Ultra-Fast / Low Resource",
        "description": "Blazing fast general assistant, minimal RAM usage (~1.3 GB).",
        "context_length": 8192,
        "is_vision": False
    },
    {
        "name": "llama3.2:3b",
        "category": "Balanced Daily Driver",
        "description": "High intelligence, excellent coding and reasoning (~2.0 GB).",
        "context_length": 8192,
        "is_vision": False
    },
    {
        "name": "qwen2.5:3b",
        "category": "Code & Multilingual",
        "description": "Superior code generation and multilingual comprehension (~2.0 GB).",
        "context_length": 32768,
        "is_vision": False
    },
    {
        "name": "qwen2.5:7b",
        "category": "Heavy Reasoning & Architecture",
        "description": "Deep reasoning, full architectural design and complex coding (~4.7 GB).",
        "context_length": 32768,
        "is_vision": False
    },
    {
        "name": "deepseek-r1:1.5b",
        "category": "Step-by-Step Chain of Thought",
        "description": "Built-in reasoning traces and mathematical logic (~1.1 GB).",
        "context_length": 16384,
        "is_vision": False
    },
    {
        "name": "llama3.2-vision:latest",
        "category": "Multimodal Vision",
        "description": "Image understanding, diagrams, and OCR analysis (~4.5 GB).",
        "context_length": 8192,
        "is_vision": True
    },
    {
        "name": "llava:7b",
        "category": "Multimodal Vision",
        "description": "Popular visual QA and image comprehension model (~4.7 GB).",
        "context_length": 4096,
        "is_vision": True
    }
]


def check_ollama_status() -> dict:
    """Check if Ollama daemon is reachable and responding."""
    try:
        res = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=(0.8, 1.5))
        if res.status_code == 200:
            version = res.json().get("version", "unknown")
            return {"online": True, "version": version}
        return {"online": False, "error": f"HTTP {res.status_code}"}
    except Exception as exc:
        return {"online": False, "error": str(exc)}


def get_installed_models() -> list[dict]:
    """Fetch all locally pulled Ollama models."""
    try:
        res = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=(0.8, 2.0))
        res.raise_for_status()
        models = res.json().get("models", [])
        formatted = []
        for m in models:
            name = m.get("name", "")
            size_bytes = m.get("size", 0)
            size_gb = round(size_bytes / (1024 ** 3), 2)
            modified_at = m.get("modified_at", "")
            is_embed = "embed" in name or "bge" in name
            is_vision = "vision" in name or "llava" in name or "moondream" in name

            formatted.append({
                "name": name,
                "size_gb": size_gb,
                "modified_at": modified_at,
                "is_embedding": is_embed,
                "is_vision": is_vision
            })
        return formatted
    except Exception as exc:
        print(f"Error fetching Ollama models: {exc}")
        return []


def get_available_chat_models() -> list[str]:
    """Return list of names for chat-capable models."""
    models = get_installed_models()
    chat_models = [m["name"] for m in models if not m["is_embedding"]]
    if not chat_models:
        chat_models = [DEFAULT_CHAT_MODEL]
    return chat_models


def resolve_model(requested_model: Optional[str]) -> str:
    """Resolve requested model name against installed models with sensible fallbacks."""
    chat_models = get_available_chat_models()
    if requested_model and requested_model.strip():
        req = requested_model.strip()
        # Direct match
        if req in chat_models:
            return req
        # Prefix match (e.g., 'llama3.2:1b' matching 'llama3.2:1b')
        for m in chat_models:
            if m.startswith(req) or req.startswith(m.split(":")[0]):
                return m
    # Return first available or default
    return chat_models[0] if chat_models else DEFAULT_CHAT_MODEL


def pull_model_stream(model_name: str):
    """Trigger pulling an Ollama model with streaming progress."""
    url = f"{OLLAMA_BASE_URL}/api/pull"
    with requests.post(url, json={"name": model_name}, stream=True, timeout=600) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                yield line.decode("utf-8")
