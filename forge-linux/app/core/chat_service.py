"""Local Qwen chat and project-name suggestions, one subprocess per request."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from . import intent
from .process import kill_tree


class ChatService(QObject):
    thinking = Signal(bool)
    reply = Signal(str, str)          # text, subject (may be empty)
    namesSuggested = Signal(list)
    error = Signal(str)

    def __init__(self, config_path: Path, cfg: dict, app_dir: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.config_path = Path(config_path)
        self.cfg = cfg
        self.app_dir = Path(app_dir)
        self.python = cfg.get("python") or sys.executable
        self._gate = threading.Semaphore(1)
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._conversation: list[dict[str, str]] = []
        self._closed = False

    def ask(self, raw: str, source: Path | None) -> None:
        if self._closed:
            return
        thread = threading.Thread(target=self._ask_worker, args=(raw, source), daemon=True)
        thread.start()

    def suggest(self, raw: str) -> None:
        if self._closed or not self.cfg.get("chat"):
            return
        threading.Thread(target=self._suggest_worker, args=(raw,), daemon=True).start()

    def close(self) -> None:
        self._closed = True
        with self._lock:
            process = self._process
        kill_tree(process)

    # -- internals ------------------------------------------------------
    def _ask_worker(self, raw: str, source: Path | None) -> None:
        self.thinking.emit(True)
        with self._gate:
            scratch = Path(tempfile.mkdtemp(prefix="FORGE-chat-"))
            try:
                with self._lock:
                    self._conversation.append({"role": "user", "content": raw})
                    messages = list(self._conversation[-12:])
                request = scratch / "chat.json"
                reply_path = scratch / "reply.txt"
                request.write_text(json.dumps({
                    "messages": messages,
                    "attachment": Path(source).name if source else "none",
                }), encoding="utf-8")
                command = [
                    self.python, "-u", str(self.app_dir / "backend" / "chat.py"),
                    str(request), str(self.config_path), str(reply_path),
                ]
                process = subprocess.Popen(
                    command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    text=True, start_new_session=True,
                )
                with self._lock:
                    self._process = process
                try:
                    _, errors = process.communicate(timeout=600)
                except subprocess.TimeoutExpired:
                    kill_tree(process)
                    raise RuntimeError("Chat took too long.")
                finally:
                    with self._lock:
                        self._process = None
                if process.returncode != 0:
                    raise RuntimeError("Chat failed. " + (errors or "").strip())
                text = reply_path.read_text(encoding="utf-8").strip()
                if not text:
                    raise RuntimeError("Chat returned an empty reply.")
                with self._lock:
                    self._conversation.append({"role": "assistant", "content": text})
                    if len(self._conversation) > 12:
                        del self._conversation[: len(self._conversation) - 12]
                self.reply.emit(text, intent.subject(raw) or "")
            except Exception as exc:  # noqa: BLE001 - shown as a chat line
                self.error.emit(str(exc))
            finally:
                shutil.rmtree(scratch, ignore_errors=True)
                self.thinking.emit(False)

    def _suggest_worker(self, raw: str) -> None:
        scratch = Path(tempfile.mkdtemp(prefix="FORGE-names-"))
        try:
            prompt = scratch / "prompt.txt"
            reply = scratch / "names.txt"
            prompt.write_text(raw, encoding="utf-8")
            command = [
                self.python, "-u", str(self.app_dir / "backend" / "names.py"),
                str(prompt), str(self.config_path), str(reply),
            ]
            process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, start_new_session=True,
            )
            try:
                process.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                kill_tree(process)
                return
            if process.returncode != 0 or not reply.is_file():
                return
            names: list[str] = []
            for line in reply.read_text(encoding="utf-8").splitlines():
                name = intent.clean_name(line)
                if name and not any(existing.lower() == name.lower() for existing in names):
                    names.append(name)
            if names:
                self.namesSuggested.emit(names[:5])
        except Exception:
            pass
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
