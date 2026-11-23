"""Job queue and runner supervision for the Linux build.

The GUI owns one JobManager. Jobs run one at a time, oldest first, and every
child process is started in its own process group so Cancel can stop the whole
pipeline (FLUX, TRELLIS, Blender, UniRig) at once.
"""
from __future__ import annotations

import os
import queue
import random
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from . import config, intent
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
    process: subprocess.Popen | None = None
    watcher: threading.Thread | None = None
    watcher_stop: threading.Event = field(default_factory=threading.Event)
    anchor: int = 0


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

    # -- public API -----------------------------------------------------
    @property
    def busy(self) -> bool:
        return self._busy

    def enqueue(self, raw: str, source: Path | None, name: str, mode: str, quality: str,
                anchor: int = 0) -> str:
        now = datetime.now()
        stem = intent.clean_name(name).replace(" ", "_")
        if not stem:
            stem = "image" if mode == "image" else "forge"
        job_id = f"{stem}_{now:%Y%m%d_%H%M%S_%f}"
        folder = self.output / job_id
        folder.mkdir(parents=True, exist_ok=True)
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
            asset=folder / (job_id + extension), anchor=anchor,
        )
        with self._lock:
            self._jobs[job.id] = job
        self.jobAdded.emit(job.id, job.name, job.kind, job.raw, anchor)
        self.jobState.emit(job.id, "Queued", job.kind + " · waiting in line")
        self._queue.put(job)
        self._set_busy(True)
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._drain, name="forge-jobs", daemon=True)
            self._worker.start()
        return job.id

    def cancel(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None or job.done or job.cancelled:
            return
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
        self.messageAdded.emit(job.name, "🛑 Cancelled before it started.")

    def shutdown(self) -> None:
        self._stop.set()
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            if not job.done:
                job.cancelled = True
                job.watcher_stop.set()
                if job is self._current:
                    kill_tree(job.process)

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
            if job.cancelled:
                continue
            self._current = job
            job.started = time.monotonic()
            job.stage = "Starting"
            self.jobStage.emit(job.id, job.stage)
            self.jobState.emit(job.id, "Working", job.kind + " · " + job.stage)
            mode, source = job.mode, job.source
            if mode == "model" and source is None:
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
            except _Cancelled:
                job.done = True
                job.watcher_stop.set()
                self.jobState.emit(job.id, "Cancelled", job.kind + " · cancelled")
                self.jobCancelled.emit(job.id)
                self.messageAdded.emit(job.name, "🛑 Cancelled. I cleaned up its unfinished files.")
                self._delete_later(job.folder)
            except Exception as exc:  # noqa: BLE001 - surface the pipeline error in the UI
                job.done = True
                job.watcher_stop.set()
                elapsed = time.monotonic() - job.started
                self.jobState.emit(
                    job.id, "Failed",
                    job.kind + " · stopped" + (" after " + intent.elapsed(elapsed) if elapsed else ""),
                )
                message = str(exc) or "The build stopped."
                self.jobFailed.emit(job.id, message)
                self.messageAdded.emit(job.name, "🙁 " + message + " Press Ctrl + L to see the build log.")
            else:
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
                self._current = None
                job.process = None
        self._set_busy(False)

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
        ]
        if job.source is not None:
            command += ["--input", str(job.source)]
        log_path = job.folder / "pipeline.log"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command, cwd=str(job.folder), env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True,
            )
            job.process = process
            if job.cancelled:
                kill_tree(process)
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.rstrip("\n")
                log.write(line + "\n")
                log.flush()
                self.buildLog.emit(line)
                self._narrate(job, line)
            code = process.wait()
        if job.cancelled:
            raise _Cancelled()
        if code != 0:
            raise RuntimeError("The build stopped.")
        if job.asset is None or not job.asset.is_file():
            raise FileNotFoundError("The build produced no " + (job.asset.suffix.lstrip(".") if job.asset else "output") + " file.")
        if job.mode == "model" or job.mode == "rig":
            if job.mode == "model" and not job.asset.is_file():
                raise FileNotFoundError(job.asset)

    def _narrate(self, job: Job, data: str) -> None:
        if data.startswith("[stage] "):
            stage = data[8:]
            job.stage = stage.replace(" (high quality)", "").replace(" (draft)", "")
            self.jobStage.emit(job.id, job.stage)
            self.jobState.emit(job.id, "Working", job.kind + " · " + job.stage)
            self.jobProgress.emit(job.id, 0.0, True)
            high = "high quality" in stage
            if stage.startswith("Generating image") and job.mode != "image":
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
            elif stage == "Preparing Unity files":
                self.messageAdded.emit(job.name, "📦 Packing the Unity files and sharpening the textures. Almost there!")
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
            ]) + " “" + prompt + "”  Next up: the reference image 🎨")
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
