"""Tests for preflight memory checks that must not modify host processes."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from backend import runner
from backend.memory import GIB, MemoryUnavailable, require_memory


class MemoryPreflightTest(unittest.TestCase):
    def test_allows_stage_when_both_budgets_are_available(self):
        with patch("backend.memory.available_vram_bytes", return_value=(14 * GIB, 16 * GIB)), \
             patch("backend.memory.available_ram_bytes", return_value=22 * GIB):
            require_memory("subject", {})

    def test_blocks_before_model_loading_when_vram_is_busy(self):
        with patch("backend.memory.available_vram_bytes", return_value=(12 * GIB, 16 * GIB)), \
             patch("backend.memory.available_ram_bytes", return_value=22 * GIB):
            with self.assertRaisesRegex(MemoryUnavailable, "12.0 GiB VRAM.*Close other applications"):
                require_memory("subject", {})

    def test_blocks_before_model_loading_when_system_memory_is_busy(self):
        with patch("backend.memory.available_vram_bytes", return_value=(14 * GIB, 16 * GIB)), \
             patch("backend.memory.available_ram_bytes", return_value=19 * GIB):
            with self.assertRaisesRegex(MemoryUnavailable, "19.0 GiB RAM.*Close other applications"):
                require_memory("subject", {})

    def test_cpu_qwen_fallback_needs_ram_but_not_vram(self):
        with patch("backend.memory.available_vram_bytes", side_effect=AssertionError("VRAM must not be read")), \
             patch("backend.memory.available_ram_bytes", return_value=22 * GIB):
            require_memory("subject-cpu", {})

    def test_accepts_explicit_budget_for_supported_hardware(self):
        cfg = {"memoryBudgetsGiB": {"trellis-high": {"vram": 11, "ram": 9}}}
        with patch("backend.memory.available_vram_bytes", return_value=(11 * GIB, 16 * GIB)), \
             patch("backend.memory.available_ram_bytes", return_value=9 * GIB):
            require_memory("trellis", cfg, "high")

    def test_qwen_worker_memory_exit_never_uses_the_fallback(self):
        from tempfile import TemporaryDirectory
        import subprocess

        with TemporaryDirectory() as directory, \
             patch("backend.runner.require_memory"), \
             patch("backend.runner.run", side_effect=subprocess.CalledProcessError(76, ["subject.py"])), \
             patch("backend.runner.compile_image_prompt") as compile_prompt:
            job = Path(directory)
            with self.assertRaisesRegex(MemoryUnavailable, "did not load Qwen"):
                runner.enhance_subject(job, "a fox", None, {"python": "python", "cache": directory}, {})
            compile_prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
