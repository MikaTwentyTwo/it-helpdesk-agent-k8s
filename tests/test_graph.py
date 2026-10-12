import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.graph import run_agents
from app.supervisor import RoutingDecision


class FakeModel:
    def __init__(self, approve=True):
        self.approve = approve
        self.active = 0
        self.peak = 0
        self.specialist_calls = 0
        self.critic_calls = 0
        self.synthesizer_calls = 0

    async def call(self, system, question, json_mode=False):
        payload = json.loads(question)

        if json_mode:
            self.critic_calls += 1
            return json.dumps({
                "approved": self.approve,
                "feedback": "" if self.approve else "Revise the answer",
            })

        if "reviewer_feedback" in payload:
            self.specialist_calls += 1
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                await asyncio.sleep(0.02)
                return "Safe diagnostic recommendation"
            finally:
                self.active -= 1

        self.synthesizer_calls += 1
        return "Combined reviewed answer"


def patches(model, topics, clarification=""):
    return (
        patch(
            "app.graph.route_question",
            new=AsyncMock(return_value=RoutingDecision(
                topics=topics,
                clarification=clarification,
            )),
        ),
        patch(
            "app.graph.retrieve",
            new=AsyncMock(return_value=[
                {"id": "wifi.md", "content": "Wi-Fi reference", "score": 0.8},
                {"id": "printer.md", "content": "Printer reference", "score": 0.7},
            ]),
        ),
        patch("app.graph.call_model", new=model.call),
    )


class GraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_specialists_and_join(self):
        model = FakeModel()
        routing, retrieval, llm = patches(model, ["wifi", "printer"])
        with routing, retrieval, llm:
            result = await run_agents("Wi-Fi and printer issue")

        self.assertEqual(model.peak, 2)
        self.assertEqual(model.specialist_calls, 2)
        self.assertEqual(model.critic_calls, 1)
        self.assertEqual(model.synthesizer_calls, 1)
        self.assertEqual(len(result["findings"]), 2)
        self.assertEqual(result["round"], 1)
        self.assertEqual(result["answer"], "Combined reviewed answer")

    async def test_rejection_has_bounded_revision(self):
        model = FakeModel(approve=False)
        routing, retrieval, llm = patches(model, ["wifi", "printer"])
        with routing, retrieval, llm:
            result = await run_agents("Wi-Fi and printer issue")

        self.assertEqual(result["round"], 2)
        self.assertEqual(model.specialist_calls, 4)
        self.assertEqual(model.critic_calls, 2)
        self.assertEqual(model.synthesizer_calls, 0)
        self.assertFalse(result["review"]["approved"])
        self.assertIn("Contact", result["answer"])

    async def test_unclear_question_skips_specialists(self):
        model = FakeModel()
        routing, retrieval, llm = patches(
            model, [], clarification="Please describe your IT issue."
        )
        with routing, retrieval as mock_retrieval, llm:
            result = await run_agents("Unclear question")
            mock_retrieval.assert_not_awaited()

        self.assertEqual(result["topics"], [])
        self.assertEqual(model.specialist_calls, 0)
        self.assertEqual(model.critic_calls, 0)
        self.assertEqual(result["answer"], "Please describe your IT issue.")


if __name__ == "__main__":
    unittest.main()
