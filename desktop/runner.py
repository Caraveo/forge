"""One local job. The GUI passes a request file so chat text never enters a shell."""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parent
DATA = Path(os.environ["LOCALAPPDATA"]) / "FORGE-Data"


def run(args, **kwargs):
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def process(job, raw, mode, cfg, output=None, resolution=512, steps=None, seed=42):
    def stage(label):
        print("[stage] " + label, flush=True)

    prompt = re.sub(r"^(forge|build|generate|image|enhance)\s+", "", raw, flags=re.I)
    image = output if output and mode == "image" else job / (job.name + ".png")
    mesh = output if output and mode == "model" else image.with_suffix(".glb")
    for path in (image, mesh):
        path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, FORGE_DATA=cfg.get("cache", str(DATA)), FORGE_FLUX=cfg["flux"],
               HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", PYTHONUNBUFFERED="1")
    if mode != "image":
        stage("Enhancing prompt")
        result = subprocess.run([cfg["enhancerPython"], str(APP / "prompt_enhancer.py"), "--", prompt],
                                check=True, stdout=subprocess.PIPE, text=True, env=env)
        prompt = result.stdout.strip()
        if not prompt:
            raise ValueError("The enhancer returned an empty prompt.")
        print(prompt, flush=True)
        if mode == "enhance":
            return
    stage("Generating image")
    run([cfg["python"], APP / "flux_generate.py", "--out", image, "--seed", seed,
         "--steps", steps if mode=="image" and steps else 4, "--", prompt], env=env)
    if not image.is_file():
        raise FileNotFoundError(image)
    if mode == "image":
        return
    stage("Building textured model")
    run([cfg["trellis"], "--models", cfg["models"], "--image", image, "--output", mesh,
         "--backend", "Vulkan", "--gpu", cfg.get("vulkanGPU", 0), "--res", resolution,
         "--steps", steps or 12, "--seed", seed,
         "--dump-bg", "--webp", "off", "--verbose"], env=env)
    if not mesh.is_file():
        raise FileNotFoundError(mesh)
    stage("Preparing Unity files")
    assets = job / (job.name + "-asset")
    assets.mkdir(exist_ok=True)
    fbx = assets / (job.name + ".fbx")
    export = [cfg["blender"], "-b", "--factory-startup", "--python-exit-code", "1",
              "--python", APP / "transit_blender.py", "--", mesh, fbx, assets]
    run(export, env=env)
    for texture in list(assets.glob("*.png")):
        scaled = texture.with_name(texture.stem + "-4x.png")
        run([cfg["upscaler"], "-i", texture, "-o", scaled, "-n", "realesrgan-x4plus",
             "-m", Path(cfg["upscaler"]).parent / "models", "-s", 4, "-f", "png"], env=env)
        scaled.replace(texture)
    run(export, env=env)
    if not fbx.is_file():
        raise FileNotFoundError(fbx)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--resolution", "--res", type=int, choices=(512,1024,1536), default=512)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", choices=["image", "model", "enhance"], default="model")
    parser.add_argument("prompt", nargs="*")
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8-sig"))
    prefix = re.sub(r"[^A-Za-z0-9_-]+","_",args.name or "forge")
    job = args.job or Path.cwd() / (prefix + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    job.mkdir(exist_ok=bool(args.job))
    raw = (job / "prompt.txt").read_text(encoding="utf-8-sig") if args.job else " ".join(args.prompt)
    if not raw.strip():
        parser.error("Describe the asset to build")
    process(job, raw.strip(), args.mode, cfg, args.out.resolve() if args.out else None,
            args.resolution, args.steps, args.seed)
