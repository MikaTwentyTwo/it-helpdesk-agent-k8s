import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.llm import ask_model

app = FastAPI(
    title="IT HelpDesk Agent",
    description="Multi-agent IT support system",
    version="0.2.0",
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        answer = await ask_model(request.question)
        return {"answer": answer}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Model response timed out")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Ollama request failed")
