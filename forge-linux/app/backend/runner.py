"""Run local generation tools and save stage checkpoints for 3D builds."""
import argparse
import ctypes
import signal
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if __package__:
    from .checkpoint import Checkpoint, Paused, atomic_json, digest, exclusive
    from .creative import initialise as initialise_creative, offer_next
    from .memory import MemoryUnavailable, require_memory
    from .subject import MODEL
else:
    from checkpoint import Checkpoint, Paused, atomic_json, digest, exclusive
    from creative import initialise as initialise_creative, offer_next
    from memory import MemoryUnavailable, require_memory
    from subject import MODEL

GPU_LOCK = ()
PAUSED_EXIT = 75
APP = Path(__file__).resolve().parent
DATA = Path(os.environ.get("FORGE_DATA", str(Path.home() / ".local" / "share" / "FORGE-Data")))


def run(args, **kwargs):
    subprocess.run(list(map(str, args)), check=True, pass_fds=GPU_LOCK, **kwargs)


def released(name):
    """Record a completed subprocess handoff for diagnostics, never system cleanup."""
    print("[model-released] " + name, flush=True)


def compile_image_prompt(prompt, cfg, env):
    compiled = subprocess.check_output(
        [cfg.get("enhancerPython", cfg["python"]), APP / "prompt_enhancer.py", "--", prompt],
        text=True, env=env, pass_fds=GPU_LOCK).strip()
    if not compiled:
        raise ValueError("The enhancer returned an empty prompt.")
    return compiled


def enhance_subject(job, prompt, source, cfg, env):
    request = job / "subject-request.json"
    result = job / "subject.json"
    result.unlink(missing_ok=True)
    atomic_json(request, {"subject": prompt, "reference": str(source) if source else None,
                          "cache": str(Path(cfg.get("cache", DATA)) / "models" / "qwen"),
                          "revision": cfg.get("subjectRevision", "main"),
                          "memory": cfg})
    print("[stage] Preparing your subject", flush=True)
    # The Qwen worker chooses GPU or the explicitly budgeted CPU/RAM fallback
    # immediately before model placement. Do not pre-reject here: an idle GPU
    # can change between queueing and the worker starting.
    subject_env = dict(env, HF_HUB_OFFLINE="0" if cfg.get("subjectDownload", True) else "1")
    dependencies = Path(cfg["python"]).parent.parent.parent / "subject-deps"
    if dependencies.is_dir():
        subject_env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (str(dependencies), env.get("PYTHONPATH"))))
    try:
        run([cfg["python"], APP / "subject.py", "--request", request, "--result", result],
            env=subject_env)
        reply = json.loads(result.read_text(encoding="utf-8"))
    except MemoryUnavailable:
        raise
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 76:
            raise MemoryUnavailable("FORGE did not load Qwen because available memory changed.") from exc
        print(f"[subject] Qwen unavailable: {exc}", flush=True)
        print("[subject-fallback]", flush=True)
        reply = {"subject": prompt, "suggestions": [], "question": "", "engine": "legacy"}
    except (OSError, ValueError) as exc:
        print(f"[subject] Qwen unavailable: {exc}", flush=True)
        print("[subject-fallback]", flush=True)
        reply = {"subject": prompt, "suggestions": [], "question": "", "engine": "legacy"}
    if not isinstance(reply.get("suggestions"), list):
        suggestion = reply.get("suggestion")
        reply["suggestions"] = [suggestion] if isinstance(suggestion, str) and suggestion else []
    reply.setdefault("question", "")
    reply.setdefault("engine", MODEL)
    if source is None:
        reply["image_prompt"] = compile_image_prompt(reply["subject"], cfg, env)
    atomic_json(result, reply)
    return reply, [result]


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


