"""Small, read-only host resource snapshots for FORGE's status glyphs."""
from __future__ import annotations

from pathlib import Path


def _meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, value, *_ = line.split()
            values[key.rstrip(":")] = int(value) * 1024
    except (OSError, ValueError):
        pass
    return values


def _cpu_total() -> tuple[int, int] | None:
    try:
        fields = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()[1:]
        values = [int(value) for value in fields]
        total = sum(values)
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return total, idle
    except (OSError, ValueError, IndexError):
        return None


class ResourceMonitor:
    """Collects metrics without changing GPU state or touching other apps."""

    def __init__(self):
        self._cpu = _cpu_total()

    def snapshot(self) -> dict[str, float]:
        memory = _meminfo()
        total_ram = memory.get("MemTotal", 0)
        available_ram = memory.get("MemAvailable", total_ram)
        system_memory = 0.0 if not total_ram else 1 - available_ram / total_ram

        vram_used = vram_total = 0
        gpu_busy: float | None = None
        for card in Path("/sys/class/drm").glob("card[0-9]*"):
            device = card / "device"
            try:
                total = int((device / "mem_info_vram_total").read_text().strip())
                used = int((device / "mem_info_vram_used").read_text().strip())
            except (OSError, ValueError):
                continue
            if total > vram_total:
                vram_total, vram_used = total, used
                try:
                    gpu_busy = float((device / "gpu_busy_percent").read_text().strip()) / 100
                except (OSError, ValueError):
                    gpu_busy = None

        current = _cpu_total()
        cpu = 0.0
        if current is not None and self._cpu is not None:
            total_delta = current[0] - self._cpu[0]
            idle_delta = current[1] - self._cpu[1]
            if total_delta > 0:
                cpu = 1 - idle_delta / total_delta
        self._cpu = current
        return {
            "vram": max(0.0, min(1.0, vram_used / vram_total)) if vram_total else 0.0,
            "ram": max(0.0, min(1.0, system_memory)),
            "gpu": max(0.0, min(1.0, gpu_busy if gpu_busy is not None else 0.0)),
            "cpu": max(0.0, min(1.0, cpu)),
        }
