import os
from app.telemetry import observed, llm_tokens
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11435")
MODEL = "qwen3.5:4b"


@observed("llm.chat")
async def call_model(system: str, question: str, json_mode: bool = False) -> str:
    payload = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
    }
    if json_mode:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=600.0, trust_env=False) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        content = data["message"]["content"]
        llm_tokens.labels("input").inc(data.get("prompt_eval_count", 0))
        llm_tokens.labels("output").inc(data.get("eval_count", 0))
        return content


async def ask_model(question: str) -> str:
    return await call_model(
        system=(
            "You are an IT helpdesk assistant. "
            "Answer in Russian with short, safe troubleshooting steps. "
            "Never request passwords or suggest bypassing access controls. "
            "Do not claim you performed actions."
        ),
        question=question,
    )

