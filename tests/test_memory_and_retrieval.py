import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import memory
from app.knowledge_graph import read_dependencies
from app.rag import cosine


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(
            memory,
            "DB_PATH",
            Path(self.folder.name) / "memory.db",
        )
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.folder.cleanup()

    def test_history_isolated_and_persistent(self):
        memory.save_turn("session-a", "My OS is Windows 11", "Noted")
        self.assertEqual(memory.read_history("session-b"), [])
        history = memory.read_history("session-a")
        self.assertEqual(history[0]["question"], "My OS is Windows 11")
        # Each call opens a new SQLite connection.
        self.assertEqual(memory.read_history("session-a"), history)

    def test_history_keeps_last_four_turns(self):
        for index in range(6):
            memory.save_turn("session-a", f"question-{index}", "answer")
        history = memory.read_history("session-a")
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["question"], "question-2")
        self.assertEqual(history[-1]["question"], "question-5")

    def test_long_term_requires_confirmation_and_user_scope(self):
        with self.assertRaises(ValueError):
            memory.save_confirmed_solution(
                "user-a", "Problem", "Solution", confirmed=False
            )
        self.assertEqual(memory.read_solutions("user-a"), [])

        memory.save_confirmed_solution(
            "user-a", "Problem", "Solution", confirmed=True
        )
        self.assertEqual(memory.read_solutions("user-b"), [])
        self.assertEqual(
            memory.read_solutions("user-a")[0]["solution"],
            "Solution",
        )


class RetrievalAndGraphTests(unittest.TestCase):
    def test_cosine_and_dimension_validation(self):
        self.assertAlmostEqual(cosine([1, 0], [1, 0]), 1)
        self.assertAlmostEqual(cosine([1, 0], [0, 1]), 0)
        with self.assertRaises(ValueError):
            cosine([1, 0], [1])
        with self.assertRaises(ValueError):
            cosine([0, 0], [1, 0])

    def test_dependency_selection(self):
        edges = read_dependencies(["wifi", "printer"])
        pairs = {(edge["source"], edge["target"]) for edge in edges}
        self.assertEqual(
            pairs,
            {("wifi", "network"), ("printer", "network")},
        )


if __name__ == "__main__":
    unittest.main()
