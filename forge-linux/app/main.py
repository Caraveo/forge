"""FORGE Linux desktop entry point and Qt/QML controller."""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from PySide6.QtCore import Property, QObject, QSettings, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterModule, qmlRegisterType
from PySide6.QtQuick import QQuickWindow

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core import config, intent  # noqa: E402
from core.chat_service import ChatService  # noqa: E402
from core.dimension_bridge import DimensionBridge  # noqa: E402
from core.jobs import JobManager  # noqa: E402
from core.process import open_path  # noqa: E402
from core.resources import ResourceMonitor  # noqa: E402
from backend import creative  # noqa: E402

VERSION = config.VERSION
PICK = random.choice


def is_dark() -> bool:
    override = os.environ.get("FORGE_THEME", "").lower()
    if override in ("dark", "light"):
        return override == "dark"
    try:
        scheme = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip().strip("'")
        if scheme == "prefer-dark":
            return True
        if scheme == "prefer-light":
            return False
        theme = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip().strip("'").lower()
        if theme:
            return "dark" in theme
    except (OSError, subprocess.SubprocessError):
        pass
    return True


def local_path(value: str) -> Path:
    if not value:
        return Path()
    if value.startswith("file:"):
        return Path(QUrl(value).toLocalFile())
    return Path(value).expanduser()


