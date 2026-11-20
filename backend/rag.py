
from pathlib import Path
from pypdf import PdfReader
from docx import Document
from zipfile import BadZipFile

import requests
import math
from pathlib import Path

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

def read_pdf(file_path):

    reader = PdfReader(file_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)
def read_docx(file_path):

    document = Document(file_path)

    paragraphs = []

    for paragraph in document.paragraphs:

        if paragraph.text.strip():
            paragraphs.append(paragraph.text)

    return "\n".join(paragraphs)

def split_text(text, chunk_size=700, overlap=100):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def get_embedding(text):
    response = requests.post(
        OLLAMA_EMBED_URL,
        json={
            "model": EMBED_MODEL,
            "input": text
        },
        timeout=120
    )
    response.raise_for_status()

    return response.json()["embeddings"][0]


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0

    return dot / (norm_a * norm_b)


def build_knowledge_index():

    knowledge_folder = (
        Path(__file__).resolve().parent.parent / "knowledge"
    )

    index = []

    supported_formats = [".txt", ".pdf", ".docx"]

    for file_path in knowledge_folder.iterdir():

        if file_path.suffix.lower() not in supported_formats:
            continue

        print("Reading:", file_path.name)

        if file_path.suffix.lower() == ".txt":

            text = file_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

        elif file_path.suffix.lower() == ".pdf":

            text = read_pdf(file_path)

        elif file_path.suffix.lower() == ".docx":

            try:
                text = read_docx(file_path)

            except (BadZipFile, ValueError, OSError) as error:

                print(
                    f"Skipping invalid DOCX: {file_path.name}"
                )

                print("Reason:", error)

                continue

        chunks = split_text(text)

        for chunk in chunks:

            if not chunk.strip():
                continue

            embedding = get_embedding(chunk)

            index.append({
                "source": file_path.name,
                "text": chunk,
                "embedding": embedding
            })

    print("Total indexed chunks:", len(index))

    return index



def retrieve_context(question, index, top_k=3, threshold=0.45):

    question_embedding = get_embedding(question)

    results = []

    for item in index:

        score = cosine_similarity(
            question_embedding,
            item["embedding"]
        )

        if score >= threshold:

            results.append({
                "source": item["source"],
                "text": item["text"],
                "score": score
            })

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results[:top_k]
