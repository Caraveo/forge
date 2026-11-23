#!/usr/bin/env python3
"""Provision the FORGE Linux runtime.

The Windows build downloaded a private Python + ROCm environment, TRELLIS,
Blender, Real-ESRGAN, FLUX, TRELLIS weights and the UniRig/chat models. This
script does the same with Linux-native pieces, using uv for the two Python
runtimes (3.12 for PySide6/ROCm and 3.11 for Blender's bpy wheel).

Everything is installed under ``~/.local/share/FORGE-Data`` unless
FORGE_DATA_HOME or --runtime is set. The script is resumable: each phase has a
marker or a binary probe, so an interrupted download can be retried safely.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
VERSION = "0.15.0"
UV_VERSION = "0.13.9"
UV_URL = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz"
UV_SHA256 = "a7fbaff2b9a271d85c1bdb540941090fd1ce011797b4abeb48e4dcd39c2471d5"
TRELLIS_URL = "https://github.com/pwilkin/trellis.cpp/releases/download/v0.8.1/trellis-vulkan-linux-x64.tar.gz"
TRELLIS_SHA256 = "8c2ed7f76ab9f09d3e24dae82b1a52a75d308e853bdfd289e26d57b1f422f33b"
UPSCALE_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip"
UPSCALE_SHA256 = "e5aa6eb131234b87c0c51f82b89390f5e3e642b7b70f2b9bbe95b6a285a40c96"
BLENDER_VERSION = "4.2.15"
BLENDER_URL = f"https://download.blender.org/release/Blender4.2/blender-{BLENDER_VERSION}-linux-x64.tar.xz"
BLENDER_SHA256 = "b9dcc1d06861529779e7faf8d82c9dd3563443dfb1eb14212424c8c40b77074e"

FLUX_REPO = "black-forest-labs/FLUX.1-schnell"
FLUX_REVISION = "169573f54945f633efbe126a40a5676b4228363c"
FLUX_FILES = [
    "model_index.json", "scheduler/*", "tokenizer*/*",
    "text_encoder*/*.json", "text_encoder*/*.safetensors",
    "transformer/*.json", "transformer/*.safetensors",
    "vae/*.json", "vae/*.safetensors",
]
TRELLIS_REPO = "ilintar/trellis2-gguf"
TRELLIS_REVISION = "a57397bd3d351599d9729fc144b3f87c3f87d65b"
TRELLIS_FILES = [
    "birefnet.gguf", "dinov3.gguf", "ss_flow.gguf", "ss_dec.gguf",
    "shape_flow_512.gguf", "shape_flow_1024.gguf", "shape_dec.gguf",
    "tex_flow_512.gguf", "tex_flow_1024.gguf", "tex_dec.gguf",
]
QWEN_REPO = "Qwen/Qwen3-0.6B"
QWEN_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
QWEN_FILES = [
    "config.json", "generation_config.json", "LICENSE", "merges.txt",
    "model.safetensors", "tokenizer.json", "tokenizer_config.json", "vocab.json",
]
UNIRIG_REPO = "VAST-AI/UniRig"
UNIRIG_REVISION = "36842e2b5947e9e60f89275b83208c8e74071c63"
UNIRIG_FILES = [
    "skeleton/articulation-xl_quantization_256/model.ckpt",
    "skin/articulation-xl/model.ckpt",
]
OPT_REPO = "facebook/opt-350m"
OPT_REVISION = "08ab08cc4b72ff5593870b5d527cf4230323703c"

REQUIREMENTS = [
    "PySide6==6.12.0",
    "diffusers==0.35.2",
    "transformers==4.51.3",
    "tokenizers==0.21.4",
    "huggingface_hub==0.34.4",
    "safetensors==0.8.0",
    "accelerate==1.10.1",
    "Pillow>=10.4",
    "rich>=13.9",
    "numpy==1.26.4",
    "scipy>=1.13",
    "trimesh>=4.5",
    "fast-simplification==0.1.12",
    "python-box>=7.2",
    "PyYAML>=6.0",
    "tqdm>=4.66",
    "einops>=0.8",
    "omegaconf>=2.3",
    "addict>=2.4",
    "timm==1.0.15",
    "lightning==2.5.2",
    "pyrender==0.1.45",
    "open3d==0.19.0",
    "psutil>=6.0",
    "requests>=2.32",
]


class SetupError(RuntimeError):
    pass


def data_home() -> Path:
    override = os.environ.get("FORGE_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return (base / "FORGE-Data").resolve()


def documents() -> Path:
    override = os.environ.get("FORGE_OUTPUT")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "Documents"


_LOG_FILE = None


def log(message: str = "") -> None:
    print(message, flush=True)
    if _LOG_FILE is not None:
        _LOG_FILE.write(message + "\n")
        _LOG_FILE.flush()


def human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path, sha256: str | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size > 0:
        if not sha256 or file_sha256(destination) == sha256:
            return
    partial = destination.with_suffix(destination.suffix + ".partial")
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "FORGE-Linux/" + VERSION})
            with urllib.request.urlopen(request, timeout=60) as response:
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                started = time.monotonic()
                with partial.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        done += len(chunk)
                        if total and (done == total or done % (64 * 1024 * 1024) < len(chunk)):
                            speed = done / max(0.1, time.monotonic() - started)
                            log(f"  {destination.name}: {100 * done / total:5.1f}%  "
                                f"{human(done)} / {human(total)}  ({human(speed)}/s)")
            if sha256 and file_sha256(partial) != sha256:
                partial.unlink(missing_ok=True)
                raise SetupError(f"Checksum failed for {destination.name}")
            partial.replace(destination)
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            partial.unlink(missing_ok=True)
            if attempt == 3:
                raise SetupError(f"Could not download {url}: {exc}") from exc
            log(f"  download retry {attempt}/3: {exc}")
            time.sleep(2 * attempt)


def extract_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as bundle:
        root = destination.resolve()
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if root not in target.parents and target != root:
                raise SetupError("Archive contains an unsafe path: " + member.name)
        bundle.extractall(destination)


def extract_zip(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        root = destination.resolve()
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if root not in target.parents and target != root:
                raise SetupError("Archive contains an unsafe path: " + member.filename)
        bundle.extractall(destination)


def run(command: list[str | Path], env: dict[str, str] | None = None,
        capture: bool = False) -> subprocess.CompletedProcess:
    log("  $ " + " ".join(str(part) for part in command))
    return subprocess.run([str(part) for part in command], env=env,
                          text=True, capture_output=capture, check=False)


def require(result: subprocess.CompletedProcess, message: str) -> None:
    if result.returncode != 0:
        detail = ((result.stdout or "") + (result.stderr or "")).strip()
        raise SetupError(message + (("\n" + detail[-4000:]) if detail else ""))


def ensure_uv(runtime: Path) -> Path:
    found = shutil.which("uv")
    if found:
        return Path(found)
    target = runtime / "uv" / "uv"
    if target.is_file():
        return target
    log("Installing uv (private Python manager)...")
    archive = runtime / "uv.tar.gz"
    download(UV_URL, archive, sha256=UV_SHA256)
    staging = runtime / "uv-installing"
    shutil.rmtree(staging, ignore_errors=True)
    extract_tar(archive, staging)
    binary = next(staging.rglob("uv"), None)
    if binary is None:
        raise SetupError("uv was not found in its archive.")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, target)
    target.chmod(0o755)
    shutil.rmtree(staging, ignore_errors=True)
    archive.unlink(missing_ok=True)
    return target


def python_ok(python: Path, imports: str) -> bool:
    if not python.is_file():
        return False
    result = run([python, "-c", imports], capture=True)
    return result.returncode == 0


def ensure_env(runtime: Path, uv: Path, with_flux: bool) -> Path:
    env = runtime / "env"
    python = env / "bin" / "python"
    marker = env / ".complete-linux"
    if python_ok(python, "import torch, diffusers, transformers, PySide6") and marker.is_file():
        log("Python environment already installed.")
        return python
    if not python.is_file():
        log("Creating the Python 3.12 environment...")
        result = run([uv, "venv", "--python", "3.12", env])
        require(result, "Could not create the Python 3.12 environment.")
    if not python.is_file():
        raise SetupError("The Python 3.12 environment has no interpreter.")
    if not python_ok(python, "import torch; assert torch.version.hip and torch.cuda.is_available()"):
        log("Installing PyTorch for ROCm 7.2...")
        result = run([uv, "pip", "install", "--python", python,
                      "torch==2.11.0", "torchvision==0.26.0",
                      "--index-url", "https://download.pytorch.org/whl/rocm7.2"])
        require(result, "PyTorch ROCm installation failed.")
    log("Installing FORGE Python packages...")
    result = run([uv, "pip", "install", "--python", python, *REQUIREMENTS])
    require(result, "FORGE Python package installation failed.")
    marker.write_text(VERSION + "\n", encoding="utf-8")
    return python


def ensure_subject_runtime(runtime: Path, uv: Path, python: Path) -> None:
    """Keep Qwen3-VL's newer Transformers stack isolated from FLUX and chat."""
    target = runtime / "subject-deps"
    marker = target / ".qwen3-vl-4.57.6"
    if marker.is_file():
        return
    result = run([uv, "pip", "install", "--python", python, "--target", target,
                  "--upgrade", "--no-deps", "transformers==4.57.6", "tokenizers==0.22.1"])
    if result.returncode:
        log("The subject assistant could not be installed. Existing generation remains available.")
        return
    marker.touch()


