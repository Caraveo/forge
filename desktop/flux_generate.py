import argparse
import os
import re
from pathlib import Path

ROOT = Path(os.environ.get("FORGE_DATA", str(Path.home() / ".forge")))
os.environ.setdefault("MIOPEN_USER_DB_PATH", str(ROOT / "miopen-db"))
os.environ.setdefault("MIOPEN_CUSTOM_CACHE_DIR", str(ROOT / "miopen-cache"))
Path(os.environ["MIOPEN_USER_DB_PATH"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["MIOPEN_CUSTOM_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)

import torch
from diffusers import FluxPipeline
from PIL import PngImagePlugin
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table
from transformers import PreTrainedTokenizerFast

MODEL = "FLUX.1-schnell"
MODEL_DIR = Path(os.environ["FORGE_FLUX"])
OFFLOAD_DIR = ROOT / "models" / "offload" / "flux-schnell"
STYLE = "low-poly stylized 3D game asset, faceted geometry, hand-painted PBR colors, HDR high-contrast stylized color, vibrant HDR lighting, crisp edges, centered full object, clean pure white studio background"

ap = argparse.ArgumentParser(description="AMD/ROCm FLUX.1-schnell generator with a terminal UI")
ap.add_argument("prompt", nargs="*")
ap.add_argument("--prompt-file", default="", help="Read the complete prompt, including line breaks, from a UTF-8 text file")
ap.add_argument("--out", default="")
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--steps", type=int, default=4)
ap.add_argument("--width", type=int, default=768)
ap.add_argument("--height", type=int, default=768)
ap.add_argument("--max-tokens", type=int, default=512)
ap.add_argument("--offload", choices=("cpu", "disk"), default="cpu")
a = ap.parse_args()

console = Console()
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
if a.prompt_file:
    prompt = Path(a.prompt_file).read_text(encoding="utf-8").strip()
else:
    prompt = " ".join(a.prompt).strip()
if not prompt:
    raise SystemExit("Provide a prompt or --prompt-file")
full_prompt = f"{prompt}, {STYLE}"
slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:60] or "asset"
out = Path(a.out) if a.out else Path.cwd() / f"{slug}-flux-schnell-{a.seed}.png"

if not MODEL_DIR.exists() or not (MODEL_DIR / "transformer").exists():
    raise SystemExit(f"Complete {MODEL} snapshot not found at {MODEL_DIR}")

table = Table(title="FLUX image generation")
table.add_column("Setting", style="cyan")
table.add_column("Value", style="white")
table.add_row("MODEL", MODEL)
table.add_row("GPU", torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU")
table.add_row("ROCm", str(getattr(torch.version, "hip", "n/a")))
table.add_row("Mode", f"{a.offload} offload")
table.add_row("Prompt", prompt)
table.add_row("Size / steps", f"{a.width}x{a.height} / {a.steps}")
console.print(table)
console.print(f"[dim]Loading local model from {MODEL_DIR}[/dim]")

# The bundled T5 tokenizer.json is usable without the optional sentencepiece wheel.
# Passing it explicitly avoids Transformers trying to convert the slow tokenizer.
tokenizer_2 = PreTrainedTokenizerFast(
    tokenizer_file=str(MODEL_DIR / "tokenizer_2" / "tokenizer.json"),
    unk_token="<unk>", eos_token="</s>", pad_token="<pad>",
)
pipe = FluxPipeline.from_pretrained(
    str(MODEL_DIR), torch_dtype=dtype, local_files_only=True, tokenizer_2=tokenizer_2
)
if device.type == "cuda":
    if a.offload == "disk" and hasattr(pipe.transformer, "enable_group_offload"):
        OFFLOAD_DIR.mkdir(parents=True, exist_ok=True)
        try:
            # Coordinate placement for every large FLUX component. Applying
            # this only to the transformer leaves the T5 encoder on CPU while
            # the pipeline sends its token IDs to CUDA.
            for component in (pipe.text_encoder, pipe.text_encoder_2, pipe.transformer, pipe.vae):
                if hasattr(component, "enable_group_offload"):
                    component.enable_group_offload(
                        onload_device=device,
                        offload_device=torch.device("cpu"),
                        offload_type="leaf_level",
                        offload_to_disk_path=str(OFFLOAD_DIR),
                    )
                else:
                    component.to(device)
            console.print(f"[green]SSD offload: {OFFLOAD_DIR}[/green]")
        except Exception as exc:
            console.print(f"[yellow]Disk offload unavailable ({exc}); using sequential CPU offload.[/yellow]")
            pipe.enable_sequential_cpu_offload(device=device)
    else:
        pipe.enable_sequential_cpu_offload(device=device)
else:
    pipe.to(device)

with Progress(TextColumn("Generating"), BarColumn(), TextColumn("{task.completed}/{task.total}"), TimeRemainingColumn()) as progress:
    task = progress.add_task("generation", total=a.steps)

    def on_step_end(_pipe, step, _timestep, callback_kwargs):
        progress.update(task, completed=step + 1)
        return callback_kwargs

    generator = torch.Generator(device="cpu").manual_seed(a.seed)
    image = pipe(
        prompt=full_prompt,
        guidance_scale=0.0,
        num_inference_steps=a.steps,
        max_sequence_length=a.max_tokens,
        width=a.width,
        height=a.height,
        generator=generator,
        callback_on_step_end=on_step_end,
    ).images[0]

out.parent.mkdir(parents=True, exist_ok=True)
meta = PngImagePlugin.PngInfo()
for key, value in {
    "Model": MODEL,
    "Description": prompt,
    "Prompt": full_prompt,
    "Seed": str(a.seed),
    "Steps": str(a.steps),
    "Size": f"{a.width}x{a.height}",
    "Offload": a.offload,
}.items():
    meta.add_text(key, value)
image.save(out, pnginfo=meta)
console.print(f"[bold green]Saved:[/bold green] {out.resolve()}")
