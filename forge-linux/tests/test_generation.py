"""Run with FORGE's runtime Python: python -m unittest discover -s forge-linux/tests."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
from backend import runner, subject
from backend import creative
from backend.checkpoint import Checkpoint, Paused
from core import intent

STAGES = ["subject", "reference", "reconstruction", "materials", "unity"]


def glb_bytes():
    document = b'{"asset":{"version":"2.0"},"meshes":[{}]}'
    document += b" " * (-len(document) % 4)
    return struct.pack("<4sIII4s", b"glTF", 2, 20 + len(document), len(document), b"JSON") + document


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.calls = []
        self.active = None
        self.pause_on = None
        self.fail_on = None
        self.cfg = {key: key for key in ("python", "trellis", "blender", "models", "flux", "upscaler")}
        self.cfg["cache"] = str(self.project)
        self.addCleanup(patch.stopall)
        patch.object(runner, "run", side_effect=self.model_command).start()
        patch.object(runner, "require_memory").start()
        patch.object(runner, "compile_image_prompt", side_effect=lambda prompt, *_: f"COMPILER({prompt})").start()

    def execute(self, source=None):
        checkpoint = Checkpoint(self.project, {"prompt": "forge a toy fox", "seed": 42,
                                               "source": str(source) if source else None})
        runner.process(self.project, "forge a toy fox", "model", self.cfg,
                       source=source, checkpoint=checkpoint)
        checkpoint.save(state="done")

    def model_command(self, command, **_):
        self.assertIsNone(self.active)
        args = list(map(str, command))
        if args[1].endswith("subject.py"):
            self.active = "subject"
            request = json.loads(Path(args[-3]).read_text())
            self.assertEqual(request["subject"], "a toy fox")
            self.assertNotIn("white", request["subject"])
            if request["reference"]:
                self.assertTrue(Path(request["reference"]).is_file())
            Path(args[-1]).write_text(json.dumps({
                "subject": "A red wooden fox",
                "suggestions": ["Try maple.", "Broaden the tail silhouette.", "Use a warm amber accent."],
                "question": "Would you like a more playful or refined version?",
            }))
        elif args[1].endswith("flux_generate.py"):
            self.active = "reference"
            self.assertEqual(args[-1], "COMPILER(A red wooden fox)")
            Image.new("RGB", (8, 8)).save(args[args.index("--out") + 1])
        elif args[0] == "trellis":
            self.active = "reconstruction"
            Path(args[args.index("--output") + 1]).write_bytes(glb_bytes())
        elif args[0] == "blender":
            folder = Path(args[-1])
            self.active = "materials" if folder.name == ".materials" else "unity"
            Path(args[-2]).write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00" + bytes(16))
            if self.active == "materials":
                Image.new("RGB", (8, 8)).save(folder / "fox.png")
        elif args[0] == "upscaler":
            self.assertIsNotNone(self.calls and self.calls[-1])
            shutil.copyfile(args[args.index("-i") + 1], args[args.index("-o") + 1])
            return
        else:
            self.fail(args)
        self.calls.append(self.active)
        if self.active == self.pause_on:
            (self.project / "generation.pause").touch()
        failed = self.active == self.fail_on
        self.active = None
        if failed:
            raise subprocess.CalledProcessError(1, args)

    def test_order_prompt_and_suggestions(self):
        with patch("builtins.print") as log:
            self.execute()
        self.assertEqual(self.calls, STAGES)
        self.assertTrue(any(call.args[0].startswith("[suggestion] {") for call in log.call_args_list))
        record = json.loads((self.project / "generation.json").read_text())
        self.assertEqual(record["inputs"]["prompt"], "forge a toy fox")
        self.assertEqual(record["completed"]["subject"]["value"]["subject"], "A red wooden fox")
        creative_data = creative.load(self.project)
        self.assertEqual(creative_data["ideas"][0]["text"], "Try maple.")
        self.assertEqual(creative_data["question"], "Would you like a more playful or refined version?")
        self.execute()
        self.assertEqual(self.calls, STAGES)

    def test_reference_bypasses_flux(self):
        reference = self.project / "reference.jpg"
        Image.new("RGB", (16, 16)).save(reference)
        self.execute(reference)
        self.assertEqual(self.calls, ["subject", "reconstruction", "materials", "unity"])
        self.assertTrue((self.project / (self.project.name + ".png")).is_file())

    def test_pause_after_each_stage(self):
        for stop in STAGES:
            with self.subTest(stage=stop), tempfile.TemporaryDirectory() as path:
                self.project = Path(path)
                self.calls = []
                self.pause_on = stop
                with self.assertRaises(Paused):
                    self.execute()
                count = STAGES.index(stop) + 1
                self.assertEqual(self.calls, STAGES[:count])
                (self.project / "generation.pause").unlink()
                self.pause_on = None
                self.execute()
                self.assertEqual(self.calls, STAGES)

    def test_interruption_repeats_only_failed_stage(self):
        self.fail_on = "materials"
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute()
        self.fail_on = None
        self.execute()
        self.assertEqual(self.calls, STAGES[:4] + STAGES[3:])

    def test_invalid_artifact_rebuilds_dependent_stages(self):
        self.execute()
        (self.project / (self.project.name + ".glb")).write_bytes(b"corrupt")
        self.execute()
        self.assertEqual(self.calls, STAGES + STAGES[2:])
        (self.project / (self.project.name + ".png")).unlink()
        self.execute()
        self.assertEqual(self.calls, STAGES + STAGES[2:] + STAGES[1:])


class SubjectAndIntentTest(unittest.TestCase):
    def test_model_messages(self):
        image = object()
        system, user = subject.messages("a carved owl", image)
        self.assertEqual(system["role"], "system")
        self.assertNotIn("pure white studio", system["content"][0]["text"])
        self.assertEqual(user["content"], [{"type": "image", "image": image},
                                           {"type": "text", "text": "a carved owl"}])

    def test_embedded_prompt_sources_are_unchanged(self):
        expected = {
            "flux_generate.py": "e910de84c415d8a331915d823e02f0079a897b4fd051849d463a4b66304aece8",
            "prompt_enhancer.py": "7adbf9184358bb9eb7d629bfb402bc4ad27931022e9dc5bef843c2365c1efeb5",
        }
        for filename, digest in expected.items():
            self.assertEqual(hashlib.sha256((APP / "backend" / filename).read_bytes()).hexdigest(), digest)

    def test_idle_draft_eligibility(self):
        for text in ("", "forge", "forge a", "forge a Fox with", "forge it", "forge a fox...",
                     "what can you forge?", "make sure it works", "hello", "generate a fish"):
            with self.subTest(text=text):
                self.assertFalse(intent.idle_model_draft(text))
        self.assertTrue(intent.idle_model_draft("forge a fox"))
        self.assertTrue(intent.idle_model_draft("please build a red fox named Fox"))


class ProcessLockTest(unittest.TestCase):
    def test_gpu_lock_held_until_child_releases_it(self):
        from backend.checkpoint import exclusive
        with tempfile.TemporaryDirectory() as path:
            lock = Path(path) / "gpu.lock"
            with exclusive(lock) as fd:
                child = subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(60)"], pass_fds=(fd,))
            try:
                probe = """
