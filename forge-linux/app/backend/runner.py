"""One local job. The GUI passes a request file so chat text never enters a shell.

Linux port of desktop/runner.py. The pipeline is unchanged: enhance the prompt,
paint with FLUX, sculpt with TRELLIS, then pack Unity files with Blender. Only
the platform-specific pieces (PowerShell rigging, Windows paths) are replaced.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parent
DATA = Path(os.environ.get("FORGE_DATA", str(Path.home() / ".local" / "share" / "FORGE-Data")))


def run(args, **kwargs):
    subprocess.run(list(map(str, args)), check=True, **kwargs)


# Quality presets. Words in the prompt choose one ("forge me a super apple" -> high);
# explicit --quality/--res/--steps always win. Keep the word lists in sync with
# app/core/intent.py, which shows the chosen preset in the app.
QUALITY = {
    "draft":    {"res": 512,  "steps": 8,  "atlas": 1024, "tex_res": 512,  "image": 768,  "texture": 1024},
    "standard": {"res": 512,  "steps": 12, "atlas": 1024, "tex_res": None, "image": 768,  "texture": 4096},
    "high":     {"res": 1024, "steps": 20, "atlas": 2048, "tex_res": 1024, "image": 768,  "texture": 4096, "upscale_image": True},
}
DRAFT_WORDS = r"draft|low[- ]quality|low[- ]?res"
HIGH_WORDS = (r"super|superior|supreme|high[- ]quality|quality|hq|prime|premium|ultra|best|detailed|"
              r"hi[- ]?res|high[- ]res(?:olution)?|masterpiece")


def infer_quality(text):
    if re.search(r"\b(?:%s)\b" % DRAFT_WORDS, text, re.I):
        return "draft"
    if re.search(r"\b(?:%s)\b" % HIGH_WORDS, text, re.I):
        return "high"
    return "standard"


def strip_quality(prompt):
    """Drop quality words so they steer the build, not the subject ("super apple" -> "apple")."""
    words = "|".join(w for w in (DRAFT_WORDS, HIGH_WORDS))
    prompt = re.sub(r"\b(?:%s)\b" % words, " ", prompt, flags=re.I)
    prompt = re.sub(r"^\s*(?:me|us)\s+", "", re.sub(r"\s+", " ", prompt)).strip(" ,.-")
    return re.sub(r"\b([Aa]) (?=[AEIOUaeiou])", r"\1n ", prompt)


def resolve_quality(raw, quality, resolution, steps, cfg):
    """Pick the preset, apply explicit overrides, and fall back if weights are missing."""
    name = quality if quality in QUALITY else infer_quality(raw)
    preset = dict(QUALITY[name], name=name)
    if resolution:
        preset["res"] = resolution
    if steps:
        preset["steps"] = steps
    if preset["res"] not in (512, 1024):
        print("[quality] Resolution %s is not installed; using 1024." % preset["res"], flush=True)
        preset["res"] = 1024
    models = Path(cfg["models"])
    needed = ["shape_flow_%d.gguf" % preset["res"], "tex_flow_%d.gguf" % preset["res"]]
    if not all((models / f).is_file() for f in needed):
        print("[quality] %s weights are missing; building at standard quality." % preset["res"], flush=True)
        preset.update({k: v for k, v in QUALITY["standard"].items()}, name="standard")
    return preset


def process(job, raw, mode, cfg, output=None, resolution=None, steps=None, seed=42, source=None, quality="auto"):
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
    preset = resolve_quality(raw, quality, resolution, steps, cfg)
    prompt = strip_quality(prompt) or prompt
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
            process(job, raw, "model", cfg, resolution=resolution, steps=steps, seed=seed, source=source, quality=quality)
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
        run([cfg["python"], APP / "rig.py", "--mesh", source, "--output", fbx,
             "--unirig", cfg.get("unirig", ""), "--cpu-python",
             str(Path(cfg.get("unirig", "")) / "python311" / "bin" / "python"),
             "--gpu-python", cfg["python"]], env=env)
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
        result = subprocess.run([cfg.get("enhancerPython", cfg["python"]), str(APP / "prompt_enhancer.py"), "--", prompt],
                                check=True, stdout=subprocess.PIPE, text=True, env=env)
        prompt = result.stdout.strip()
        if not prompt:
            raise ValueError("The enhancer returned an empty prompt.")
        print(prompt, flush=True)
        print("[prompt] " + " ".join(prompt.split()), flush=True)
        if mode == "enhance":
            return
    label = {"draft": "draft", "standard": "", "high": "high quality"}[preset["name"]]
    if label:
        print("[quality] %s: %s geometry, %s steps, %spx atlas, %spx Unity textures" % (
            label, preset["res"], preset["steps"], preset["atlas"], preset["texture"]), flush=True)
    if source is None:
        stage("Generating image" + (" (%s)" % label if label else ""))
        flux = [cfg["python"], APP / "flux_generate.py", "--out", image, "--seed", seed,
                "--steps", steps if mode == "image" and steps else 4,
                "--offload", "disk"]
        try:
            run(flux + ["--width", preset["image"], "--height", preset["image"], "--", prompt], env=env)
        except subprocess.CalledProcessError:
            if preset["image"] <= 768:
                raise
            print("[quality] The image was too large for the GPU; painting it at 768 px.", flush=True)
            run(flux + ["--width", 768, "--height", 768, "--", prompt], env=env)
    if not image.is_file():
        raise FileNotFoundError(image)
    if mode == "image":
        if preset.get("upscale_image") and source is None:
            # High-quality images: paint at 768 px, then upscale 4x to 3072 px.
            stage("Upscaling image (high quality)")
            larger = image.with_name(image.stem + "-4x.png")
            run([cfg["upscaler"], "-i", image, "-o", larger, "-n", "realesrgan-x4plus",
                 "-m", Path(cfg["upscaler"]).parent / "models", "-s", 4, "-f", "png"], env=env)
            larger.replace(image)
        return
    # Events the app turns into conversation: [show] when a file is ready,
    # [watch] for a file another process will write while it runs.
    if source is None:
        print("[show] image " + str(image), flush=True)
    print("[watch] cutout " + str(mesh.with_name(mesh.stem + "_cutout.png")), flush=True)

    def build(settings):
        command = [cfg["trellis"], "--models", cfg["models"], "--image", image, "--output", mesh,
                   "--backend", "Vulkan", "--gpu", cfg.get("vulkanGPU", 0), "--res", settings["res"],
                   "--steps", settings["steps"], "--seed", seed, "--atlas", settings["atlas"],
                   "--dump-bg", "--webp", "off", "--verbose"]
        if settings["tex_res"]:
            command += ["--tex-res", settings["tex_res"]]
        run(command, env=env)

    stage("Building textured model" + (" (%s)" % label if label else ""))
    try:
        build(preset)
    except subprocess.CalledProcessError:
        if preset["name"] != "high":
            raise
        # A high-quality build can exhaust VRAM on a 16 GB card; finish the job anyway.
        print("[quality] The high-quality build stopped; retrying at standard quality.", flush=True)
        preset = dict(QUALITY["standard"], name="standard")
        stage("Building textured model (standard retry)")
        build(preset)
    if not mesh.is_file():
        raise FileNotFoundError(mesh)
    print("[show] model " + str(mesh), flush=True)
    stage("Preparing Unity files")
    assets = job / (job.name + "-asset")
    assets.mkdir(exist_ok=True)
    fbx = assets / (job.name + ".fbx")
    export = [cfg["blender"], "-b", "--factory-startup", "--python-exit-code", "1",
              "--python", APP / "transit_blender.py", "--", mesh, fbx, assets]
    run(export, env=env)
    from PIL import Image
    for texture in list(assets.glob("*.png")):
        with Image.open(texture) as baked:
            size = max(baked.size)
        if size < preset["texture"]:
            scaled = texture.with_name(texture.stem + "-4x.png")
            run([cfg["upscaler"], "-i", texture, "-o", scaled, "-n", "realesrgan-x4plus",
                 "-m", Path(cfg["upscaler"]).parent / "models", "-s", 4, "-f", "png"], env=env)
            scaled.replace(texture)
        # Cap Unity textures at the preset size; a 2048 atlas upscaled 4x would be 8K.
        with Image.open(texture) as current:
            current.load()
            if max(current.size) > preset["texture"]:
                ratio = preset["texture"] / max(current.size)
                current.resize((round(current.width * ratio), round(current.height * ratio)),
                               Image.LANCZOS).save(texture)
    run(export, env=env)
    if not fbx.is_file():
        raise FileNotFoundError(fbx)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--resolution", "--res", type=int, choices=(512, 1024),
                        help="geometry resolution; overrides the quality preset")
    parser.add_argument("--quality", choices=["auto", "draft", "standard", "high"], default="auto",
                        help="auto reads words such as super, premium or draft from the prompt")
    parser.add_argument("--steps", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", choices=["image", "model", "enhance", "upscale", "background", "rig"], default="model")
    parser.add_argument("--input", type=Path)
    parser.add_argument("prompt", nargs="*")
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8-sig"))
    prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", args.name or "forge")
    job = args.job or Path.cwd() / (prefix + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    job.mkdir(parents=True, exist_ok=bool(args.job))
    raw = (job / "prompt.txt").read_text(encoding="utf-8-sig") if args.job else " ".join(args.prompt)
    if not raw.strip() and args.input:
        raw = args.mode
    if not raw.strip():
        parser.error("Describe the asset to build")
    process(job, raw.strip(), args.mode, cfg, args.out.resolve() if args.out else None,
            args.resolution, args.steps, args.seed, args.input.resolve() if args.input else None,
            args.quality)
