import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
import sys
sys.path.insert(0, str(APP))

from backend import creative


class CreativeContextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        creative.initialise(self.project, "forge a fox", "a small wooden fox", {
            "suggestions": ["Make the tail fuller.", "Use maple grain.", "Try a midnight-blue version."],
            "question": "Playful or refined?",
        })

    def test_ideas_are_offered_without_another_qwen_request(self):
        _, first = creative.offer_next(self.project)
        _, second = creative.offer_next(self.project)
        self.assertEqual(first["text"], "Make the tail fuller.")
        self.assertEqual(second["text"], "Use maple grain.")

    def test_selection_rejection_modification_and_revision_persist(self):
        data, first = creative.offer_next(self.project)
        creative.select(self.project, first["id"])
        _, second = creative.offer_next(self.project)
        creative.reject(self.project, second["id"])
        creative.add_modification(self.project, "Make the ears slightly larger")
        data = creative.load(self.project)
        prompt = creative.revision_prompt(data)
        self.assertIn("Make the tail fuller.", prompt)
        self.assertIn("Make the ears slightly larger", prompt)
        self.assertNotIn("Use maple grain.", prompt)
        creative.record_revision(self.project, prompt, "fox-revision-1")
        restored = creative.load(self.project)
        self.assertEqual(restored["revisions"][0]["job_id"], "fox-revision-1")
        self.assertEqual(restored["ideas"][0]["status"], "queued")
        self.assertEqual(restored["revisions"][0]["ideas"], [first["id"]])
        self.assertEqual(restored["ideas"][1]["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
