from app.telemetry import observed
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@observed("memory.graph.read")
def read_dependencies(topics: list[str]) -> list[dict]:
    path = ROOT / "knowledge" / "dependencies.json"
    edges = json.loads(path.read_text(encoding="utf-8-sig"))["edges"]
    selected = set(topics)
    return [
        edge for edge in edges
        if edge["source"] in selected or edge["target"] in selected
    ]