def ensure_unirig_cpu(runtime: Path, uv: Path) -> Path:
    env = runtime / "unirig" / "python311"
    python = env / "bin" / "python"
    marker = env / ".complete-linux"
    if python_ok(python, "import bpy, trimesh, fast_simplification") and marker.is_file():
        log("UniRig Blender Python environment already installed.")
        return python
    if not python.is_file():
        log("Creating the Python 3.11 Blender environment...")
        result = run([uv, "venv", "--python", "3.11", env])
        require(result, "Could not create the Blender Python 3.11 environment.")
    log("Installing bpy and UniRig extraction packages...")
    result = run([uv, "pip", "install", "--python", python,
                  "bpy==4.2.0", "numpy==1.26.4", "trimesh>=4.5", "fast-simplification==0.1.12",
                  "scipy>=1.13", "tqdm>=4.66", "python-box>=7.2", "PyYAML>=6.0"])
    require(result, "UniRig Blender Python packages failed to install.")
    marker.write_text(VERSION + "\n", encoding="utf-8")
    return python


def find_binary(root: Path, name: str) -> Path | None:
    if (root / name).is_file():
        return root / name
    for candidate in root.rglob(name):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def ensure_trellis(runtime: Path) -> Path:
    root = runtime / "tools" / "trellis"
    binary = find_binary(root, "trellis-cli")
    if binary:
        return binary
    log("Installing TRELLIS.cpp (Vulkan)...")
    archive = runtime / "trellis.tar.gz"
    download(TRELLIS_URL, archive, sha256=TRELLIS_SHA256)
    extract_tar(archive, root)
    archive.unlink(missing_ok=True)
    binary = find_binary(root, "trellis-cli")
    if binary is None:
        raise SetupError("trellis-cli was not found in its archive.")
    binary.chmod(0o755)
    return binary


