import asyncio
import logging

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.graph import run_agents
from app.memory import read_history, save_turn, read_solutions, save_confirmed_solution

logger = logging.getLogger("uvicorn.error")
lock = asyncio.Lock()

app = FastAPI(
    title="IT HelpDesk Agent",
    description="Multi-agent helpdesk with session memory",
    version="0.4.0",
)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=4000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        async with lock:
            history = read_history(request.session_id)
            solutions = read_solutions("demo")
            result = await run_agents(request.question, history, solutions)

            if not result["topics"]:
                status = "clarification_required"
            elif result.get("review", {}).get("approved") is True:
                status = "review_passed"
            else:
                status = "escalation_required"

            save_turn(
                request.session_id,
                request.question,
                result["answer"],
            )

            return {
                "session_id": request.session_id,
                "history_turns_used": len(history),
                "confirmed_solutions_used": len(solutions),
                "answer": result["answer"],
                "status": status,
                "topics": result["topics"],
                "rag_sources": [
                    {"id": doc["id"], "score": round(doc["score"], 4)}
                    for doc in result.get("documents", [])
                ],
                "rounds": result["round"],
                "review": result.get("review"),
                "debug_findings": result.get("findings", []),
            }
    except httpx.TimeoutException:
        logger.exception("Model request timed out")
        raise HTTPException(504, "Model response timed out")
    except httpx.HTTPError:
        logger.exception("Ollama request failed")
        raise HTTPException(502, "Ollama request failed")
    except ValidationError:
        logger.exception("Invalid structured model output")
        raise HTTPException(502, "Model returned invalid structured output")


class SolutionRequest(BaseModel):
    problem: str = Field(min_length=1, max_length=2000)
    solution: str = Field(min_length=1, max_length=4000)
    confirmed: bool


@app.post("/memory/solutions")
async def confirm_solution(request: SolutionRequest):
    if request.confirmed is not True:
        raise HTTPException(400, "Explicit confirmation is required")
    if not request.problem.strip() or not request.solution.strip():
        raise HTTPException(400, "Fields must not be blank")

    async with lock:
        record_id = save_confirmed_solution(
            "demo",
            request.problem,
            request.solution,
            confirmed=True,
        )
    return {"id": record_id, "saved": True}
