"""Durable creative-assistant context for one FORGE project."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from .checkpoint import atomic_json
except ImportError:
    from checkpoint import atomic_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(project: Path) -> Path:
    return project / "creative.json"


def load(project: Path) -> dict | None:
    path = _path(project)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save(project: Path, data: dict) -> dict:
    data["updated"] = _now()
    atomic_json(_path(project), data)
    return data


def initialise(project: Path, original_prompt: str, enhanced_subject: str, response: dict) -> dict:
    existing = load(project)
    if existing is not None:
        return existing
    ideas = [
        {"id": "idea-%d" % index, "text": text, "status": "available"}
        for index, text in enumerate(response.get("suggestions", []), 1)
        if isinstance(text, str) and text.strip()
    ]
    data = {
        "schema": 1,
        "created": _now(),
        "original_prompt": original_prompt,
        "enhanced_subject": enhanced_subject,
        "question": response.get("question", ""),
        "ideas": ideas,
        "selected": [],
        "rejected": [],
        "modifications": [],
        "revisions": [],
        "conversation": [],
    }
    return save(project, data)


def _idea(data: dict, idea_id: str) -> dict | None:
    return next((idea for idea in data.get("ideas", []) if idea.get("id") == idea_id), None)


def select(project: Path, idea_id: str) -> dict:
    data = load(project)
    if data is None:
        raise ValueError("This project's creative context is unavailable.")
    idea = _idea(data, idea_id)
    if idea is None:
        raise ValueError("That idea is no longer available.")
    if idea.get("status") == "queued":
        raise ValueError("That idea is already queued for a revised version.")
    idea["status"] = "selected"
    if idea_id not in data["selected"]:
        data["selected"].append(idea_id)
    data["conversation"].append({"at": _now(), "kind": "accepted", "idea": idea_id})
    return save(project, data)


def reject(project: Path, idea_id: str) -> dict:
    data = load(project)
    if data is None:
        raise ValueError("This project's creative context is unavailable.")
    idea = _idea(data, idea_id)
    if idea is None:
        raise ValueError("That idea is no longer available.")
    idea["status"] = "rejected"
    if idea_id not in data["rejected"]:
        data["rejected"].append(idea_id)
    data["conversation"].append({"at": _now(), "kind": "rejected", "idea": idea_id})
    return save(project, data)


def add_modification(project: Path, text: str) -> dict:
    data = load(project)
    if data is None:
        raise ValueError("This project's creative context is unavailable.")
    value = " ".join(text.split())[:600]
    if not value:
        raise ValueError("Describe the change you would like to make.")
    data["modifications"].append(value)
    data["conversation"].append({"at": _now(), "kind": "modification", "text": value})
    return save(project, data)


def available_ideas(data: dict) -> list[dict]:
    return [idea for idea in data.get("ideas", []) if idea.get("status") == "available"]


def offer_next(project: Path) -> tuple[dict, dict] | tuple[dict, None]:
    """Offer one saved idea without asking Qwen to load again."""
    data = load(project)
    if data is None:
        raise ValueError("This project's creative context is unavailable.")
    idea = next((item for item in data.get("ideas", []) if item.get("status") == "available"), None)
    if idea is None:
        return data, None
    idea["status"] = "offered"
    data["conversation"].append({"at": _now(), "kind": "offered", "idea": idea["id"]})
    return save(project, data), idea


def revision_prompt(data: dict) -> str:
    additions = [idea["text"] for idea in data.get("ideas", []) if idea.get("status") == "selected"]
    additions.extend(data.get("modifications", []))
    prompt = data.get("original_prompt", "")
    return prompt + (", " + ", ".join(additions) if additions else "")


def record_revision(project: Path, prompt: str, job_id: str) -> dict:
    data = load(project)
    if data is None:
        raise ValueError("This project's creative context is unavailable.")
    queued_ideas = [idea["id"] for idea in data.get("ideas", []) if idea.get("status") == "selected"]
    for idea in data.get("ideas", []):
        if idea.get("id") in queued_ideas:
            idea["status"] = "queued"
    data["revisions"].append({"at": _now(), "prompt": prompt, "job_id": job_id,
                              "ideas": queued_ideas})
    data["conversation"].append({"at": _now(), "kind": "revision-queued", "job_id": job_id,
                                 "ideas": queued_ideas})
    return save(project, data)
