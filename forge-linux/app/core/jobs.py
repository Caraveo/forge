"""Job queue and runner supervision for the Linux build.

The GUI owns one JobManager. Jobs run one at a time, oldest first, and every
child process is started in its own process group so Cancel can stop the whole
pipeline (FLUX, TRELLIS, Blender, UniRig) at once.
"""
from __future__ import annotations

import fcntl
import json
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from . import config, intent
from backend.checkpoint import atomic_json
from backend.creative import load as load_creative
from .process import kill_tree

STAGE_FLOW = re.compile(r"\]\s+(\d+)/(\d+).*?~([\d.]+)s left")


@dataclass
class Job:
    id: str
    name: str
    raw: str
    source: Path | None
    mode: str
    quality: str
    kind: str
    folder: Path
    asset: Path | None = None
    stage: str = "Starting"
    started: float = 0.0
    cancelled: bool = False
    done: bool = False
    queued: bool = False
    paused: bool = False
    pausing: bool = False
    resumed: bool = False
    shown: set[str] = field(default_factory=set)

    @property
    def persistent(self):
        return self.mode == "model" or (self.mode == "rig" and self.source is not None
                                        and self.source.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))

    @property
    def pause_file(self):
        return self.folder / "generation.pause"

    process: subprocess.Popen | None = None
    watcher: threading.Thread | None = None
    watcher_stop: threading.Event = field(default_factory=threading.Event)
    anchor: int = 0
    original: str = ""


