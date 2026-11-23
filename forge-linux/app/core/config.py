"""Filesystem and configuration helpers for the Linux build."""
from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
APP_NAME = "FORGE"
VERSION = "0.05-linux"


def data_home() -> Path:
    override = os.environ.get("FORGE_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return (base / "FORGE-Data").resolve()


DATA = data_home()
RUNTIME = DATA / "runtime"
CONFIG_PATH = RUNTIME / "config.json"
SETUP_LOG = DATA / "setup.log"
OWNED_MARKER = RUNTIME / ".forge-owned"
PARKED_MARKER = RUNTIME / ".forge-upgrade"
COMPLETE_MARKER = ".complete-linux"


def documents_dir() -> Path:
    override = os.environ.get("FORGE_OUTPUT")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "Documents"


def default_output() -> Path:
    return documents_dir() / "FORGE"


def development_config() -> Path:
    return APP_DIR / "development.json"


def active_config_path() -> Path:
    dev = development_config()
    return dev if dev.is_file() else CONFIG_PATH


def load_config() -> dict | None:
    path = active_config_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def save_config(config: dict) -> Path:
    path = active_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def restore_runtime() -> None:
    """Undo the temporary marker rename used while upgrading the runtime."""
    if not PARKED_MARKER.is_file():
        return
    if OWNED_MARKER.is_file():
        PARKED_MARKER.unlink(missing_ok=True)
    else:
        PARKED_MARKER.replace(OWNED_MARKER)


def preserve_runtime() -> None:
    if not OWNED_MARKER.is_file():
        return
    PARKED_MARKER.unlink(missing_ok=True)
    OWNED_MARKER.replace(PARKED_MARKER)


def runtime_ready() -> bool:
    restore_runtime()
    return (
        CONFIG_PATH.is_file()
        and (RUNTIME / "unirig" / COMPLETE_MARKER).is_file()
        and (RUNTIME / "chat" / COMPLETE_MARKER).is_file()
    )


def ensure_runtime() -> Path:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    return RUNTIME


def remove_runtime() -> bool:
    """Remove only a runtime this project created (mirrors Setup.Remove)."""
    import shutil

    if not OWNED_MARKER.is_file():
        return False
    shutil.rmtree(RUNTIME, ignore_errors=True)
    return True