class AppController(QObject):
    appendEntry = Signal(dict)
    updateEntry = Signal(str, dict)
    removeEntry = Signal(str)
    appendJob = Signal(dict)
    updateJob = Signal(str, dict)
    removeJob = Signal(str)
    clearComposer = Signal()
    focusComposer = Signal()
    setupLine = Signal(str)
    setupFinished = Signal(bool, str)
    runtimeReadyChanged = Signal()
    setupRunningChanged = Signal()
    setupLogChanged = Signal()
    attachmentChanged = Signal()
    busyChanged = Signal()
    chatThinkingChanged = Signal()
    buildLogChanged = Signal()
    outputDirChanged = Signal()
    nameSuggestions = Signal(str, list)
    setComposerText = Signal(str)
    closeReady = Signal()
    resourcesChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._cfg: dict | None = None
        self._config_path = config.active_config_path()
        self._dev = config.development_config().is_file()
        self._manager: JobManager | None = None
        self._chat: ChatService | None = None
        self._attachment: Path | None = None
        self._pending_name: dict | None = None
        self._revision_target: Path | None = None
        self._model_keys: dict[str, str] = {}
        self._jobs: dict[str, dict] = {}
        self._build_log: list[str] = []
        self._setup_process: subprocess.Popen | None = None
        self._setup_log: list[str] = []
        self._settings = QSettings()
        self._dimension = DimensionBridge()
        self._resource_monitor = ResourceMonitor()
        self._resources = self._resource_monitor.snapshot()
        self._resource_timer = QTimer(self)
        self._resource_timer.setInterval(2000)
        self._resource_timer.timeout.connect(self._update_resources)
        self._resource_timer.start()
        self._dark = is_dark()
        self._busy = False
        self._thinking = False
        self.askNames = True
        self.lastSubject: str | None = None
        self.setupLine.connect(self._on_setup_line)
        self._load()

    # -- startup --------------------------------------------------------
    def _load(self) -> None:
        self._cfg = config.load_config()
        if self._cfg:
            self._start_services()

    @property
    def runtime_ready(self) -> bool:
        return self._cfg is not None

    def _start_services(self) -> None:
        if self._manager is not None or self._cfg is None:
            return
        self._config_path = config.active_config_path()
        self._manager = JobManager(self._config_path, self._cfg, APP_DIR, self)
        self._manager.messageAdded.connect(self._on_message)
        self._manager.imageAdded.connect(self._on_image)
        self._manager.modelAdded.connect(self._on_model)
        self._manager.jobAdded.connect(self._on_job_added)
        self._manager.jobState.connect(self._on_job_state)
        self._manager.jobStage.connect(self._on_job_stage)
        self._manager.jobProgress.connect(self._on_job_progress)
        self._manager.jobDone.connect(self._on_job_done)
        self._manager.buildLog.connect(self._on_build_log)
        self._manager.busyChanged.connect(self._on_busy)
        self._manager.errorMessage.connect(self._on_error)
        self._manager.suggestionAdded.connect(self._on_suggestion)
        self._manager.creativeRestored.connect(self._on_creative_restored)
        self._manager.closeReady.connect(self.closeReady)
        QTimer.singleShot(0, self._manager.recover)
        self._chat = ChatService(self._config_path, self._cfg, APP_DIR, self)
        self._chat.thinking.connect(self._on_thinking)
        self._chat.queued.connect(self._on_chat_queued)
        self._chat.reply.connect(self._on_chat_reply)
        self._chat.namesSuggested.connect(self._on_names)
        self._chat.error.connect(self._on_chat_error)

    # -- properties -----------------------------------------------------
    def _get_dark(self) -> bool:
        return self._dark

    darkMode = Property(bool, _get_dark, constant=True)

    @Property(bool, notify=runtimeReadyChanged)
    def runtimeReady(self) -> bool:
        return self.runtime_ready

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=chatThinkingChanged)
    def chatThinking(self) -> bool:
        return self._thinking

    @Property(bool, notify=setupRunningChanged)
    def setupRunning(self) -> bool:
        return self._setup_process is not None and self._setup_process.poll() is None

    @Property(str, notify=setupLogChanged)
    def setupLogText(self) -> str:
        return "\n".join(self._setup_log[-4000:])

    @Property(str, notify=buildLogChanged)
    def buildLogText(self) -> str:
        return "\n".join(self._build_log[-4000:])

    @Property(str, notify=attachmentChanged)
    def attachmentPath(self) -> str:
        return str(self._attachment) if self._attachment else ""

    @Property(str, notify=attachmentChanged)
    def attachmentName(self) -> str:
        return self._attachment.name if self._attachment else ""

    @Property(str, notify=attachmentChanged)
    def attachmentUrl(self) -> str:
        return QUrl.fromLocalFile(str(self._attachment)).toString() if self._attachment else ""

    @Property(str, notify=attachmentChanged)
    def attachmentKind(self) -> str:
        if not self._attachment:
            return ""
        return "3D model" if self._attachment.suffix.lower() in (".glb", ".fbx") else "Image"

    @Property(str, notify=attachmentChanged)
    def attachmentTag(self) -> str:
        if not self._attachment:
            return ""
        ext = self._attachment.suffix.lower()
        return "3D" if ext in (".glb", ".fbx") else ext.lstrip(".").upper()

    @Property(list, notify=attachmentChanged)
    def attachmentActions(self) -> list:
        if not self._attachment:
            return []
        ext = self._attachment.suffix.lower()
        if ext == ".glb":
            return [
                {"label": "👀 Preview", "command": "preview", "arg": str(self._attachment)},
                {"label": "🦴 Rig", "command": "rig", "arg": str(self._attachment)},
            ]
        if ext == ".fbx":
            return [{"label": "🦴 Rig", "command": "rig", "arg": str(self._attachment)}]
        return [
            {"label": "🧱 Build 3D", "command": "submit", "arg": "forge"},
            {"label": "✂️ Remove background", "command": "submit", "arg": "remove background"},
            {"label": "🔍 Upscale", "command": "submit", "arg": "upscale"},
        ]

    @Property(str, notify=outputDirChanged)
    def outputDir(self) -> str:
        return str(self._manager.output) if self._manager else str(config.default_output())

    @Property(str, constant=True)
    def version(self) -> str:
        return VERSION

    @Property(str, constant=True)
    def setupCommand(self) -> str:
        return str(APP_DIR.parents[1] / "install.sh")

    # -- attachment -----------------------------------------------------
    @Slot(str)
    def acceptFile(self, value: str) -> None:
        path = local_path(value)
        if not path.is_file():
            return
        ext = path.suffix.lower()
        if ext == ".txt":
            try:
                if path.stat().st_size > 65536:
                    self._say("📄 That text file is too large to use as a prompt (64 KB at most).")
                    return
                text = path.read_text(encoding="utf-8", errors="replace")
                text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                if not text:
                    self._say("📄 That text file is empty.")
                    return
                self.clearComposer.emit()
                self._set_composer(text[:2000].rstrip())
                self.focusComposer.emit()
            except OSError as exc:
                self._say("📄 Could not read that text file. " + str(exc))
            return
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".glb", ".fbx"):
            label = ext.upper().lstrip(".") + " files" if ext else "that file"
            self._say("🚫 FORGE can't work with " + label + ". Attach an image (PNG, JPEG, WebP), "
                      "a 3D model (GLB, FBX) or a text prompt (TXT).")
            return
        self.setAttachment(str(path))
        self.focusComposer.emit()

    def _set_composer(self, text: str) -> None:
        self.setComposerText.emit(text)

    @Slot(str)
    def setAttachment(self, value: str) -> None:
        path = local_path(value) if value else None
        self._attachment = path if path and path.is_file() else None
        self.attachmentChanged.emit()

    @Slot()
    def clearAttachment(self) -> None:
        self._attachment = None
        self.attachmentChanged.emit()

    @Slot(str, result=str)
    def fileName(self, value: str) -> str:
        return local_path(value).name

    @Slot(str, result=str)
    def localPath(self, value: str) -> str:
        return str(local_path(value))

    @Slot(str)
    def saveAsset(self, source: str, target: str) -> None:
        source_path = local_path(source)
        target_path = local_path(target)
        try:
            if source_path.resolve() != target_path.resolve():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
        except OSError as exc:
            self._say("Could not save. " + str(exc))

    @Slot(str)
    def openPath(self, value: str) -> None:
        try:
            open_path(local_path(value))
        except Exception as exc:  # noqa: BLE001 - shown as a chat line
            self._say("Could not open that file. " + str(exc))

    @Slot(str)
    def saveFile(self, value: str) -> None:
        # The QML result card already knows a good destination; this is the
        # generic action for ActionButtons outside the save dialog path.
        self.saveAsset(value, value)

    # -- conversation ---------------------------------------------------
    def _say(self, text: str, job: str = "") -> None:
        self.appendEntry.emit({"kind": "text", "text": text, "jobName": job,
                               "key": "say:" + uuid.uuid4().hex})

    def _on_message(self, job: str, text: str) -> None:
        self._say(text, job)

    def _on_image(self, path: str, cutout: bool) -> None:
        self.appendEntry.emit({"kind": "image", "path": path, "url": self.urlFor(path),
                               "cutout": cutout, "key": "image:" + uuid.uuid4().hex})

    def _on_model(self, path: str, caption: str) -> None:
        job_id = Path(path).parent.name
        key = "model:" + job_id
        self._model_keys[job_id] = key
        self.appendEntry.emit({"kind": "model", "key": key, "path": path, "url": self.urlFor(path),
                               "caption": caption, "folder": ""})

    @Slot(str)
    def preview(self, path: str) -> None:
        key = "preview:" + uuid.uuid4().hex
        self.appendEntry.emit({"kind": "model", "key": key, "path": path, "url": self.urlFor(path),
                               "caption": intent.caption(path), "folder": ""})

    @Slot(str, result=str)
    def urlFor(self, value: str) -> str:
        return QUrl.fromLocalFile(str(local_path(value))).toString()

    @Slot(str, result=str)
    def dimensionUrl(self, value: str) -> str:
        """Return a private, local Dimension preview URL when it is installed."""
        return self._dimension.preview_url(local_path(value))

    @Property(dict, notify=resourcesChanged)
    def resources(self) -> dict:
        return self._resources

    def _update_resources(self) -> None:
        self._resources = self._resource_monitor.snapshot()
        self.resourcesChanged.emit()

    @Slot(str)
    def openDimension(self, value: str) -> None:
        """Open the complete local Dimension studio for the selected model."""
        if self._busy:
            self._say("Dimension Studio will be ready after this generation finishes, so GPU model work stays exclusive.")
            return
        path = local_path(value)
        if not path.is_file():
            self._say("That model is no longer available to preview.")
            return
        try:
            subprocess.Popen(["dimension", str(path)], start_new_session=True)
        except OSError:
            self._say("Dimension is not installed. The built-in interactive preview is still available.")

    @Slot(str)
    def submit(self, raw):
        self._submit(raw)

    def _submit(self, raw: str, automatic=False) -> None:
        raw = (raw or "").strip()
        if not raw:
            return
        if self._manager is None or self._cfg is None:
            self._say("Finish runtime setup and reopen FORGE to build.")
            return
        if self._revision_target is not None:
            project = self._revision_target
            self._revision_target = None
            try:
                creative.add_modification(project, raw)
            except ValueError as exc:
                self._say(str(exc))
                return
            self.clearComposer.emit()
            self.appendEntry.emit({"kind": "user", "text": raw, "key": "user:" + uuid.uuid4().hex})
            self._say("I saved that change for the next revision.")
            self._revision_actions(project)
            return
        original = raw
        mode = intent.mode(raw)
        subject = intent.subject(raw)
        if mode == "chat" and subject is not None:
            self.lastSubject = subject
        if (self._attachment is None and self.lastSubject is not None
                and mode in ("model", "image")
                and re.search(r"\b(it|that|this)\s*[.!?]*$", raw, re.I)):
            raw = ("forge " if mode == "model" else "generate ") + self.lastSubject
        if (mode in ("model", "image") and self._attachment is None
                and re.match(r"^(forge|build|make|mold|generate|create|imagine|image)\s*[.!?]*$", raw, re.I)):
            self._say("What would you like me to create?")
            return
        if mode in ("rig", "background", "upscale") and self._attachment is None:
            self._say("Attach or select a file for this action.")
            return
        if (self._attachment is not None and mode not in ("rig", "chat")
                and self._attachment.suffix.lower() in (".fbx", ".glb")):
            self._say("Select an image for this action, or use rig for the selected model.")
            return
        if self._attachment is not None and mode == "image":
            self._say("To use the attached image, choose forge or upscale. Clear it to generate a new image.")
            return
        if mode == "chat" and not self._cfg.get("chat"):
            self._say("Chat is still installing. Reopen FORGE to finish setup, or start with forge or generate.")
            return
        if mode == "rig" and not self._cfg.get("unirig"):
            self._say("Rigging is still installing. Reopen FORGE to finish setup.")
            return

        source = self._attachment
        self.clearComposer.emit()
        if mode != "chat":
            self.setAttachment("")
        self.appendEntry.emit({"kind": "user", "text": raw, "key": "user:" + uuid.uuid4().hex})
        rigs_image = (mode == "rig" and source is not None
                      and source.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
        quality = intent.quality(raw)
        if mode in ("model", "image") or rigs_image:
            if quality == "high":
                self.appendEntry.emit({
                    "kind": "note", "key": "note:" + uuid.uuid4().hex,
                    "text": ("High quality: painted, then upscaled 4× to 3072 px. Takes a little longer."
                             if mode == "image" else
                             "High quality: 1024 geometry, 2048 px texture atlas, 4K Unity textures. "
                             "Takes longer; falls back to standard if your GPU runs short."),
                })
            elif quality == "draft":
                self.appendEntry.emit({"kind": "note", "key": "note:" + uuid.uuid4().hex,
                                       "text": "Draft quality: faster, rougher geometry and 1K textures."})
        if mode == "chat":
            self._run_chat(raw, source)
            return
        named = re.search(r"\b(?:named|called)\s+([A-Za-z0-9_-]{1,48})", raw, re.I)
        name = named.group(1) if named else None
        if name is None and source is not None and mode in ("rig", "upscale", "background"):
            suffix = "Rigged" if mode == "rig" else "Upscaled" if mode == "upscale" else "Cutout"
            name = intent.caption(source) + " " + suffix
        if name is None and mode in ("model", "image"):
            if self.askNames and not automatic:
                self._ask_name(raw, source, mode, quality, original)
                return
            name = intent.fallback_names(raw)[0]
        self._enqueue(raw, source, name, mode, quality, original)

    def _enqueue(self, raw: str, source: Path | None, name: str | None,
                 mode: str, quality: str, original: str) -> str | None:
        assert self._manager is not None
        try:
            return self._manager.enqueue(raw, source, name or "", mode, quality, original=original)
        except (OSError, RuntimeError) as exc:
            self._say(str(exc))
            return None

    def _ask_name(self, raw: str, source: Path | None, mode: str, quality: str, original: str) -> None:
        key = "name:" + uuid.uuid4().hex
        suggestions = intent.fallback_names(raw)[:3]
        if source is not None:
            caption = intent.clean_name(intent.caption(source))
            if caption:
                suggestions = [caption] + [n for n in suggestions if n.lower() != caption.lower()]
        self._pending_name = {"key": key, "raw": raw, "source": source,
                              "mode": mode, "quality": quality, "original": original, "suggestions": suggestions}
        self.appendEntry.emit({
            "kind": "name", "key": key, "title": "Name this project",
            "hint": "Pick a suggestion or type your own. Your files are saved under this name.",
            "suggestions": suggestions, "done": False,
        })
        if self._chat is not None and self._cfg and self._cfg.get("chat"):
            self._chat.suggest(raw)

    @Slot(str)
    def chooseName(self, name: str) -> None:
        if self._pending_name is None:
            return
        cleaned = intent.clean_name(name)
        if not cleaned:
            self.focusComposer.emit()
            return
        pending = self._pending_name
        self._pending_name = None
        self.removeEntry.emit(pending["key"])
        self._enqueue(pending["raw"], pending["source"], cleaned, pending["mode"], pending["quality"], pending["original"])
        self.focusComposer.emit()

    @Slot(list)
    def _on_names(self, names: list) -> None:
        if self._pending_name is None:
            return
        pending = self._pending_name
        for name in names:
            cleaned = intent.clean_name(name)
            if cleaned and all(cleaned.lower() != existing.lower() for existing in pending["suggestions"]):
                pending["suggestions"].append(cleaned)
        self.updateEntry.emit(pending["key"], {"suggestions": list(pending["suggestions"][:8])})

    def _run_chat(self, raw: str, source: Path | None) -> None:
        if self._chat is None:
            self._say("Chat is still installing.")
            return
        self.appendEntry.emit({"kind": "thinking", "key": "thinking", "text": "💭 Thinking…"})
        self._chat.ask(raw, source)

    def _on_thinking(self, value: bool) -> None:
        self._thinking = value
        self.chatThinkingChanged.emit()

    def _on_chat_queued(self) -> None:
        self._say("I’ll answer when your current creation has finished its model work.")

    def _on_chat_reply(self, text: str, subject: str) -> None:
        self.removeEntry.emit("thinking")
        self._thinking = False
        self.chatThinkingChanged.emit()
        self._say(text)
        if subject:
            label = subject if len(subject) <= 28 else subject[:27].rstrip() + "…"
            self.appendEntry.emit({
                "kind": "choices", "key": "choices:" + uuid.uuid4().hex,
                "buttons": [
                    {"label": "🎨 Image of “" + label + "”", "command": "submit", "arg": "generate " + subject},
                    {"label": "🧱 3D model of “" + label + "”", "command": "submit", "arg": "forge " + subject},
                ],
            })

    def _on_chat_error(self, message: str) -> None:
        self.removeEntry.emit("thinking")
        self._thinking = False
        self.chatThinkingChanged.emit()
        self._say("🙁 Chat stopped: " + message)

    def _on_suggestion(self, name, raw, idea_id, suggestion, folder):
        self._idea_card(Path(folder), name, idea_id, suggestion)

    def _idea_card(self, project: Path, name: str, idea_id: str, suggestion: str) -> None:
        payload = json.dumps({"project": str(project), "idea": idea_id})
        self.appendEntry.emit({
            "kind": "actions", "key": "idea:" + uuid.uuid4().hex,
            "title": f"Here’s an idea for a later version of {name}: {suggestion}",
            "buttons": [
                {"label": "Use this idea", "command": "creativeSelect", "arg": payload},
                {"label": "No thanks", "command": "creativeReject", "arg": payload},
                {"label": "More ideas", "command": "creativeMore", "arg": str(project)},
                {"label": "Refine it myself", "command": "creativeRefine", "arg": str(project)},
            ],
        })

    def _revision_actions(self, project: Path) -> None:
        self.appendEntry.emit({
            "kind": "actions", "key": "revision:" + uuid.uuid4().hex,
            "title": "Your changes are saved. When you’re ready, I can create a revised version.",
            "buttons": [
                {"label": "Create revised version", "command": "creativeRevision", "arg": str(project)},
                {"label": "Keep exploring", "command": "creativeMore", "arg": str(project)},
            ],
        })

    def _on_creative_restored(self, folder: str, data: dict) -> None:
        project = Path(folder)
        name = intent.clean_name(project.name.rsplit("_", 3)[0]) or "this project"
        self.appendEntry.emit({
            "kind": "actions", "key": "creative-restore:" + project.name,
            "title": f"Welcome back. {name} has saved creative ideas and revision notes.",
            "buttons": [
                {"label": "Review ideas", "command": "creativeReview", "arg": str(project)},
                {"label": "Refine this design", "command": "creativeRefine", "arg": str(project)},
                {"label": "Create revised version", "command": "creativeRevision", "arg": str(project)},
            ],
        })

    # -- jobs -----------------------------------------------------------
    def _on_job_added(self, job_id: str, name: str, kind: str, raw: str, anchor: int) -> None:
        entry = {"id": job_id, "name": name, "kind": kind, "raw": raw,
                 "state": "Queued", "detail": kind + " · waiting in line",
                 "progress": 0.0, "indeterminate": False, "done": False,
                 "working": False, "failed": False, "cancelled": False,
                 "recoverable": self._manager.is_recoverable(job_id)}
        self._jobs[job_id] = entry
        self.appendJob.emit(entry)

    def _on_job_state(self, job_id: str, state: str, detail: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.update({"state": state, "detail": detail,
                    "working": state == "Working",
                    "done": state in ("Done", "Failed", "Cancelled"),
                    "failed": state == "Failed", "cancelled": state == "Cancelled"})
        self.updateJob.emit(job_id, dict(job))

    def _on_job_stage(self, job_id: str, stage: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        if stage == "Starting":
            self._build_log.clear()
            self.buildLogChanged.emit()
        job["stage"] = stage
        self.updateJob.emit(job_id, {"stage": stage, "detail": job["detail"]})

    def _on_job_progress(self, job_id: str, percent: float, indeterminate: bool) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.update({"progress": percent, "indeterminate": indeterminate})
        self.updateJob.emit(job_id, {"progress": percent, "indeterminate": indeterminate})

    def _on_job_done(self, job_id: str, mode: str, asset: str, folder: str) -> None:
        job = self._jobs.get(job_id, {})
        if mode == "model":
            self._say("🎉 " + PICK(["All done!", "Finished!", "It's ready!"]) +
                      " Rig it, save it, or expand it for a closer look.")
            key = self._model_keys.get(job_id)
            if key:
                self.updateEntry.emit(key, {"folder": folder})
            else:
                self.appendEntry.emit({"kind": "model", "key": "model:" + job_id,
                                       "path": asset, "url": self.urlFor(asset),
                                       "caption": intent.caption(asset), "folder": folder})
        elif mode in ("image", "upscale", "background"):
            self._say("🎉 " + PICK(["Here it is!", "All done, here it is!", "Ta-da!"]))
            self.appendEntry.emit({
                "kind": "imageResult", "key": "result:" + job_id, "path": asset,
                "url": self.urlFor(asset), "caption": intent.caption(asset), "folder": folder,
                "buttons": [
                    {"label": "Save image", "command": "saveFile", "arg": asset},
                    {"label": "Select image", "command": "select", "arg": asset},
                    {"label": "📁 Open folder", "command": "open", "arg": folder},
                ],
            })
        elif mode == "rig":
            self._say("🎉 " + PICK(["It's rigged!", "Bones in place, it's rigged!"]) +
                      " Save the FBX and drop it into Unity.")
            self.appendEntry.emit({
                "kind": "actions", "key": "rig-result:" + job_id,
                "title": "Save the FBX and drop it into Unity.",
                "buttons": [
                    {"label": "Save rigged FBX", "command": "saveFile", "arg": asset},
                    {"label": "📁 Open folder", "command": "open", "arg": folder},
                ],
            })

    def _on_build_log(self, line: str) -> None:
        self._build_log.append(line)
        if len(self._build_log) > 4000:
            del self._build_log[:1000]
        self.buildLogChanged.emit()

    def _on_busy(self, value: bool) -> None:
        self._busy = value
        self.busyChanged.emit()
        if self._chat is not None:
            self._chat.set_gpu_busy(value)

    def _on_error(self, message: str) -> None:
        self._say("🙁 " + message)

    @Slot(str)
    def pauseJob(self, job_id):
        if self._manager:
            self._manager.pause(job_id)

    @Slot(str)
    def resumeJob(self, job_id):
        if self._manager:
            self._manager.resume(job_id)

    @Slot()
    def saveAndClose(self):
        if self._manager:
            self._manager.save_and_close()
        else:
            self.closeReady.emit()

    @Slot()
    def cancelAndClose(self):
        if self._manager:
            self._manager.shutdown(cancel=True)

    @Slot(str)
    def cancelJob(self, job_id: str) -> None:
        if self._manager is not None:
            self._manager.cancel(job_id)

    @Slot(str)
    def dismissJob(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)
        self.removeJob.emit(job_id)

    def _project_is_active(self, project: Path) -> bool:
        job = self._jobs.get(project.name, {})
        return job.get("state") in ("Queued", "Working", "Pausing")

    @staticmethod
    def _project_source(project: Path) -> Path | None:
        return next((path for path in project.glob("input.*")
                     if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")), None)

    def _review_creative_context(self, project: Path) -> None:
        data = creative.load(project)
        if data is None:
            self._say("I couldn’t find the saved ideas for that project.")
            return
        ideas = [idea for idea in data.get("ideas", []) if idea.get("status") in ("available", "offered")]
        if not ideas:
            self._say("You’ve reviewed all of the saved ideas. You can still describe your own change.")
            self._revision_actions(project)
            return
        for idea in ideas:
            self._idea_card(project, intent.clean_name(project.name.rsplit("_", 3)[0]), idea["id"], idea["text"])

    def _create_revision(self, project: Path) -> None:
        data = creative.load(project)
        if data is None:
            self._say("I couldn’t find the saved ideas for that project.")
            return
        prompt = creative.revision_prompt(data)
        if prompt == data.get("original_prompt", ""):
            self._say("Choose an idea or describe a change first, then I can create a revised version.")
            return
        title = intent.clean_name(project.name.rsplit("_", 3)[0]) or "Design"
        number = len(data.get("revisions", [])) + 1
        name = f"{title} revision {number}"
        source = self._project_source(project)
        self.appendEntry.emit({"kind": "user", "text": "Create a revised version: " + prompt,
                               "key": "user:" + uuid.uuid4().hex})
        job_id = self._enqueue(prompt, source, name, "model", intent.quality(prompt), prompt)
        if job_id:
            creative.record_revision(project, prompt, job_id)
            self._say("Your revised version is in the queue. Your original creation stays exactly as it was.")

    @Slot(str, str)
    def handleAction(self, command: str, arg: str) -> None:
        if command == "submit":
            self.submit(arg)
        elif command == "subjectDraft":
            draft, source = json.loads(arg)
            self.setAttachment(source)
            self.setComposerText.emit(draft)
            self.focusComposer.emit()
        elif command == "creativeSelect":
            payload = json.loads(arg)
            project = Path(payload["project"])
            try:
                creative.select(project, payload["idea"])
            except (ValueError, OSError) as exc:
                self._say(str(exc))
                return
            self._create_revision(project)
        elif command == "creativeReject":
            payload = json.loads(arg)
            try:
                creative.reject(Path(payload["project"]), payload["idea"])
            except (ValueError, OSError) as exc:
                self._say(str(exc))
                return
            self._say("Got it. I’ll leave that idea out of future revisions.")
        elif command == "creativeMore":
            project = Path(arg)
            try:
                data, idea = creative.offer_next(project)
            except (ValueError, OSError) as exc:
                self._say(str(exc))
                return
            if idea is None:
                self._say("Those are all the saved ideas for now. Tell me what you’d like to change, and I’ll save it.")
                self._revision_actions(project)
            else:
                self._idea_card(project, intent.clean_name(project.name.rsplit("_", 3)[0]), idea["id"], idea["text"])
        elif command == "creativeReview":
            self._review_creative_context(Path(arg))
        elif command == "creativeRefine":
            project = Path(arg)
            if creative.load(project) is None:
                self._say("I couldn’t find the saved ideas for that project.")
                return
            self._revision_target = project
            self.clearComposer.emit()
            self.focusComposer.emit()
            self._say("Tell me what you’d change. I’ll save it for the next version while your current creation keeps going.")
        elif command == "creativeRevision":
            self._create_revision(Path(arg))
        elif command == "open":
            self.openPath(arg)
        elif command == "select":
            self.setAttachment(arg)
            self.focusComposer.emit()
        elif command == "rig":
            self.setAttachment(arg)
            self.submit("rig it")
        elif command == "preview":
            self.preview(arg)
        elif command == "saveFile":
            self.saveFile(arg)
        elif command == "save":
            # The QML result card opens a save dialog when it needs a destination.
            self.saveAsset(arg, arg)

    # -- setup ----------------------------------------------------------
    @Slot()
    def runSetup(self) -> None:
        if self.setupRunning:
            return
        self._setup_log = ["Starting FORGE runtime setup…"]
        self.setupLogChanged.emit()
        self.setupRunningChanged.emit()
        command = [sys.executable, str(APP_DIR / "backend" / "setup_runtime.py"),
                   "--runtime", str(config.RUNTIME)]
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, start_new_session=True,
            )
        except OSError as exc:
            self._setup_log.append("Could not start setup: " + str(exc))
            self.setupLogChanged.emit()
            self.setupFinished.emit(False, str(exc))
            return
        self._setup_process = process
        threading.Thread(target=self._read_setup, args=(process,), daemon=True).start()

    def _read_setup(self, process: subprocess.Popen) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.setupLine.emit(line.rstrip("\n"))
        code = process.wait()
        self._setup_process = None
        if code == 0:
            self._load()
            if self._cfg:
                self._start_services()
                self.runtimeReadyChanged.emit()
            self.setupFinished.emit(True, "FORGE is ready.")
        else:
            self.setupFinished.emit(False, "Setup stopped. See the log above.")
        self.setupRunningChanged.emit()

    @Slot(str)
    def _on_setup_line(self, line: str) -> None:
        self._setup_log.append(line)
        if len(self._setup_log) > 4000:
            del self._setup_log[:1000]
        self.setupLogChanged.emit()

    # -- lifecycle ------------------------------------------------------
    @Slot()
    def shutdown(self) -> None:
        if self._manager is not None:
            self._manager.shutdown()
        if self._chat is not None:
            self._chat.close()
        self._dimension.close()
        if self._setup_process is not None and self._setup_process.poll() is None:
            try:
                os.killpg(os.getpgid(self._setup_process.pid), 15)
            except (ProcessLookupError, PermissionError):
                pass


def hardware_check() -> int:
    try:
        from backend.setup_runtime import hardware_report
        hardware_report()
    except Exception as exc:  # noqa: BLE001
        print("Could not inspect hardware:", exc)
    ok = Path("/dev/kfd").exists()
    if not ok:
        print("ROCm is unavailable: /dev/kfd is missing.")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="forge", add_help=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--remove-runtime", action="store_true")
    parser.add_argument("--preserve-runtime", action="store_true")
    parser.add_argument("--restore-runtime", action="store_true")
    parser.add_argument("--preview", nargs="+", metavar="FILE")
    parser.add_argument("--build", nargs="+", metavar="TEXT")
    parser.add_argument("--screenshot", metavar="PNG")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.check:
        return hardware_check()
    if args.remove_runtime:
        print("Runtime removed." if config.remove_runtime() else "No FORGE-owned runtime to remove.")
        return 0
    if args.preserve_runtime:
        config.preserve_runtime()
        return 0
    if args.restore_runtime:
        config.restore_runtime()
        return 0
    config.restore_runtime()

    QGuiApplication.setDesktopFileName("forge")
    app = QGuiApplication(sys.argv[:1])
    app.setFont(QFont("Noto Sans", 10))
    app.setApplicationName("FORGE")
    app.setApplicationDisplayName("FORGE")
    app.setOrganizationName("FORGE")
    app.setWindowIcon(QIcon(str(APP_DIR / "ui" / "icon.png")))

    qmlRegisterModule("FORGE.UI", 1, 0)
    for component in sorted((APP_DIR / "ui" / "components").glob("*.qml")):
        qmlRegisterType(QUrl.fromLocalFile(str(component)), "FORGE.UI", 1, 0, component.stem)

    controller = AppController()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(APP_DIR / "ui"))
    engine.rootContext().setContextProperty("controller", controller)
    engine.load(QUrl.fromLocalFile(str(APP_DIR / "ui" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    if not isinstance(window, QQuickWindow):
        return 1
    window.requestActivate()
    if hasattr(window, "raise_"):
        window.raise_()

    if args.preview:
        QTimer.singleShot(0, lambda: controller.preview(args.preview[0]))
    if args.build:
        controller.askNames = False
        controller.submit(" ".join(args.build))

    if args.screenshot or (args.preview and len(args.preview) > 1):
        target = Path(args.screenshot or args.preview[1]).expanduser()
        delay = int(os.environ.get("FORGE_SCREENSHOT_DELAY", "3200"))

        def grab() -> None:
            image = window.grabWindow()
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(target))
            print("saved", target, image.width(), image.height())
            controller.shutdown()
            app.quit()

        QTimer.singleShot(delay, grab)

    def closing() -> None:
        controller.shutdown()

    app.aboutToQuit.connect(closing)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
