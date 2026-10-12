from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from app.llm import call_model

ROOT = Path(__file__).resolve().parents[1]


class RoutingDecision(BaseModel):
    topics: list[Literal["wifi", "printer", "access", "software"]] = Field(
        max_length=4
    )
    clarification: str = ""


async def route_question(question: str) -> RoutingDecision:
    prompt = (ROOT / "prompts" / "supervisor.md").read_text(
        encoding="utf-8-sig"
    )
    raw = await call_model(prompt, question, json_mode=True)
    decision = RoutingDecision.model_validate_json(raw)
    decision.topics = list(dict.fromkeys(decision.topics))
    return decision
