"""Read-only resource checks for local GPU stages.

The checker only observes the host.  It never terminates a process, clears a
cache, or tries to reclaim memory belonging to another application.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


GIB = 1024 ** 3


class MemoryUnavailable(RuntimeError):
    """Raised before a model is allowed to allocate its working memory."""


@dataclass(frozen=True)
class MemoryBudget:
    name: str
    vram_gib: float
    ram_gib: float


DEFAULT_BUDGETS = {
    "subject": MemoryBudget("Qwen subject assistant", 13, 20),
    "subject-cpu": MemoryBudget("Qwen subject assistant on CPU", 0, 20),
    "flux": MemoryBudget("reference image generation", 8, 12),
    "trellis-standard": MemoryBudget("standard 3D reconstruction", 8, 8),
    "trellis-high": MemoryBudget("high-quality 3D reconstruction", 12, 10),
    "upscale": MemoryBudget("image upscaling", 2, 3),
    "unirig": MemoryBudget("rigging", 6, 6),
}


def available_ram_bytes() -> int:
    """Return Linux MemAvailable, which accounts for reclaimable file cache."""
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise MemoryUnavailable("FORGE could not read available system memory.")


def available_vram_bytes() -> tuple[int, int]:
    """Return free and total VRAM from the AMD DRM driver.

    A desktop can expose the primary display as card0 and an AMD compute GPU as
    another card.  Selecting the largest dedicated VRAM device avoids assuming
    a fixed card number.
    """
    devices = []
    for card in Path("/sys/class/drm").glob("card[0-9]*"):
        device = card / "device"
        total = device / "mem_info_vram_total"
        used = device / "mem_info_vram_used"
        if total.is_file() and used.is_file():
            try:
                total_bytes = int(total.read_text().strip())
                used_bytes = int(used.read_text().strip())
            except ValueError:
                continue
            if total_bytes > 0:
                devices.append((total_bytes - used_bytes, total_bytes))
    if not devices:
        raise MemoryUnavailable("FORGE could not read available AMD GPU memory.")
    return max(devices, key=lambda item: item[1])


def budget_for(stage: str, cfg: dict, quality: str = "standard") -> MemoryBudget:
    key = "trellis-%s" % quality if stage == "trellis" else stage
    default = DEFAULT_BUDGETS[key]
    configured = cfg.get("memoryBudgetsGiB", {}).get(key, {})
    return MemoryBudget(
        default.name,
        float(configured.get("vram", default.vram_gib)),
        float(configured.get("ram", default.ram_gib)),
    )


def require_memory(stage: str, cfg: dict, quality: str = "standard") -> None:
    """Reject a GPU stage before it loads when its memory budget is unavailable."""
    budget = budget_for(stage, cfg, quality)
    free_vram = total_vram = 0
    if budget.vram_gib > 0:
        free_vram, total_vram = available_vram_bytes()
    free_ram = available_ram_bytes()
    required_vram = round(budget.vram_gib * GIB)
    required_ram = round(budget.ram_gib * GIB)
    if free_vram >= required_vram and free_ram >= required_ram:
        vram_status = ("%.1f/%.1f GiB VRAM and " % (free_vram / GIB, total_vram / GIB)) if budget.vram_gib else ""
        print(
            "[memory] %s: %s%.1f GiB RAM available"
            % (budget.name, vram_status, free_ram / GIB),
            flush=True,
        )
        return
    shortages = []
    if budget.vram_gib and free_vram < required_vram:
        shortages.append("%.1f GiB VRAM available, %.1f GiB required" % (free_vram / GIB, budget.vram_gib))
    if free_ram < required_ram:
        shortages.append("%.1f GiB RAM available, %.1f GiB required" % (free_ram / GIB, budget.ram_gib))
    message = (
        "Not enough available memory for %s: %s. Close other applications that use GPU or system "
        "memory, then resume this project. FORGE did not start this stage."
        % (budget.name, "; ".join(shortages))
    )
    print("[memory-blocked] " + message, flush=True)
    raise MemoryUnavailable(message)