def ensure_upscaler(runtime: Path) -> Path:
    root = runtime / "tools" / "upscale"
    binary = find_binary(root, "realesrgan-ncnn-vulkan")
    if binary:
        return binary
    log("Installing Real-ESRGAN (Vulkan)...")
    archive = runtime / "upscale.zip"
    download(UPSCALE_URL, archive, sha256=UPSCALE_SHA256)
    extract_zip(archive, root)
    archive.unlink(missing_ok=True)
    binary = find_binary(root, "realesrgan-ncnn-vulkan")
    if binary is None:
        raise SetupError("realesrgan-ncnn-vulkan was not found in its archive.")
    binary.chmod(0o755)
    return binary


def ensure_blender(runtime: Path) -> Path:
    root = runtime / "tools" / "blender"
    binary = find_binary(root, "blender")
    if binary:
        return binary
    log(f"Installing Blender {BLENDER_VERSION} LTS...")
    archive = runtime / "blender.tar.xz"
    download(BLENDER_URL, archive, sha256=BLENDER_SHA256)
    extract_tar(archive, root)
    archive.unlink(missing_ok=True)
    binary = find_binary(root, "blender")
    if binary is None:
        raise SetupError("Blender was not found in its archive.")
    binary.chmod(0o755)
    return binary


def snapshot(python: Path, repo: str, revision: str, files: list[str],
             destination: Path, env: dict[str, str]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    missing = [name for name in files if not any(destination.glob(name))]
    if not missing:
        return
    log(f"Downloading {repo} from Hugging Face...")
    code = ("import sys; from huggingface_hub import snapshot_download; "
            "snapshot_download(sys.argv[1], revision=sys.argv[2], "
            "allow_patterns=sys.argv[3].split(','), local_dir=sys.argv[4])")
    result = run([python, "-c", code, repo, revision, ",".join(files), destination], env=env)
    require(result, f"Downloading {repo} failed.")


def ensure_models(runtime: Path, python: Path, with_flux: bool, skip_models: bool) -> dict:
    paths = {
        "models": runtime / "models" / "trellis",
        "flux": runtime / "models" / "flux",
        "chat": runtime / "chat",
        "unirig": runtime / "unirig",
    }
    env = dict(os.environ)
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        env.pop(key, None)
    env.update({
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "TOKENIZERS_PARALLELISM": "false",
    })
    if skip_models:
        log("Skipping model weights (--skip-models).")
        return paths

    snapshot(python, TRELLIS_REPO, TRELLIS_REVISION, TRELLIS_FILES, paths["models"], env)

    chat_marker = paths["chat"] / ".complete-linux"
    if not chat_marker.is_file():
        snapshot(python, QWEN_REPO, QWEN_REVISION, QWEN_FILES, paths["chat"], env)
        chat_marker.write_text(VERSION + "\n", encoding="utf-8")
    else:
        log("Chat weights already installed.")

    unirig_marker = paths["unirig"] / ".complete-linux"
    if not unirig_marker.is_file():
        experiments = paths["unirig"] / "UniRig-main" / "experiments"
        opt = paths["unirig"] / "UniRig-main" / "models" / "opt"
        snapshot(python, UNIRIG_REPO, UNIRIG_REVISION, UNIRIG_FILES, experiments, env)
        snapshot(python, OPT_REPO, OPT_REVISION, ["config.json"], opt, env)
        unirig_marker.write_text(VERSION + "\n", encoding="utf-8")
    else:
        log("UniRig weights already installed.")

    if with_flux:
        log("Downloading FLUX.1-schnell (gated; requires an accepted license)...")
        try:
            snapshot(python, FLUX_REPO, FLUX_REVISION, FLUX_FILES, paths["flux"], env)
        except SetupError as exc:
            log("")
            log("FLUX was not downloaded. Text-to-model needs it, but attached images work now.")
            log("Accept the license at https://huggingface.co/black-forest-labs/FLUX.1-schnell")
            log("then run:  hf auth login  (or set HF_TOKEN)  and  ./install.sh --with-flux")
            log(str(exc).splitlines()[0])
        else:
            (paths["flux"] / ".complete-linux").write_text(VERSION + "\n", encoding="utf-8")
    else:
        log("Skipping FLUX.1-schnell (gated). Run ./install.sh --with-flux after accepting its license.")
    return paths


def hardware_report() -> None:
    log("Hardware:")
    log(f"  CPU: {platform.processor() or platform.machine()}")
    try:
        mem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
        log(f"  RAM: {mem:.1f} GiB")
    except (ValueError, OSError):
        pass
    gpu = None
    for vendor in sorted(Path("/sys/class/drm").glob("card*/device/vendor")):
        try:
            if vendor.read_text().strip().lower() == "0x1002":
                card = vendor.parent
                name = (card / "product_name")
                vram = (card / "mem_info_vram_total")
                label = name.read_text().strip() if name.is_file() else "AMD GPU"
                size = f" ({int(vram.read_text()) / 1024**3:.1f} GiB VRAM)" if vram.is_file() else ""
                gpu = label + size
                break
        except OSError:
            pass
    log(f"  GPU: {gpu or 'no AMD GPU detected'}")
    log(f"  KFD: {'present' if Path('/dev/kfd').exists() else 'missing'}")
    log("")


def copy_unirig_source(runtime: Path) -> None:
    source = PROJECT / "runtime" / "unirig" / "UniRig-main"
    target = runtime / "unirig" / "UniRig-main"
    if not source.is_dir():
        if target.is_dir():
            return
        raise SetupError("UniRig source is missing from the FORGE installation.")
    log("Copying UniRig source...")
    shutil.copytree(source, target, dirs_exist_ok=True)


def write_config(runtime: Path, python: Path, tools: dict, models: dict) -> Path:
    output = documents() / "FORGE"
    output.mkdir(parents=True, exist_ok=True)
    path = runtime / "config.json"
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    if not isinstance(previous, dict):
        previous = {}
    config = {
        "python": str(python),
        "enhancerPython": str(python),
        "flux": str(models["flux"]),
        "models": str(models["models"]),
        "trellis": str(tools["trellis"]),
        "blender": str(tools["blender"]),
        "upscaler": str(tools["upscale"]),
        "output": str(output),
        "chat": str(models["chat"]),
        "unirig": str(models["unirig"]),
        "vulkanGPU": 0,
        "version": VERSION,
        "modelRevisions": {"flux": FLUX_REVISION, "trellis": TRELLIS_REVISION, "unirig": UNIRIG_REVISION},
        **{key: previous[key] for key in ("subjectRevision", "subjectDownload")
           if key in previous},
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the FORGE Linux runtime")
    parser.add_argument("--runtime", type=Path, default=None,
                        help="runtime directory (default: ~/.local/share/FORGE-Data/runtime)")
    parser.add_argument("--with-flux", action="store_true",
                        help="download the gated FLUX.1-schnell weights")
    parser.add_argument("--skip-models", action="store_true",
                        help="install code and tools only, without model weights")
    parser.add_argument("--subject-only", action="store_true",
                        help="add the Qwen3-VL dependencies to an existing installation")
    parser.add_argument("--check", action="store_true", help="print hardware information and exit")
    args = parser.parse_args()

    if args.check:
        hardware_report()
        return 0

    runtime = (args.runtime or data_home() / "runtime").expanduser().resolve()
    data = runtime.parent
    data.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / ".forge-owned").touch()
    log_path = data / "setup.log"
    global _LOG_FILE
    _LOG_FILE = log_path.open("a", encoding="utf-8")

    log("")
    log("FORGE " + VERSION + " runtime setup")
    log("Runtime: " + str(runtime))
    log("")
    hardware_report()
    log("This setup installs under your home directory and does not modify "
        "your existing AI projects or system Python.")
    log("")

    try:
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
            raise SetupError("FORGE Linux requires a 64-bit x86 Linux system.")
        if not Path("/dev/kfd").exists():
            log("Warning: /dev/kfd is missing. ROCm inference will not work until the amdgpu kernel driver is available.")
        if args.subject_only:
            python = runtime / "env" / "bin" / "python"
            if not python.is_file():
                raise SetupError("Install the FORGE runtime first.")
            ensure_subject_runtime(runtime, ensure_uv(runtime), python)
            return 0 if (runtime / "subject-deps" / ".qwen3-vl-4.57.6").is_file() else 1
        log("Preparing directories...")
        for folder in ("tools", "models", "tmp", "chat", "unirig"):
            (runtime / folder).mkdir(parents=True, exist_ok=True)
        copy_unirig_source(runtime)

        uv = ensure_uv(runtime)
        python = ensure_env(runtime, uv, args.with_flux)
        ensure_subject_runtime(runtime, uv, python)
        cpu_python = ensure_unirig_cpu(runtime, uv)
        log("Blender Python: " + str(cpu_python))

        tools = {
            "trellis": ensure_trellis(runtime),
            "upscale": ensure_upscaler(runtime),
            "blender": ensure_blender(runtime),
        }
        for name, path in tools.items():
            log(f"{name}: {path}")

        models = ensure_models(runtime, python, args.with_flux, args.skip_models)
        config = write_config(runtime, python, tools, models)
        log("")
        log("Runtime ready: " + str(config))
        log("")
        log("Start FORGE with:  " + str(PROJECT.parent / "forge"))
        log("CLI examples:      " + str(PROJECT.parent / "forge-cli") + " generate \"a red apple\"")
        if not (models["flux"] / "transformer").is_dir():
            log("")
            log("Text-to-model is waiting for FLUX.1-schnell. Attached images already work.")
            log("Accept https://huggingface.co/black-forest-labs/FLUX.1-schnell then run:")
            log("  hf auth login && ./install.sh --with-flux")
        return 0
    except SetupError as exc:
        log("")
        log("SETUP FAILED: " + str(exc))
        return 1
    except KeyboardInterrupt:
        log("")
        log("Setup cancelled.")
        return 130
    finally:
        if _LOG_FILE is not None:
            _LOG_FILE.close()
            _LOG_FILE = None


if __name__ == "__main__":
    sys.exit(main())
