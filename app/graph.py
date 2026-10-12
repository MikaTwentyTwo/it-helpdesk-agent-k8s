import json
import operator
from pathlib import Path
from typing import Annotated, TypedDict

from pydantic import BaseModel, StrictBool
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from app.llm import call_model
from app.supervisor import route_question

ROOT = Path(__file__).resolve().parents[1]


def read_prompt(name: str) -> str:
    return (ROOT / "prompts" / f"{name}.md").read_text(
        encoding="utf-8-sig"
    )


class Review(BaseModel):
    approved: StrictBool
    feedback: str


class AgentState(TypedDict, total=False):
    question: str
    topics: list[str]
    clarification: str
    findings: Annotated[list[dict], operator.add]
    round: int
    review: dict
    answer: str


def current_findings(state: AgentState):
    return [
        item for item in state["findings"]
        if item["round"] == state["round"]
    ]


async def supervisor(state: AgentState):
    decision = await route_question(state["question"])
    return {**decision.model_dump(), "round": 1}


def specialist_tasks(state: AgentState):
    return [
        Send(
            "specialist",
            {
                "question": state["question"],
                "topic": topic,
                "round": state["round"],
                "feedback": state.get("review", {}).get("feedback", ""),
            },
        )
        for topic in state["topics"]
    ]


def dispatch(state: AgentState):
    if not state["topics"]:
        return "clarify"
    return specialist_tasks(state)


async def specialist(state: dict):
    prompt = read_prompt(state["topic"])
    knowledge = (
        ROOT / "knowledge" / f"{state['topic']}.md"
    ).read_text(encoding="utf-8-sig")
    prompt += (
        "\nUse the following curated knowledge as factual reference. "
        "Do not invent unsupported procedures.\n" + knowledge
    )
    payload = json.dumps(
        {
            "question": state["question"],
            "reviewer_feedback": state["feedback"],
        },
        ensure_ascii=False,
    )
    answer = await call_model(prompt, payload)
    return {
        "findings": [
            {
                "topic": state["topic"],
                "round": state["round"],
                "answer": answer,
            }
        ]
    }


async def critic(state: AgentState):
    request = json.loads(state["question"])
    payload = json.dumps(
        {
            "current_question": request["current_question"],
            "confirmed_solutions": request.get("confirmed_solutions", []),
            "user_messages": [
                turn["question"]
                for turn in request["dialogue_history"]
            ],
            "findings": current_findings(state),
        },
        ensure_ascii=False,
    )
    raw = await call_model(
        read_prompt("critic"), payload, json_mode=True
    )
    review = Review.model_validate_json(raw)
    return {"review": review.model_dump()}


def after_review(state: AgentState):
    if state["review"]["approved"]:
        return "synthesizer"
    if state["round"] < 2:
        return "revise"
    return "escalate"


def revise(state: AgentState):
    return {"round": state["round"] + 1}


async def synthesizer(state: AgentState):
    payload = json.dumps(
        {
            "question": state["question"],
            "findings": current_findings(state),
        },
        ensure_ascii=False,
    )
    answer = await call_model(read_prompt("synthesizer"), payload)
    return {"answer": answer}


def escalate(state: AgentState):
    return {
        "answer": (
            "Recommendations did not pass review. "
            "Contact your authorized IT administrator."
        )
    }


def clarify(state: AgentState):
    return {
        "answer": state["clarification"]
        or "Please describe your IT issue in more detail."
    }


builder = StateGraph(AgentState)
builder.add_node("supervisor", supervisor)
builder.add_node("specialist", specialist)
builder.add_node("critic", critic)
builder.add_node("revise", revise)
builder.add_node("synthesizer", synthesizer)
builder.add_node("escalate", escalate)
builder.add_node("clarify", clarify)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges(
    "supervisor", dispatch, ["specialist", "clarify"]
)
builder.add_edge("specialist", "critic")
builder.add_conditional_edges(
    "critic", after_review, ["synthesizer", "revise", "escalate"]
)
builder.add_conditional_edges("revise", specialist_tasks, ["specialist"])

for node in ["synthesizer", "escalate", "clarify"]:
    builder.add_edge(node, END)

graph = builder.compile()


async def run_agents(
    question: str,
    history: list[dict] | None = None,
    solutions: list[dict] | None = None,
):
    contextual_question = json.dumps(
        {
            "current_question": question,
            "dialogue_history": history or [],
            "confirmed_solutions": solutions or [],
        },
        ensure_ascii=False,
    )
    return await graph.ainvoke(
        {"question": contextual_question, "findings": []},
        config={"recursion_limit": 20},
    )
