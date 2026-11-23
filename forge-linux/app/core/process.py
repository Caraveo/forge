"""Process helpers shared by the GUI and command line runners."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Iterable


def kill_tree(process: subprocess.Popen | None, grace: float = 6.0) -> None:
    """Stop a runner and every process it launched (FLUX, TRELLIS, Blender, UniRig)."""
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=grace)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass


def run_checked(command: Iterable[str | Path], cwd: Path | None = None, env: dict | None = None) -> None:
    subprocess.run([str(part) for part in command], cwd=str(cwd) if cwd else None, env=env, check=True)


def python_executable() -> str:
    return sys.executable


def open_path(path: str | Path) -> None:
    """Open a file or folder with the desktop's default handler."""
    target = str(path)
    opener = "xdg-open"
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        raise RuntimeError("No desktop session is available to open " + target)
    subprocess.Popen([opener, target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