import fcntl, sys
with open(sys.argv[1], 'a+b') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(7)
"""
                self.assertEqual(subprocess.run([sys.executable, "-c", probe, str(lock)]).returncode, 7)
            finally:
                child.kill()
                child.wait()
            self.assertEqual(subprocess.run([sys.executable, "-c", probe, str(lock)]).returncode, 0)

    def test_gui_parent_death_stops_worker_group(self):
        with tempfile.TemporaryDirectory() as path:
            folder = Path(path)
            cfg = folder / "config.json"
            tool = folder / "trellis"
            tool.write_text("#!" + sys.executable + "\nimport os, time\n"
                            "from pathlib import Path\n"
                            "Path(__file__).with_suffix('.pid').write_text(str(os.getpid()))\n"
                            "time.sleep(60)\n")
            tool.chmod(0o755)
            # This test exercises parent-death process cleanup, not the live
            # host preflight. Keep its tiny fake stage independent of desktop
            # VRAM pressure while the production defaults remain protective.
            cfg.write_text(json.dumps({"flux": "", "trellis": str(tool), "models": path,
                                       "memoryBudgetsGiB": {"trellis-standard": {"vram": 0, "ram": 0}}}))
            (folder / "prompt.txt").write_text("remove background")
            (folder / "input.png").touch()
            parent_script = """
import os, subprocess, sys, time
child = subprocess.Popen([sys.executable, *sys.argv[1:], '--gui-parent', str(os.getpid())],
                         start_new_session=True)
print(child.pid, flush=True)
time.sleep(60)
"""
            command = [sys.executable, "-c", parent_script, str(APP / "backend" / "runner.py"),
                       "--config", str(cfg), "--job", path, "--mode", "background",
                       "--input", str(folder / "input.png")]
            with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as parent:
                group = int(parent.stdout.readline())
                try:
                    deadline = time.monotonic() + 5
                    while not tool.with_suffix(".pid").is_file() and time.monotonic() < deadline:
                        time.sleep(0.025)
                    self.assertTrue(tool.with_suffix(".pid").is_file())
                    parent.kill()
                    parent.wait()
                    stage_pid = int(tool.with_suffix(".pid").read_text())
                    while time.monotonic() < deadline:
                        states = []
                        for pid in (group, stage_pid):
                            try:
                                states.append(Path(f"/proc/{pid}/stat").read_text().split(") ")[1][0])
                            except FileNotFoundError:
                                states.append("Z")
                        if states == ["Z", "Z"]:
                            break
                        time.sleep(0.025)
                    self.assertEqual(states, ["Z", "Z"])
                finally:
                    try:
                        os.killpg(group, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    if parent.poll() is None:
                        parent.kill()


if __name__ == "__main__":
    unittest.main()