def process(job, raw, mode, cfg, output=None, resolution=None, steps=None, seed=42, source=None, quality="auto", checkpoint=None):
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
        require_memory("trellis", cfg, "standard")
        target = job / "background.glb"
        run([cfg["trellis"], "--models", cfg["models"], "--image", source,
             "--output", target, "--backend", "Vulkan", "--bg-only", "--dump-bg",
             "--bg-removal", "birefnet"], env=env)
        released("TRELLIS")
        cutout = target.with_name("background_cutout.png")
        shutil.copy2(cutout, output or image)
        return
    if mode == "rig":
        if source is None or not source.is_file():
            raise ValueError("Select a model or image to rig.")
        if source.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            process(job, raw, "model", cfg, resolution=resolution, steps=steps, seed=seed, source=source, quality=quality, checkpoint=checkpoint)
            source = job / (job.name + "-asset") / (job.name + ".fbx")
        def rig_asset():
            rig_source = source
            if rig_source.suffix.lower() == ".glb":
                prepared = job / "rig-input"
                prepared.mkdir(exist_ok=True)
                converted = prepared / "model.fbx"
                stage("Preparing model for rigging")
                run([cfg["blender"], "-b", "--factory-startup", "--python-exit-code", "1",
                     "--python", APP / "transit_blender.py", "--", rig_source, converted, prepared], env=env)
                rig_source = converted
            stage("Rigging with UniRig")
            require_memory("unirig", cfg)
            fbx = output or job / (job.name + ".fbx")
            fbx.unlink(missing_ok=True)
            run([cfg["python"], APP / "rig.py", "--mesh", rig_source, "--output", fbx,
                 "--unirig", cfg.get("unirig", ""), "--cpu-python",
                 str(Path(cfg.get("unirig", "")) / "python311" / "bin" / "python"),
                 "--gpu-python", cfg["python"]], env=env)
            released("UniRig")
            if not fbx.is_file():
                raise FileNotFoundError(fbx)
            return None, [fbx]

        if checkpoint:
            checkpoint.perform("rig", rig_asset)
        else:
            rig_asset()
        return
    if mode == "upscale":
        if source is None or not source.is_file():
            raise ValueError("Select an image to upscale.")
        stage("Upscaling image")
        require_memory("upscale", cfg)
        run([cfg["upscaler"], "-i", source, "-o", output or image,
             "-n", "realesrgan-x4plus", "-m", Path(cfg["upscaler"]).parent / "models",
             "-s", 4, "-f", "png"], env=env)
        released("Real-ESRGAN")
        if not (output or image).is_file():
            raise FileNotFoundError(output or image)
        return
    if mode == "model":
        subject = checkpoint.perform("subject", lambda: enhance_subject(
            job, "" if source and prompt in ("model", "rig", "forge") else prompt, source, cfg, env))
        creative = initialise_creative(job, raw, subject["subject"], subject)
        prompt = subject.get("image_prompt", subject["subject"])
        if subject["subject"]:
            print("[prompt] " + " ".join(subject["subject"].split()), flush=True)
        creative, idea = offer_next(job)
        if idea is not None:
            print("[suggestion] " + json.dumps({"id": idea["id"], "text": idea["text"]}), flush=True)
        if creative.get("question"):
            print("[creative-question] " + creative["question"], flush=True)
    if mode == "enhance":
        stage("Enhancing prompt")
        result = compile_image_prompt(prompt, cfg, env)
        print(result, flush=True)
        print("[prompt] " + " ".join(result.split()), flush=True)
        return
    label = {"draft": "draft", "standard": "", "high": "high quality"}[preset["name"]]
    if label:
        print("[quality] %s: %s geometry, %s steps, %spx atlas, %spx Unity textures" % (
            label, preset["res"], preset["steps"], preset["atlas"], preset["texture"]), flush=True)
    def reference():
        if mode == "model":
            image.unlink(missing_ok=True)
        if source is not None:
            from PIL import Image
            stage("Preparing your reference image")
            with Image.open(source) as attached:
                attached.convert("RGBA").save(image)
        else:
            stage("Generating image" + (" (%s)" % label if label else ""))
            require_memory("flux", cfg)
            flux = [cfg["python"], APP / "flux_generate.py", "--out", image, "--seed", seed,
                    "--steps", steps if mode == "image" and steps else 4,
                    "--offload", "disk"]
            try:
                run(flux + ["--width", preset["image"], "--height", preset["image"], "--", prompt], env=env)
                released("FLUX")
            except subprocess.CalledProcessError:
                if preset["image"] <= 768:
                    raise
                print("[quality] The image was too large for the GPU; painting it at 768 px.", flush=True)
                run(flux + ["--width", 768, "--height", 768, "--", prompt], env=env)
                released("FLUX")
        return None, [image]

    if mode == "model":
        checkpoint.perform("reference", reference)
    else:
        reference()
    if not image.is_file():
        raise FileNotFoundError(image)
    if mode == "image":
        if preset.get("upscale_image") and source is None:
            # High-quality images: paint at 768 px, then upscale 4x to 3072 px.
            stage("Upscaling image (high quality)")
            require_memory("upscale", cfg)
            larger = image.with_name(image.stem + "-4x.png")
            run([cfg["upscaler"], "-i", image, "-o", larger, "-n", "realesrgan-x4plus",
                 "-m", Path(cfg["upscaler"]).parent / "models", "-s", 4, "-f", "png"], env=env)
            released("Real-ESRGAN")
            larger.replace(image)
        return
    # Events the app turns into conversation: [show] when a file is ready,
    # [watch] for a file another process will write while it runs.
    if source is None:
        print("[show] image " + str(image), flush=True)
    cutout = mesh.with_name(mesh.stem + "_cutout.png")

    def build(settings):
        command = [cfg["trellis"], "--models", cfg["models"], "--image", image, "--output", mesh,
                   "--backend", "Vulkan", "--gpu", cfg.get("vulkanGPU", 0), "--res", settings["res"],
                   "--steps", settings["steps"], "--seed", seed, "--atlas", settings["atlas"],
                   "--dump-bg", "--webp", "off", "--verbose"]
        if settings["tex_res"]:
            command += ["--tex-res", settings["tex_res"]]
        run(command, env=env)
        released("TRELLIS")

    def reconstruct():
        mesh.unlink(missing_ok=True)
        cutout.unlink(missing_ok=True)
        print("[watch] cutout " + str(cutout), flush=True)
        settings = preset
        stage("Building textured model" + (" (%s)" % label if label else ""))
        require_memory("trellis", cfg, settings["name"])
        try:
            build(settings)
        except subprocess.CalledProcessError:
            if preset["name"] != "high":
                raise
            # A high-quality build can exhaust VRAM on a 16 GB card; finish the job anyway.
            print("[quality] The high-quality build stopped; retrying at standard quality.", flush=True)
            settings = dict(QUALITY["standard"], name="standard")
            stage("Building textured model (standard retry)")
            require_memory("trellis", cfg, settings["name"])
            build(settings)
        return settings, [mesh] + ([cutout] if cutout.is_file() else [])

    preset = checkpoint.perform("reconstruction", reconstruct)
    print("[show] model " + str(mesh), flush=True)

    def export_fbx(folder):
        fbx = folder / (job.name + ".fbx")
        run([cfg["blender"], "-b", "--factory-startup", "--python-exit-code", "1",
             "--python", APP / "transit_blender.py", "--", mesh, fbx, folder], env=env)
        if not fbx.is_file():
            raise FileNotFoundError(fbx)

    materials = job / ".materials"

    def prepare_materials():
        stage("Preparing materials and textures")
        if materials.exists():
            shutil.rmtree(materials)
        materials.mkdir()
        export_fbx(materials)
        from PIL import Image
        for texture in list(materials.glob("*.png")):
            with Image.open(texture) as baked:
                size = max(baked.size)
            if size < preset["texture"]:
                scaled = texture.with_name(texture.stem + "-4x.png")
                require_memory("upscale", cfg)
                run([cfg["upscaler"], "-i", texture, "-o", scaled, "-n", "realesrgan-x4plus",
                     "-m", Path(cfg["upscaler"]).parent / "models", "-s", 4, "-f", "png"], env=env)
                released("Real-ESRGAN")
                scaled.replace(texture)
            # Cap Unity textures at the preset size; a 2048 atlas upscaled 4x would be 8K.
            with Image.open(texture) as current:
                current.load()
                if max(current.size) > preset["texture"]:
                    ratio = preset["texture"] / max(current.size)
                    current.resize((round(current.width * ratio), round(current.height * ratio)),
                                   Image.LANCZOS).save(texture)
        return None, sorted(materials.iterdir())

    checkpoint.perform("materials", prepare_materials)

    def unity():
        stage("Preparing Unity files")
        assets = job / (job.name + "-asset")
        staging = job / ".unity-stage"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        for texture in materials.glob("*.png"):
            shutil.copy2(texture, staging / texture.name)
        export_fbx(staging)
        artifacts = sorted(staging.iterdir())
        assets.mkdir(exist_ok=True)
        for artifact in artifacts:
            artifact.replace(assets / artifact.name)
        staging.rmdir()
        return None, [assets / artifact.name for artifact in artifacts]

    checkpoint.perform("unity", unity)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--gui-parent", type=int)
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
    cfg.setdefault("cache", str(args.config.resolve().parent))
    prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", args.name or "forge")
    job = args.job or Path.cwd() / (prefix + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    job.mkdir(parents=True, exist_ok=bool(args.job))
    raw = (job / "prompt.txt").read_text(encoding="utf-8-sig") if args.job else " ".join(args.prompt)
    if not raw.strip() and args.input:
        raw = args.mode
    if not raw.strip():
        parser.error("Describe the asset to build")
    if args.gui_parent:
        if os.getpgrp() != os.getpid():
            parser.error("The GUI runner requires its own process group")

        def stop_group(*_):
            os.killpg(os.getpgrp(), signal.SIGKILL)

        signal.signal(signal.SIGTERM, stop_group)
        if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGTERM, 0, 0, 0):
            raise OSError(ctypes.get_errno(), "Could not supervise pipeline process group")
        if os.getppid() != args.gui_parent:
            stop_group()
        # Only the runner holds the pipe's write end. If the runner itself is
        # killed, this guard also stops any model or tool it left behind.
        read_end, supervisor_pipe = os.pipe()
        try:
            subprocess.Popen(
                [sys.executable, "-c",
                 "import os, signal; os.read(0, 1); os.killpg(os.getpgrp(), signal.SIGKILL)"],
                stdin=read_end, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        finally:
            os.close(read_end)

    job = job.resolve()
    source = args.input.resolve() if args.input else None
    output = args.out.resolve() if args.out else None
    persistent = args.mode == "model" or (args.mode == "rig" and source is not None and
                                          source.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    with exclusive(Path(cfg.get("cache", DATA)) / "gpu.lock") as fd:
        GPU_LOCK = (fd,)
        checkpoint = None
        if persistent:
            metadata = job / "prompt-metadata.json"
            original = json.loads(metadata.read_text(encoding="utf-8"))["original"] if metadata.exists() else raw.strip()
            inputs = {"prompt": raw.strip(), "original_prompt": original, "source": str(source) if source else None,
                      "source_sha256": digest(source) if source else None, "mode": args.mode,
                      "output": str(output) if output else None, "seed": args.seed, "quality": args.quality,
                      "resolution": args.resolution, "steps": args.steps,
                      "subject_download": cfg.get("subjectDownload", True),
                      "models": {"subject": MODEL, "subject_revision": cfg.get("subjectRevision", "main"),
                                 "image": {"id": "black-forest-labs/FLUX.1-schnell", "path": cfg["flux"]},
                                 "reconstruction": {"id": "ilintar/trellis2-gguf", "path": cfg["models"]},
                                 "runtime_revisions": cfg.get("modelRevisions", {})},
                      "configuration": {key: cfg.get(key) for key in
                                        ("trellis", "blender", "upscaler", "vulkanGPU", "unirig", "version")}}
            checkpoint = Checkpoint(job, inputs)
        try:
            process(job, raw.strip(), args.mode, cfg, output, args.resolution, args.steps, args.seed,
                    source, args.quality, checkpoint)
        except Paused:
            sys.exit(PAUSED_EXIT)
        except Exception as exc:
            if checkpoint:
                checkpoint.save(state="failed", error=str(exc))
            raise
        if checkpoint:
            checkpoint.save(state="done", current=None, error=None)
