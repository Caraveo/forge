"""Durable stage records in the existing FORGE project directory."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import uuid


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf-8") as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate(path, durable=False):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Missing or empty artifact: {path}")
    suffix = path.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".webp"):
        from PIL import Image
        with Image.open(path) as image:
            image.load()
    elif suffix == ".glb":
        with path.open("rb") as stream:
            header = stream.read(20)
            if len(header) != 20:
                raise ValueError(f"Truncated GLB: {path}")
            magic, version, length, json_size, chunk = struct.unpack("<4sIII4s", header)
            if (magic, version, length, chunk) != (b"glTF", 2, path.stat().st_size, b"JSON"):
                raise ValueError(f"Invalid GLB: {path}")
            if not 0 < json_size <= length - 20:
                raise ValueError(f"Invalid GLB chunk: {path}")
            document = json.loads(stream.read(json_size))
            if not isinstance(document, dict) or not document.get("meshes"):
                raise ValueError(f"GLB has no mesh: {path}")
    elif suffix == ".json":
        json.loads(path.read_text(encoding="utf-8"))
    elif suffix == ".fbx":
        with path.open("rb") as stream:
            if not stream.read(23).startswith(b"Kaydara FBX Binary"):
                raise ValueError(f"Invalid FBX: {path}")
    if durable:
        with path.open("rb") as stream:
            os.fsync(stream.fileno())
        sync_directory(path.parent)
    return {"path": str(path.resolve()), "sha256": digest(path)}


@contextmanager
def exclusive(path):
    """OS-owned lock releases on normal exit or process termination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield stream.fileno()


class Paused(Exception):
    pass


class Checkpoint:
    def __init__(self, directory, inputs):
        self.directory = directory
        self.path = directory / "generation.json"
        self.pause = directory / "generation.pause"
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {
            "schema": 1, "id": uuid.uuid4().hex, "project": directory.name, "created": now(),
            "completed": {}, "current": None, "error": None, "state": "running", "inputs": inputs,
        }
        if self.data["inputs"] != inputs:
            self.data.update(inputs=inputs, completed={}, current=None, error=None)
        self.remaining = list(self.data["completed"])
        self.invalidated = False
        self.save(state="running")

    def save(self, **changes):
        self.data.update(changes, updated=now())
        atomic_json(self.path, self.data)

    def boundary(self):
        if self.pause.exists():
            self.save(state="paused")
            raise Paused()
        if (self.directory / "generation.close").exists():
            self.save(state="running")
            raise Paused()

    def perform(self, name, work):
        self.boundary()
        completed = self.data["completed"]
        record = completed.get(name)
        if self.remaining and self.remaining[0] == name:
            self.remaining.pop(0)
        else:
            self.invalidated = True
        if record and not self.invalidated:
            try:
                if all(validate(Path(item["path"])) == item for item in record["artifacts"]):
                    return record["value"]
            except (OSError, ValueError, SyntaxError):
                pass
        self.invalidated = True
        for stale in [name, *self.remaining]:
            completed.pop(stale, None)
        self.remaining.clear()
        self.save(current=name, error=None)
        try:
            value, artifacts = work()
            record = {"value": value, "artifacts": [validate(path, durable=True) for path in artifacts],
                      "finished": now()}
            completed[name] = record
            self.save(current=None)
        except Exception as exc:
            self.save(state="failed", error=str(exc))
            raise
        self.boundary()
        return value
