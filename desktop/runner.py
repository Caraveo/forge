"""One local job. The GUI passes a request file so chat text never enters a shell."""
import argparse
import json
import os
import re
import subprocess
import sys
import shutil
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parent
DATA = Path(os.environ["LOCALAPPDATA"]) / "FORGE-Data"


def run(args, **kwargs):
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def process(job, raw, mode, cfg, output=None, resolution=512, steps=None, seed=42, source=None):
    def stage(label):
        print("[stage] " + label, flush=True)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        if source and output.resolve() == source.resolve():
            raise ValueError("Choose an output path different from the input.")
    if source and mode == "image":
        raise ValueError("Use model, background, upscale, or rig with an attached image.")
    if source and mode != "rig" and source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("This operation requires an image attachment.")

    prompt = re.sub(r"^(?:(?:please|can you|could you|would you)\s+)+", "", raw.strip(), flags=re.I)
    prompt = re.sub(r"^(forge|build|make|mold|generate|create|imagine|image|enhance)\s+", "", prompt, flags=re.I)
    image = output if output and mode == "image" else job / (job.name + ".png")
    mesh = output if output and mode == "model" else image.with_suffix(".glb")
    for path in (image, mesh):
        path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, FORGE_DATA=cfg.get("cache", str(DATA)), FORGE_FLUX=cfg["flux"],
               HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", PYTHONUNBUFFERED="1")
    if mode == "background":
        if source is None or not source.is_file():
            raise ValueError("Select an image to remove its background.")
        stage("Removing background")
        target = job / "background.glb"
        run([cfg["trellis"], "--models", cfg["models"], "--image", source,
             "--output", target, "--backend", "Vulkan", "--bg-only", "--dump-bg",
             "--bg-removal", "birefnet"], env=env)
        cutout = target.with_name("background_cutout.png")
        shutil.copy2(cutout, output or image)
        return
    if mode == "rig":
        if source is None or not source.is_file():
            raise ValueError("Select a model or image to rig.")
        if source.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            process(job, raw, "model", cfg, resolution=resolution, steps=steps, seed=seed, source=source)
            source = job / (job.name + "-asset") / (job.name + ".fbx")
        if source.suffix.lower() == ".glb":
            prepared = job / "rig-input"
            prepared.mkdir(exist_ok=True)
            converted = prepared / "model.fbx"
            stage("Preparing model for rigging")
            run([cfg["blender"], "-b", "--factory-startup", "--python-exit-code", "1",
                 "--python", APP / "transit_blender.py", "--", source, converted, prepared], env=env)
            source = converted
        stage("Rigging with UniRig")
        fbx = output or job / (job.name + ".fbx")
        run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             APP / "rig.ps1", "-Mesh", source, "-Output", fbx], env=env)
        if not fbx.is_file():
            raise FileNotFoundError(fbx)
        return
    if mode == "upscale":
        if source is None or not source.is_file():
            raise ValueError("Select an image to upscale.")
        stage("Upscaling image")
        run([cfg["upscaler"], "-i", source, "-o", output or image,
             "-n", "realesrgan-x4plus", "-m", Path(cfg["upscaler"]).parent / "models",
             "-s", 4, "-f", "png"], env=env)
        if not (output or image).is_file():
            raise FileNotFoundError(output or image)
        return
    if source is not None:
        from PIL import Image
        with Image.open(source) as attached:
            attached.convert("RGBA").save(image)
    if mode != "image" and source is None:
        stage("Enhancing prompt")
        result = subprocess.run([cfg["enhancerPython"], str(APP / "prompt_enhancer.py"), "--", prompt],
                                check=True, stdout=subprocess.PIPE, text=True, env=env)
        prompt = result.stdout.strip()
        if not prompt:
            raise ValueError("The enhancer returned an empty prompt.")
        print(prompt, flush=True)
        if mode == "enhance":
            return
    if source is None:
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
    parser.add_argument("--mode", choices=["image", "model", "enhance", "upscale", "background", "rig"], default="model")
    parser.add_argument("--input", type=Path)
    parser.add_argument("prompt", nargs="*")
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8-sig"))
    prefix = re.sub(r"[^A-Za-z0-9_-]+","_",args.name or "forge")
    job = args.job or Path.cwd() / (prefix + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    job.mkdir(exist_ok=bool(args.job))
    raw = (job / "prompt.txt").read_text(encoding="utf-8-sig") if args.job else " ".join(args.prompt)
    if not raw.strip() and args.input:
        raw = args.mode
    if not raw.strip():
        parser.error("Describe the asset to build")
    process(job, raw.strip(), args.mode, cfg, args.out.resolve() if args.out else None,
            args.resolution, args.steps, args.seed, args.input.resolve() if args.input else None)
