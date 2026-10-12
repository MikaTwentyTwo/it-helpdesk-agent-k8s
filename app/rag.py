import hashlib
import json
import math
import sqlite3
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "rag.db"
OLLAMA_URL = "http://127.0.0.1:11435"
EMBED_MODEL = "embeddinggemma"


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            model TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
    """)
    db.commit()
    return db


async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=180.0, trust_env=False) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
        )
        response.raise_for_status()
        vector = response.json()["embeddings"][0]
        if not vector or not all(math.isfinite(x) for x in vector):
            raise ValueError("Invalid embedding")
        return vector


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions differ. Rebuild the index.")
    denominator = (
        math.sqrt(sum(x * x for x in left))
        * math.sqrt(sum(x * x for x in right))
    )
    if denominator == 0:
        raise ValueError("Zero embedding vector")
    return sum(x * y for x, y in zip(left, right)) / denominator


async def index_knowledge() -> int:
    files = sorted((ROOT / "knowledge").glob("*.md"))
    if not files:
        raise ValueError("No knowledge documents found")

    records = []
    for path in files:
        content = path.read_text(encoding="utf-8-sig")
        vector = await embed(content)
        records.append(
            (
                path.name,
                content,
                hashlib.sha256(content.encode("utf-8")).hexdigest(),
                EMBED_MODEL,
                json.dumps(vector),
            )
        )

    db = connect()
    try:
        with db:
            db.execute("DELETE FROM documents")
            db.executemany(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                records,
            )
    finally:
        db.close()
    return len(records)


async def retrieve(question: str, top_k: int = 2) -> list[dict]:
    if top_k < 1:
        raise ValueError("top_k must be positive")

    db = connect()
    try:
        rows = db.execute(
            "SELECT id, content, model, embedding FROM documents"
        ).fetchall()
    finally:
        db.close()

    if not rows:
        raise ValueError("Knowledge index is empty. Run indexing first.")
    if any(row[2] != EMBED_MODEL for row in rows):
        raise ValueError("Embedding model changed. Rebuild the index.")

    query_vector = await embed(question)
    results = [
        {
            "id": document_id,
            "content": content,
            "score": cosine(query_vector, json.loads(vector)),
        }
        for document_id, content, model, vector in rows
    ]
    return sorted(
        results, key=lambda item: item["score"], reverse=True
    )[:top_k]
