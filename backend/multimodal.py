"""
MyAI Multimodal Engine (Vision & Voice Processing)
Handles image understanding, visual analysis, OCR, and speech audio endpoints.
Integrates with Ollama multimodal vision models (llama3.2-vision, llava).
"""

import base64
import io
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from backend.model_manager import get_installed_models, OLLAMA_BASE_URL, DEFAULT_CHAT_MODEL

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def is_image_file(filename: str) -> bool:
    """Check if file has an image extension."""
    return Path(filename).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def encode_image_to_base64(image_bytes: bytes) -> str:
    """Encode raw image bytes to a base64 string for Ollama vision API."""
    return base64.b64encode(image_bytes).decode("utf-8")


def get_available_vision_models() -> list[str]:
    """Return list of installed vision-capable models in Ollama."""
    models = get_installed_models()
    return [m["name"] for m in models if m.get("is_vision", False)]


def analyze_image_with_ollama(
    prompt: str,
    image_base64: str,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends an image and a user prompt to an Ollama vision model.
    Falls back gracefully if no vision model is installed.
    """
    vision_models = get_available_vision_models()

    target_model = None
    if model and model in vision_models:
        target_model = model
    elif vision_models:
        target_model = vision_models[0]
    else:
        # Check if default model might support vision
        target_model = model or DEFAULT_CHAT_MODEL

    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": target_model,
        "prompt": prompt or "Describe and analyze this image in detail.",
        "images": [image_base64],
        "stream": False
    }

    try:
        res = requests.post(url, json=payload, timeout=120)
        if res.status_code == 200:
            data = res.json()
            return {
                "success": True,
                "model_used": target_model,
                "analysis": data.get("response", "").strip()
            }
        elif res.status_code == 404 or "does not support images" in res.text.lower():
            return {
                "success": False,
                "error": (
                    f"Model '{target_model}' does not support image analysis. "
                    "To enable vision capabilities, run: 'ollama pull llama3.2-vision' or 'ollama pull llava'."
                )
            }
        else:
            return {
                "success": False,
                "error": f"Ollama vision request failed: HTTP {res.status_code} - {res.text}"
            }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Image analysis error: {exc}"
        }
