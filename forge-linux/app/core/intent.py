"""Prompt intent, naming and quality rules.

This is a line-for-line port of desktop/Intent.cs plus the small naming helpers
from desktop/Forge.cs, so the Linux app makes the same decisions as the Windows
build.
"""
from __future__ import annotations

import re
from pathlib import Path

DRAFT_WORDS = r"draft|low[- ]quality|low[- ]?res"
HIGH_WORDS = (
    r"super|superior|supreme|high[- ]quality|quality|hq|prime|premium|ultra|best|detailed|"
    r"hi[- ]?res|high[- ]res(?:olution)?|masterpiece"
)

STOP_WORDS = {
    "a", "an", "the", "of", "and", "with", "in", "on", "for", "to", "my", "me",
    "it", "this", "that", "some", "very", "really", "just",
}
NAME_STOP_WORDS = {
    "forge", "build", "make", "mold", "generate", "create", "imagine", "image",
    "please", "can", "could", "would", "you", "me", "my", "a", "an", "the", "of",
    "with", "and", "for", "in", "on", "at", "to", "some", "that", "this", "it",
    "is", "very", "named", "called", "model", "3d", "super", "superior", "supreme",
    "quality", "high", "hq", "prime", "premium", "ultra", "best", "detailed", "res",
    "hi", "hires", "lowres", "masterpiece", "draft", "low",
}


def subject(text: str | None) -> str | None:
    """Return the buildable idea in a chat message, or None for small talk."""
    s = re.sub(r"\s+", " ", (text or "").strip())
    if not s or s.endswith("?"):
        return None
    if re.match(
        r"^(how|what|why|when|where|who|which|can|could|would|should|is|are|do|does|did|will|tell me|explain|help)\b",
        s,
        re.I,
    ):
        return None
    small = (
        r"^(hi|hii+|hello|hey|heya|yo|sup|hiya|howdy|greetings|thanks|thank you|thx|ty|ok|okay|k|cool|nice|great|awesome|lol|haha|bye|goodbye|good (morning|afternoon|evening|night)|gm|gn|yes|yeah|yep|no|nope|sure|please|sorry|wow|test|testing)\b"
    )
    if re.match(
        small + r"[\s,.!:;)(-]*(there|forge|again|all|guys|buddy|friend|so much|a lot|everyone)?[\s,.!:;)(-]*$",
        s,
        re.I,
    ):
        return None
    s = re.sub(
        r"^(i('m| am) (thinking|dreaming) (about|of)|i('d| would) like|i want|maybe|how about|what about|let's (make|do|try)|imagine)\s+",
        "",
        s,
        flags=re.I,
    )
    s = s.strip(" .!,")
    for match in re.finditer(r"[A-Za-z]{3,}", s):
        if match.group(0).lower() not in STOP_WORDS:
            return s[:160] if len(s) > 160 else s
    return None


def quality(text: str) -> str:
    """Mirror infer_quality in desktop/runner.py."""
    if re.search(r"\b(?:%s)\b" % DRAFT_WORDS, text, re.I):
        return "draft"
    if re.search(r"\b(?:%s)\b" % HIGH_WORDS, text, re.I):
        return "high"
    return "standard"


def mode(text: str) -> str:
    request = (text or "").strip()
    if re.match(r"^(hi|hello|hey|thanks|thank you|how|what|why|when|where)\b", request, re.I):
        return "chat"
    request = re.sub(r"^(?:(?:please|can you|could you|would you)\s+)+", "", request, flags=re.I)
    if re.match(r"^(make sense|make sure|build up|imagine if)\b", request, re.I):
        return "chat"
    if re.match(r"^(don't|do not|never)\b", request, re.I):
        return "chat"
    if re.match(r"^remove\s+(?:the\s+)?background\b", request, re.I):
        return "background"
    if re.match(r"^upscale\b", request, re.I):
        return "upscale"
    if re.match(r"^rig\b", request, re.I):
        return "rig"
    if re.match(r"^(generate|create|imagine|image)\b", request, re.I):
        return "image"
    if re.match(r"^(forge|build|make|mold)\b", request, re.I):
        return "model"
    return "chat"


def clean_name(value: str | None) -> str:
    name = re.sub(r"[^A-Za-z0-9 _-]", " ", value or "")
    name = re.sub(r"\s+", " ", name.replace("_", " ")).strip()
    return name[:40].strip() if len(name) > 40 else name


def caption(path: str | Path) -> str:
    stem = re.sub(r"_\d{8}_\d{6}_\d+$", "", Path(path).stem)
    return stem.replace("_", " ")


def fallback_names(raw: str) -> list[str]:
    """Names drawn from the prompt itself, used when Qwen is unavailable."""
    words = [
        w
        for w in re.findall(r"[A-Za-z][A-Za-z0-9]*", raw)
        if len(w) > 1 and w.lower() not in NAME_STOP_WORDS
    ]
    words = [w[0].upper() + w[1:] for w in words]
    names: list[str] = []

    def add(parts: list[str]) -> None:
        name = " ".join(parts)
        if name and len(name) <= 40 and not any(n.lower() == name.lower() for n in names):
            names.append(name)

    if words:
        add(words[max(0, len(words) - 2):])
        add(words[max(0, len(words) - 3):])
        add([words[-1]])
        add(words[:2])
        add([words[-1], "Prop"])
        add([words[-1], "Asset"])
    i = 1
    while len(names) < 3:
        add(["Project", str(i)])
        i += 1
    return names


def kind_label(job_mode: str, job_quality: str) -> str:
    kind = {
        "image": "Image",
        "rig": "Rigging",
        "upscale": "Upscale",
        "background": "Background removal",
    }.get(job_mode, "3D model")
    if job_quality == "high" and job_mode in ("model", "image"):
        kind += " · high quality"
    elif job_quality == "draft" and job_mode == "model":
        kind += " · draft"
    return kind


def elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def generation_subject(raw):
    return re.sub(r"^\s*(?:(?:please|can you|could you|would you)\s+)*(?:forge|build|make|mold)\b",
                  "", raw, count=1, flags=re.I).strip()


def idle_model_draft(raw):
    if mode(raw) != "model":
        return False
    description = generation_subject(raw)
    if not description or description.endswith(("?", ",", ":", "…", "...")):
        return False
    words = re.findall(r"[^\W\d_]+", description.lower())
    if not words or words[-1] in STOP_WORDS | {"named", "called", "without", "or", "but"}:
        return False
    return any(word not in NAME_STOP_WORDS and len(word) >= 2 for word in words)
