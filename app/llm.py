import httpx

OLLAMA_URL = "http://127.0.0.1:11435"
MODEL = "qwen3.5:4b"


async def ask_model(question: str) -> str:
    async with httpx.AsyncClient(timeout=180.0, trust_env=False) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL,
                "stream": False,
                "think": False,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an IT helpdesk assistant. "
                            "Answer in Russian with short, safe troubleshooting steps. "
                            "Never request passwords or suggest bypassing access controls. "
                            "Do not claim you performed actions."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

