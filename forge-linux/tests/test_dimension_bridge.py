"""Dimension's embedded preview stays local and starts in studio mode."""
from pathlib import Path
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.dimension_bridge import DimensionBridge, _FORGE_PAGE


class DimensionBridgeTest(unittest.TestCase):
    def test_preview_page_enables_studio_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text("viewer", encoding="utf-8")
            (root / "viewer.js").write_text("viewer", encoding="utf-8")
            bridge = DimensionBridge(root)
            self.assertTrue(bridge.available)
            self.assertIn("spin:true", _FORGE_PAGE)
            self.assertIn("light:true", _FORGE_PAGE)
            self.assertIn("post:true", _FORGE_PAGE)
            self.assertIn("model", _FORGE_PAGE)


if __name__ == "__main__":
    unittest.main()
