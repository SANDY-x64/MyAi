"""
MyAI Vector Database Engine (ChromaDB + Ollama nomic-embed-text)
Provides persistent local vector indexing and semantic retrieval for:
1. Long-term user memories
2. Document knowledge chunks (RAG)
Maintains full synchronization with SQLite and offers zero-downtime fallback.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
import chromadb
from chromadb.config import Settings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two numerical vectors."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_embedding(text: str) -> List[float]:
    """Generate normalized embedding vector via local Ollama nomic-embed-text."""
    response = requests.post(
        OLLAMA_EMBED_URL,
        json={"model": EMBED_MODEL, "input": text},
        timeout=120
    )
    response.raise_for_status()
    return response.json()["embeddings"][0]


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Batch generate normalized embedding vectors via local Ollama."""
    if not texts:
        return []
    response = requests.post(
        OLLAMA_EMBED_URL,
        json={"model": EMBED_MODEL, "input": texts},
        timeout=180
    )
    response.raise_for_status()
    return response.json()["embeddings"]


class MyAIVectorStore:
    """Manages persistent ChromaDB collections for MyAI memories and RAG knowledge."""

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False)
        )

        # Initialize or fetch persistent collections with cosine distance
        self.memory_col = self.client.get_or_create_collection(
            name="myai_memories",
            metadata={"hnsw:space": "cosine"}
        )
        self.doc_col = self.client.get_or_create_collection(
            name="myai_documents",
            metadata={"hnsw:space": "cosine"}
        )

    # ----------------------------------------------------
    # MEMORY VECTOR OPERATIONS
    # ----------------------------------------------------

    def upsert_memory(self, memory_id: int, content: str, category: str = "general") -> bool:
        """Store or update a memory vector in ChromaDB."""
        try:
            emb = get_embedding(content)
            self.memory_col.upsert(
                ids=[str(memory_id)],
                documents=[content],
                embeddings=[emb],
                metadatas=[{"category": category, "memory_id": memory_id}]
            )
            return True
        except Exception as exc:
            print(f"[VectorStore] Failed to upsert memory {memory_id}: {exc}")
            return False

    def search_memories(self, query: str, top_k: int = 5, threshold: float = 0.40) -> List[Dict[str, Any]]:
        """
        Query long-term memories using semantic vector search.
        Chroma cosine distance d in [0, 2], where cosine similarity s = 1 - d.
        """
        try:
            total_items = self.memory_col.count()
            if total_items == 0:
                return []

            q_emb = get_embedding(query)
            results = self.memory_col.query(
                query_embeddings=[q_emb],
                n_results=min(top_k, total_items)
            )

            hits = []
            if results and results.get("ids") and len(results["ids"][0]) > 0:
                ids = results["ids"][0]
                docs = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0]

                for mid, doc, meta, dist in zip(ids, docs, metadatas, distances):
                    similarity = max(0.0, 1.0 - dist)
                    if similarity >= threshold:
                        hits.append({
                            "id": int(mid),
                            "content": doc,
                            "category": meta.get("category", "general"),
                            "score": round(similarity, 3)
                        })

            hits.sort(key=lambda x: x["score"], reverse=True)
            return hits
        except Exception as exc:
            print(f"[VectorStore] Memory search error: {exc}")
            return []

    def delete_memory(self, memory_id: int) -> bool:
        """Remove a memory entry from ChromaDB."""
        try:
            self.memory_col.delete(ids=[str(memory_id)])
            return True
        except Exception as exc:
            print(f"[VectorStore] Failed to delete memory {memory_id}: {exc}")
            return False

    # ----------------------------------------------------
    # DOCUMENT / RAG VECTOR OPERATIONS
    # ----------------------------------------------------

    def index_document_chunks(self, filename: str, chunks: List[str]) -> int:
        """Index all text chunks for a document into ChromaDB."""
        if not chunks:
            return 0
        try:
            # Delete previous chunks for this file if re-indexing
            self.delete_document(filename)

            # Generate batch embeddings
            batch_size = 15
            indexed_count = 0
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]
                batch_ids = [f"{filename}_chunk_{i + idx}" for idx in range(len(batch_chunks))]
                batch_metas = [{"source": filename, "chunk_index": i + idx} for idx in range(len(batch_chunks))]
                batch_embeddings = get_embeddings_batch(batch_chunks)

                self.doc_col.add(
                    ids=batch_ids,
                    documents=batch_chunks,
                    embeddings=batch_embeddings,
                    metadatas=batch_metas
                )
                indexed_count += len(batch_chunks)

            return indexed_count
        except Exception as exc:
            print(f"[VectorStore] Document chunk indexing failed for {filename}: {exc}")
            return 0

    def search_documents(self, query: str, top_k: int = 4, threshold: float = 0.40) -> List[Dict[str, Any]]:
        """
        Query indexed document knowledge chunks.
        Returns source filename, chunk text, and similarity score.
        """
        try:
            total_docs = self.doc_col.count()
            if total_docs == 0:
                return []

            q_emb = get_embedding(query)
            results = self.doc_col.query(
                query_embeddings=[q_emb],
                n_results=min(top_k, total_docs)
            )

            hits = []
            if results and results.get("ids") and len(results["ids"][0]) > 0:
                docs = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0]

                for doc, meta, dist in zip(docs, metadatas, distances):
                    similarity = max(0.0, 1.0 - dist)
                    if similarity >= threshold:
                        hits.append({
                            "source": meta.get("source", "document"),
                            "text": doc,
                            "score": round(similarity, 3)
                        })

            hits.sort(key=lambda x: x["score"], reverse=True)
            return hits
        except Exception as exc:
            print(f"[VectorStore] Document search error: {exc}")
            return []

    def delete_document(self, filename: str) -> bool:
        """Remove all chunks belonging to a specific document."""
        try:
            self.doc_col.delete(where={"source": filename})
            return True
        except Exception as exc:
            print(f"[VectorStore] Failed to delete document {filename}: {exc}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Return total count of indexed memories and document chunks."""
        return {
            "total_memories": self.memory_col.count(),
            "total_document_chunks": self.doc_col.count(),
            "storage_path": str(CHROMA_DIR)
        }


# Global vector store singleton
vector_store = MyAIVectorStore()
