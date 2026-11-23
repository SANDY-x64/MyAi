"""
MyAI Advanced RAG (Retrieval-Augmented Generation) & Document Intelligence Engine
Supports PDF, DOCX, TXT, MD, CSV, and Source Code files (.py, .js, .java, .c, .sql).
Integrates with ChromaDB vector store for instant, persistent semantic retrieval with source citations.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib
import re
import math
import requests

from pypdf import PdfReader
from docx import Document
from zipfile import BadZipFile

from backend.vector_store import (
    vector_store,
    get_embedding,
    get_embeddings_batch,
    cosine_similarity,
    OLLAMA_EMBED_URL,
    EMBED_MODEL
)

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXTENSIONS = {
    ".txt", ".pdf", ".docx", ".md", ".csv",
    ".py", ".js", ".ts", ".html", ".css", ".json", ".c", ".cpp", ".java", ".sql"
}


# ----------------------------------------------------
# FILE READERS
# ----------------------------------------------------

def read_pdf(file_path: Path) -> str:
    """Extract text content from a PDF document."""
    try:
        reader = PdfReader(str(file_path))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {i + 1}]\n{text.strip()}")
        return "\n\n".join(pages)
    except Exception as exc:
        print(f"[RAG] Error reading PDF {file_path.name}: {exc}")
        return ""


def read_docx(file_path: Path) -> str:
    """Extract text from Microsoft Word .docx documents."""
    try:
        document = Document(str(file_path))
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except (BadZipFile, ValueError, OSError) as exc:
        print(f"[RAG] Skipping invalid DOCX {file_path.name}: {exc}")
        return ""


def read_text_file(file_path: Path) -> str:
    """Read plaintext, markdown, CSV, or code files with multiple encoding fallbacks."""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            return file_path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="ignore")


def extract_document_text(file_path: Path) -> str:
    """Dispatches to the appropriate extractor based on file extension."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(file_path)
    elif suffix == ".docx":
        return read_docx(file_path)
    elif suffix in SUPPORTED_EXTENSIONS:
        return read_text_file(file_path)
    return ""


# ----------------------------------------------------
# ADVANCED SEMANTIC CHUNKING
# ----------------------------------------------------

def split_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    """
    Intelligent paragraph- and sentence-aware chunker.
    Preserves semantic boundaries while keeping chunk length bounded.
    """
    if not text or not text.strip():
        return []

    # First split by double newlines (paragraphs)
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}".strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If paragraph itself is longer than chunk_size, split by sentences or sliding window
            if len(para) > chunk_size:
                start = 0
                while start < len(para):
                    end = start + chunk_size
                    piece = para[start:end].strip()
                    if piece:
                        chunks.append(piece)
                    start += chunk_size - overlap
                current_chunk = ""
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# ----------------------------------------------------
# FILE HASH / CACHE MANAGEMENT
# ----------------------------------------------------

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file to avoid re-indexing unchanged files."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# ----------------------------------------------------
# KNOWLEDGE INDEX & SYNCHRONIZATION
# ----------------------------------------------------

def index_single_document(file_path: Path) -> int:
    """Index an individual document into ChromaDB. Returns count of indexed chunks."""
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return 0

    text = extract_document_text(file_path)
    if not text.strip():
        return 0

    chunks = split_text(text, chunk_size=700, overlap=100)
    if not chunks:
        return 0

    indexed = vector_store.index_document_chunks(file_path.name, chunks)
    print(f"[RAG] Indexed '{file_path.name}': {indexed} chunks.")
    return indexed


def build_knowledge_index() -> List[Dict[str, Any]]:
    """
    Synchronizes the knowledge folder with ChromaDB incrementally.
    Indexes any new or modified files.
    Returns in-memory representation for backward compatibility.
    """
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    all_chunks = []

    # Get existing indexed sources in ChromaDB
    try:
        existing_doc_count = vector_store.doc_col.count()
    except Exception:
        existing_doc_count = 0

    files_in_dir = [
        f for f in KNOWLEDGE_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    # If ChromaDB already has documents and nothing changed, skip re-indexing
    needs_indexing = existing_doc_count == 0

    for file_path in files_in_dir:
        if needs_indexing:
            index_single_document(file_path)

    print(f"[RAG] Total knowledge documents: {len(files_in_dir)}, total indexed chunks in Chroma: {vector_store.doc_col.count()}")

    # Return summary list for backward compatibility with main.py
    return [{"source": f.name} for f in files_in_dir]


# ----------------------------------------------------
# CONTEXT RETRIEVAL
# ----------------------------------------------------

def retrieve_context(
    question: str,
    index: Optional[List[Dict[str, Any]]] = None,
    top_k: int = 4,
    threshold: float = 0.40
) -> List[Dict[str, Any]]:
    """
    Retrieve top relevant knowledge chunks for question answering.
    Uses ChromaDB vector search with cosine similarity scoring.
    """
    try:
        results = vector_store.search_documents(
            query=question,
            top_k=top_k,
            threshold=threshold
        )
        return results
    except Exception as exc:
        print(f"[RAG] Vector retrieval error: {exc}")
        return []
