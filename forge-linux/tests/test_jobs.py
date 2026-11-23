import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QSettings

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
from backend.checkpoint import Checkpoint
from core.jobs import JobManager, _Paused
from core.chat_service import ChatService
from main import AppController

QT = QCoreApplication.instance() or QCoreApplication([])


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = {"output": str(self.root)}
        self.manager = self.new_manager()
        self.calls = []

    def new_manager(self):
        manager = JobManager(self.root / "config.json", self.cfg, APP)
        self.addCleanup(self.stop, manager)
        return manager

    @staticmethod
    def stop(manager):
        manager.shutdown()
        if manager._lease and not manager._lease.closed:
            manager._lease.close()

    def wait(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            QT.processEvents()
            time.sleep(0.01)
        self.assertTrue(predicate())

    def test_pause_queued_resume_without_double_run_and_cancel(self):
        entered, proceed = threading.Event(), threading.Event()
        self.addCleanup(proceed.set)

        def run(job):
            self.calls.append(job.name)
            if job.name == "First":
                entered.set()
                self.assertTrue(proceed.wait(2))

        with patch.object(self.manager, "_run", side_effect=run):
            self.manager.enqueue("forge a box", None, "First", "model", "standard")
            self.assertTrue(entered.wait(2))
            queued = self.manager.enqueue("forge a ball", None, "Second", "model", "standard")
            cancelled = self.manager.enqueue("forge a wheel", None, "Third", "model", "standard")
            self.manager.pause(queued)
            self.manager.resume(queued)
            self.manager.resume(queued)
            self.manager.pause(cancelled)
            self.manager.cancel(cancelled)
            proceed.set()
            self.wait(lambda: len(self.calls) == 2 and not self.manager.busy)
            self.assertEqual(self.calls, ["First", "Second"])
            self.assertTrue((self.root / cancelled / "prompt.txt").is_file())
            request = json.loads((self.root / cancelled / "generation-request.json").read_text())
            self.assertEqual(request["state"], "cancelled")

    def test_save_close_and_recover_with_new_manager(self):
        entered = threading.Event()

        def run(job):
            checkpoint = Checkpoint(job.folder, {"prompt": job.raw})
            entered.set()
            deadline = time.monotonic() + 2
            while not (job.folder / "generation.close").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((job.folder / "generation.close").exists())
            checkpoint.save(state="running", current="reference")
            raise _Paused()

        with patch.object(self.manager, "_run", side_effect=run):
            job_id = self.manager.enqueue("forge a box", None, "Saved", "model", "standard")
            self.assertTrue(entered.wait(2))
            self.manager.save_and_close()
            self.wait(lambda: not self.manager.busy)
        self.stop(self.manager)
        recovered = self.new_manager()
        with patch.object(recovered, "_run", side_effect=lambda job: self.calls.append(job.id)):
            recovered.recover()
            recovered.recover()
            self.wait(lambda: not recovered.busy)
        self.assertEqual(self.calls, [job_id])
        self.assertFalse((self.root / job_id / "generation.close").exists())

    def test_manual_pause_stays_paused_after_restart(self):
        manager = self.manager
        manager._stop.set()
        job_id = manager.enqueue("forge a box", None, "Paused", "model", "standard")
        manager.pause(job_id)
        self.stop(manager)
        recovered = self.new_manager()
        with patch.object(recovered, "_run", side_effect=lambda job: self.calls.append(job.id)):
            recovered.recover()
            self.assertTrue(recovered._jobs[job_id].paused)
            self.assertFalse(recovered.busy)
            recovered.resume(job_id)
            self.wait(lambda: not recovered.busy)
        self.assertEqual(self.calls, [job_id])

    def test_chat_waits_for_generation_queue_to_be_idle(self):
        service = ChatService(self.root / "config.json", {"python": sys.executable}, APP)
        self.addCleanup(service.close)
        calls = []
        with patch.object(service, "_ask_worker", side_effect=lambda raw, source: calls.append(raw)):
            service.set_gpu_busy(True)
            service.ask("How could I refine the fox?", None)
            time.sleep(0.05)
            self.assertEqual(calls, [])
            service.set_gpu_busy(False)
            self.wait(lambda: calls == ["How could I refine the fox?"])


if __name__ == "__main__":
    unittest.main()