class JobManager(QObject):
    messageAdded = Signal(str, str)          # job name (may be empty), text
    imageAdded = Signal(str, bool)           # path, cutout
    modelAdded = Signal(str, str)            # path, caption
    jobAdded = Signal(str, str, str, str, int)  # id, name, kind, raw, anchor
    jobState = Signal(str, str, str)         # id, state, detail
    jobStage = Signal(str, str)              # id, stage
    jobProgress = Signal(str, float, bool)   # id, percent, indeterminate
    jobDone = Signal(str, str, str, str)     # id, mode, asset, folder
    jobFailed = Signal(str, str)             # id, message
    jobCancelled = Signal(str)               # id
    suggestionAdded = Signal(str, str, str, str, str)
    creativeRestored = Signal(str, dict)
    closeReady = Signal()
    buildLog = Signal(str)
    busyChanged = Signal(bool)
    errorMessage = Signal(str)

    def __init__(self, config_path: Path, cfg: dict, app_dir: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.config_path = Path(config_path)
        self.cfg = cfg
        self.app_dir = Path(app_dir)
        self.output = Path(cfg.get("output") or config.default_output()).expanduser()
        self.output.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[Job] = queue.Queue()
        self._jobs: dict[str, Job] = {}
        self._current: Job | None = None
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._busy = False
        self._saving_close = False
        self._lease = None
        try:
            self._lease = (self.output / ".forge-ui.lock").open("a+b")
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if self._lease is not None:
                self._lease.close()
            self._lease = None


    # -- public API -----------------------------------------------------
    @property
    def busy(self) -> bool:
        return self._busy

    def enqueue(self, raw: str, source: Path | None, name: str, mode: str, quality: str,
                anchor: int = 0, original: str | None = None) -> str:
        if self._saving_close or self._lease is None:
            raise RuntimeError("Use the FORGE window that owns this project queue.")
        now = datetime.now()
        stem = intent.clean_name(name).replace(" ", "_")
        if not stem:
            stem = "image" if mode == "image" else "forge"
        job_id = f"{stem}_{now:%Y%m%d_%H%M%S_%f}"
        folder = self.output / job_id
        folder.mkdir(parents=True, exist_ok=True)
        if original and original != raw:
            atomic_json(folder / "prompt-metadata.json", {"original": original})
        (folder / "prompt.txt").write_text(raw, encoding="utf-8")
        source_copy = None
        if source is not None:
            source = Path(source)
            source_copy = folder / ("input" + source.suffix.lower())
            shutil.copy2(source, source_copy)
        extension = ".png" if mode in ("image", "upscale", "background") else ".fbx" if mode == "rig" else ".glb"
        job = Job(
            id=job_id, name=intent.clean_name(name) or ("Image" if mode == "image" else "Model"),
            raw=raw, source=source_copy, mode=mode, quality=quality,
            kind=intent.kind_label(mode, quality), folder=folder,
            asset=folder / (job_id + extension), anchor=anchor, original=original or raw,
        )
        if job.persistent:
            self._write_request(job, "queued")
        self._register(job)
        self._schedule(job)
        return job.id

    def _write_request(self, job, state):
        atomic_json(job.folder / "generation-request.json", {
            "name": job.name, "mode": job.mode, "quality": job.quality, "state": state,
            "original": job.original,
            "source": job.source.name if job.source else None,
        })

    def recover(self):
        if self._lease is None:
            return
        for request in sorted(self.output.glob("*/generation-request.json"),
                              key=lambda p: p.parent.name.rsplit("_", 3)[-3:]):
            try:
                record = json.loads(request.read_text(encoding="utf-8"))
                if record["state"] in ("done", "cancelled"):
                    continue
                folder = request.parent
                if folder.name in self._jobs:
                    continue
                checkpoint = folder / "generation.json"
                state = json.loads(checkpoint.read_text(encoding="utf-8"))["state"] if checkpoint.exists() else None
                if state == "done":
                    continue
                (folder / "generation.close").unlink(missing_ok=True)
                source = record["source"]
                if source and Path(source).name != source:
                    raise ValueError("Invalid project reference")
                job = Job(folder.name, record["name"], (folder / "prompt.txt").read_text(encoding="utf-8"),
                          folder / source if source else None, record["mode"], record["quality"],
                          intent.kind_label(record["mode"], record["quality"]), folder,
                          folder / (folder.name + (".fbx" if record["mode"] == "rig" else ".glb")))
                if not job.persistent:
                    continue
                job.original = record.get("original") or job.raw
                job.resumed = state is not None
                self._register(job)
                if job.pause_file.exists() or state in ("paused", "failed") or record["state"] == "failed":
                    self._mark_paused(job)
                else:
                    self._schedule(job)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.errorMessage.emit(f"Could not restore {request.parent.name}: {exc}")
        self.restore_creative_context()

    def restore_creative_context(self):
        """Surface saved assistant context without starting Qwen or a generation job."""
        for path in sorted(self.output.glob("*/creative.json")):
            data = load_creative(path.parent)
            if data is not None:
                self.creativeRestored.emit(str(path.parent), data)

    def is_recoverable(self, job_id):
        return self._jobs[job_id].persistent

    def _register(self, job):
        with self._lock:
            self._jobs[job.id] = job
        self.jobAdded.emit(job.id, job.name, job.kind, job.raw, job.anchor)
        self.jobState.emit(job.id, "Queued", job.kind + " · waiting in line")

    def _schedule(self, job):
        if not job.queued:
            job.queued = True
            self._queue.put(job)
        self._set_busy(True)
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._drain, name="forge-jobs", daemon=True)
            self._worker.start()

    def _mark_paused(self, job):
        job.paused = True
        job.pausing = False
        self.jobState.emit(job.id, "Paused", job.kind + " · progress saved")

    def pause(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or not job.persistent or job.done or job.cancelled or job.paused or job.pausing:
                return
            job.pause_file.touch()
            if job is self._current:
                job.pausing = True
                self.jobState.emit(job.id, "Pausing", "Finishing the current stage…")
                self.messageAdded.emit(job.name, "Saving your progress after this stage…")
            else:
                self._mark_paused(job)
                self.messageAdded.emit(job.name, "Your creation is safely paused.")

    def resume(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or not job.paused or job.cancelled or self._saving_close:
                return
            job.pause_file.unlink(missing_ok=True)
            job.paused = False
            job.resumed = True
            self._write_request(job, "queued")
            self.jobState.emit(job.id, "Queued", job.kind + " · waiting in line")
            self._schedule(job)

    def save_and_close(self):
        self._saving_close = True
        self._stop.set()
        with self._lock:
            job = self._current
        if job and job.persistent:
            self.messageAdded.emit(job.name, "Finishing this stage before closing. Your project will resume when you reopen FORGE.")
            # On reopen, the runner starts from its last saved boundary.
            with self._lock:
                if self._current is job and not job.pause_file.exists():
                    job.pausing = True
                    (job.folder / "generation.close").touch()
        elif job:
            self.messageAdded.emit(job.name, "Finishing the current job before closing.")
        if not self._worker or not self._worker.is_alive():
            self.closeReady.emit()

    def cancel(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None or job.done or job.cancelled:
            return
        if job.persistent:
            self._write_request(job, "cancelled")
        job.cancelled = True
        if job is self._current and job.process is not None:
            job.stage = "Cancelling"
            self.jobStage.emit(job.id, job.stage)
            self.jobState.emit(job.id, "Working", job.kind + " · " + job.stage)
            kill_tree(job.process)
            return
        job.done = True
        self.jobState.emit(job.id, "Cancelled", job.kind + " · cancelled")
        self.jobCancelled.emit(job.id)
        self.messageAdded.emit(job.name, "Cancelled." if job.paused else "🛑 Cancelled before it started.")

    def shutdown(self, cancel: bool = False) -> None:
        self._stop.set()
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            if not job.done and not job.cancelled:
                if cancel and not job.paused:
                    self.cancel(job.id)
                job.watcher_stop.set()
                if job is self._current:
                    kill_tree(job.process)
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2)

    # -- worker ---------------------------------------------------------
    def _set_busy(self, value: bool) -> None:
        if self._busy != value:
            self._busy = value
            self.busyChanged.emit(value)

    def _drain(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=0.25)
            except queue.Empty:
                if self._current is None and self._queue.empty():
                    self._set_busy(False)
                continue
            with self._lock:
                if self._stop.is_set():
                    break
                job.queued = False
                if job.cancelled or job.paused or job is self._current or job.done:
                    continue
                self._current = job
            job.started = time.monotonic()
            job.stage = "Starting"
            self.jobStage.emit(job.id, job.stage)
            if not job.pausing:
                self.jobState.emit(job.id, "Working", job.kind + " · " + job.stage)
            mode, source = job.mode, job.source
            if job.resumed:
                self.messageAdded.emit(job.name, "Picking up where you left off…")
            elif mode == "model" and source is None:
                self.messageAdded.emit(job.name, "🚀 Let's make it! First I'll polish your prompt, then paint a reference image.")
            elif mode == "model":
                self.messageAdded.emit(job.name, "🚀 Building a 3D model from your image. First I'll cut out the background.")
            elif mode == "image":
                note = " Then I'll upscale it 4× for extra detail." if job.quality == "high" else ""
                self.messageAdded.emit(job.name, "🎨 Painting it now, one moment!" + note)
            elif mode == "background":
                self.messageAdded.emit(job.name, "✂️ Cutting it out of the background…")
            elif mode == "upscale":
                self.messageAdded.emit(job.name, "🔍 Upscaling it 4×…")
            elif mode == "rig":
                if source is not None and source.suffix.lower() not in (".glb", ".fbx"):
                    self.messageAdded.emit(job.name, "🦴 Let's give it a skeleton! I'll build the 3D model first.")
                else:
                    self.messageAdded.emit(job.name, "🦴 Let's give it a skeleton!")
            try:
                self._run(job)
            except _Paused:
                job.watcher_stop.set()
                with self._lock:
                    if not (job.folder / "generation.close").exists():
                        self._mark_paused(job)
                        self.messageAdded.emit(job.name, "Your creation is safely paused.")
            except _Cancelled:
                job.done = True
                job.watcher_stop.set()
                self.jobState.emit(job.id, "Cancelled", job.kind + " · cancelled")
                self.jobCancelled.emit(job.id)
                if job.persistent:
                    self.messageAdded.emit(job.name, "Cancelled. Your saved progress is still in the project folder.")
                else:
                    self.messageAdded.emit(job.name, "🛑 Cancelled. I cleaned up its unfinished files.")
                    self._delete_later(job.folder)
            except Exception as exc:  # noqa: BLE001 - surface the pipeline error in the UI
                if self._stop.is_set() and not self._saving_close and not job.cancelled:
                    job.watcher_stop.set()
                    continue
                if job.persistent:
                    self._write_request(job, "failed")
                    self._mark_paused(job)
                else:
                    job.done = True
                job.watcher_stop.set()
                elapsed = time.monotonic() - job.started
                self.jobState.emit(
                    job.id, "Paused" if job.persistent else "Failed",
                    job.kind + " · stopped" + (" after " + intent.elapsed(elapsed) if elapsed else ""),
                )
                message = str(exc) or "The build stopped."
                self.jobFailed.emit(job.id, message)
                self.messageAdded.emit(job.name, "🙁 " + message + " Press Ctrl + L to see the build log.")
            else:
                if job.persistent:
                    self._write_request(job, "done")
                job.done = True
                job.watcher_stop.set()
                elapsed = time.monotonic() - job.started
                self.jobState.emit(
                    job.id, "Done",
                    job.kind + " · finished" + (" after " + intent.elapsed(elapsed) if elapsed else ""),
                )
                assert job.asset is not None
                self.jobDone.emit(job.id, job.mode, str(job.asset), str(job.folder))
            finally:
                with self._lock:
                    self._current = None
                    job.process = None
        self._set_busy(False)
        if self._saving_close:
            self.closeReady.emit()

    def _run(self, job: Job) -> None:
        env = dict(os.environ)
        env.update({
            "FORGE_DATA": str(self.cfg.get("cache", config.RUNTIME)),
            "FORGE_FLUX": str(self.cfg.get("flux", "")),
            "HF_HUB_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "PYTHONUNBUFFERED": "1",
            "TOKENIZERS_PARALLELISM": "false",
        })
        python = self.cfg.get("python") or sys.executable
        command = [
            python, "-u", str(self.app_dir / "backend" / "runner.py"),
            "--config", str(self.config_path), "--job", str(job.folder), "--mode", job.mode,
            "--gui-parent", str(os.getpid()),
        ]
        if job.source is not None:
            command += ["--input", str(job.source)]
        log_path = job.folder / "pipeline.log"
        memory_error = None
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                command, cwd=str(job.folder), env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True,
            )
            job.process = process
            if job.cancelled or (self._stop.is_set() and not self._saving_close):
                kill_tree(process)
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.rstrip("\n")
                log.write(line + "\n")
                log.flush()
                self.buildLog.emit(line)
                if line.startswith("[memory-blocked] "):
                    memory_error = line[17:]
                if not job.cancelled:
                    self._narrate(job, line)
            code = process.wait()
        if job.cancelled:
            raise _Cancelled()
        if code == 75:
            raise _Paused()
        if code != 0:
            raise RuntimeError(memory_error or "The build stopped.")
        if job.asset is None or not job.asset.is_file():
            raise FileNotFoundError("The build produced no " + (job.asset.suffix.lstrip(".") if job.asset else "output") + " file.")
        if job.mode == "model" or job.mode == "rig":
            if job.mode == "model" and not job.asset.is_file():
                raise FileNotFoundError(job.asset)

    def _narrate(self, job: Job, data: str) -> None:
        if data.startswith(("[prompt] ", "[suggestion] ", "[show] ")):
            if data in job.shown:
                return
            job.shown.add(data)
        if data.startswith("[memory-blocked] "):
            message = data[17:]
            job.stage = "Waiting for available memory"
            self.jobStage.emit(job.id, job.stage)
            self.jobState.emit(job.id, "Paused", job.kind + " · waiting for available memory")
            self.messageAdded.emit(job.name, "Memory is in use by other applications. " + message)
        elif data.startswith("[memory] "):
            pass
        elif data == "[subject-fallback]":
            self.messageAdded.emit(job.name, "The subject assistant is unavailable. I’ll keep going with your request.")
        elif data.startswith("[suggestion] "):
            try:
                idea = json.loads(data[13:])
                idea_id, text = idea["id"], idea["text"]
            except (ValueError, KeyError, TypeError):
                return
            self.suggestionAdded.emit(job.name, job.raw, idea_id, text, str(job.folder))
        elif data.startswith("[creative-question] "):
            self.messageAdded.emit(job.name, "For a later version, consider this: " + data[20:])
        elif data.startswith("[stage] "):
            stage = data[8:]
            job.stage = stage.replace(" (high quality)", "").replace(" (draft)", "")
            self.jobStage.emit(job.id, job.stage)
            if not job.pausing:
                self.jobState.emit(job.id, "Working", job.kind + " · " + job.stage)
            self.jobProgress.emit(job.id, 0.0, True)
            high = "high quality" in stage
            if stage == "Preparing your subject":
                self.messageAdded.emit(job.name, "Taking a closer look at your subject…")
            elif stage.startswith("Generating image") and job.mode != "image":
                self.messageAdded.emit(job.name, "🎨 " + random.choice([
                    "Painting the reference image", "Sketching the reference image",
                    "Painting a reference for the sculpt",
                ]) + (" in high quality" if high else "") + "…")
            elif stage.startswith("Building textured model (standard retry)"):
                self.messageAdded.emit(job.name, "⚠️ High quality was too heavy for the GPU this time, so I'm finishing at standard quality.")
            elif stage.startswith("Building textured model"):
                self.messageAdded.emit(job.name, "🧱 " + random.choice([
                    "Now sculpting it in 3D", "Time to sculpt it in 3D", "Shaping the 3D model",
                ]) + (" at high quality (1024 geometry, 2K textures)" if high else "") + ". This is the longest step, so hang tight!")
            elif stage.startswith("Upscaling image (high quality)"):
                self.messageAdded.emit(job.name, "🔍 Painted! Now upscaling it 4× for extra detail…")
            elif stage == "Preparing materials and textures":
                self.messageAdded.emit(job.name, "Preparing the materials and textures…")
            elif stage == "Preparing Unity files":
                self.messageAdded.emit(job.name, "📦 Packing the Unity files. Almost there!")
            elif stage == "Preparing model for rigging":
                self.messageAdded.emit(job.name, "🦴 Getting the model ready for rigging…")
            elif stage == "Rigging with UniRig":
                self.messageAdded.emit(job.name, "🦴 UniRig is placing bones and skin weights on the GPU. Next up: your rigged FBX!")
        elif data.startswith("[prompt] "):
            prompt = data[9:]
            if len(prompt) > 260:
                prompt = prompt[:257] + "…"
            self.messageAdded.emit(job.name, "📝 " + random.choice([
                "Here's the prompt I'll use:", "I polished your idea into:", "Here's how I'll describe it:",
            ]) + " “" + prompt + "”")
        elif data.startswith("[show] image "):
            self.messageAdded.emit(job.name, "👀 " + random.choice([
                "Hey, look, here's the reference image!", "Here's the reference image!",
                "Look at this reference!",
            ]) + " Next up: sculpting it in 3D 🧱")
            self.imageAdded.emit(data[13:], False)
        elif data.startswith("[watch] cutout "):
            path = data[15:]
            if job.watcher is None or not job.watcher.is_alive():
                job.watcher_stop.clear()
                job.watcher = threading.Thread(target=self._watch_cutout, args=(job, path), daemon=True)
                job.watcher.start()
        elif data.startswith("[show] model "):
            path = data[13:]
            self.messageAdded.emit(job.name, "✨ " + random.choice([
                "The 3D model is ready, give it a spin!", "Here it is in 3D, drag to spin it!",
                "Sculpted! Drag to spin it.",
            ]) + " Next up: Unity files 📦")
            self.modelAdded.emit(path, intent.caption(path))
        elif "[flow]" in data:
            match = STAGE_FLOW.search(data)
            if match:
                done, count = int(match.group(1)), int(match.group(2))
                job.stage = f"Sculpting · step {done} of {count}"
                self.jobStage.emit(job.id, job.stage)
                if not job.pausing:
                    self.jobState.emit(job.id, "Working", job.kind + " · " + job.stage)
                self.jobProgress.emit(job.id, 100.0 * done / max(1, count), False)

    def _watch_cutout(self, job: Job, path: str) -> None:
        target = Path(path)
        while not job.watcher_stop.is_set() and not job.done:
            try:
                if target.is_file() and target.stat().st_size > 0 and time.time() - target.stat().st_mtime >= 1.0:
                    self.messageAdded.emit(job.name, "✂️ " + random.choice([
                        "Background removed! This cutout is what I'm sculpting from.",
                        "Cut it out of the background. Sculpting from this now.",
                        "Here's the clean cutout I'm sculpting from.",
                    ]))
                    self.imageAdded.emit(str(target), True)
                    return
            except OSError:
                pass
            job.watcher_stop.wait(0.5)

    @staticmethod
    def _delete_later(folder: Path) -> None:
        def remove() -> None:
            for _ in range(10):
                try:
                    shutil.rmtree(folder)
                    return
                except OSError:
                    time.sleep(1)
        threading.Thread(target=remove, daemon=True).start()


class _Cancelled(Exception):
    pass


class _Paused(Exception):
    pass
