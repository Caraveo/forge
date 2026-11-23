"""Two-stage UniRig inference without PowerShell.

The Windows build used a drive letter to keep the ROCm environment's paths
short. On Linux paths are not limited, so this script calls the same two Python
runtimes directly: Blender's Python 3.11 extracts the mesh and exports the FBX,
while the ROCm Python 3.12 environment runs the skeleton and skin models.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path


def run(command: list[str], cwd: Path, env: dict[str, str], label: str) -> None:
    print(f"[rig] {label}", flush=True)
    print("[rig] " + " ".join(str(part) for part in command), flush=True)
    result = subprocess.run([str(part) for part in command], cwd=str(cwd), env=env)
    if result.returncode != 0:
        raise RuntimeError(f"{label} stopped with exit code {result.returncode}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rig a mesh with UniRig on the AMD GPU")
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unirig", type=Path, default=None, help="UniRig runtime directory")
    parser.add_argument("--cpu-python", type=Path, default=None)
    parser.add_argument("--gpu-python", type=Path, default=None)
    args = parser.parse_args()

    mesh = args.mesh.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not mesh.is_file():
        raise FileNotFoundError(f"Mesh not found: {mesh}")
    if output.suffix.lower() != ".fbx":
        raise ValueError("The output path must end in .fbx.")
    if output.exists():
        raise FileExistsError(f"Output already exists. Choose a new FBX path: {output}")

    root = (args.unirig or Path(os.environ.get("FORGE_DATA", "")) / "runtime" / "unirig").expanduser().resolve()
    source = root / "UniRig-main"
    cpu_python = (args.cpu_python or root / "python311" / "bin" / "python").expanduser().resolve()
    gpu_python = (args.gpu_python or sys.executable).expanduser().resolve()
    if not (source / "run.py").is_file():
        raise FileNotFoundError(f"UniRig source not found: {source}")
    if not cpu_python.is_file():
        raise FileNotFoundError(f"Blender/bpy Python runtime not found: {cpu_python}")
    if not gpu_python.is_file():
        raise FileNotFoundError(f"ROCm Python runtime not found: {gpu_python}")

    work = root / "tmp" / ("gpu-rig-" + uuid.uuid4().hex)
    input_data = work / "input"
    ar_output = work / "ar"
    skin_output = work / "skin"
    for folder in (input_data, ar_output, skin_output, output.parent):
        folder.mkdir(parents=True, exist_ok=True)

    model_name = mesh.stem
    input_model_data = input_data / model_name / "raw_data.npz"
    skeleton_npz = ar_output / model_name / "predict_skeleton.npz"
    skin_npz = skin_output / model_name / "predict_skin.npz"

    lock_path = root / "tmp" / "forge-unirig.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = lock_path.open("w")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError("UniRig is already processing another model.")

    base_env = dict(os.environ)
    base_env.update({
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "PYTHONUNBUFFERED": "1",
        "TOKENIZERS_PARALLELISM": "false",
    })
    cpu_env = dict(base_env, UNIRIG_ROCM="0", UNIRIG_CPU="0")
    gpu_env = dict(base_env, UNIRIG_ROCM="1", UNIRIG_CPU="0",
                   PYOPENGL_PLATFORM="egl", MPLBACKEND="Agg")
    try:
        stamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        run([
            str(cpu_python), "-m", "src.data.extract",
            "--config=configs/data/quick_inference.yaml",
            "--require_suffix=obj,fbx,FBX,dae,glb,gltf,vrm",
            "--faces_target_count=50000", "--num_runs=1", "--force_override=true",
            "--id=0", f"--time={stamp}", f"--input={mesh}", f"--output_dir={input_data}",
        ], source, cpu_env, "Extracting mesh")
        if not input_model_data.is_file():
            raise RuntimeError("Mesh extraction produced no raw_data.npz.")

        run([
            str(gpu_python), "-c",
            "import torch; assert torch.version.hip and torch.cuda.is_available(), "
            "'ROCm GPU unavailable'; x=torch.ones(4,device='cuda'); "
            "print('GPU preflight:',torch.cuda.get_device_name(0),'| tensor:',(x+1).sum().item())",
        ], source, gpu_env, "Checking the AMD GPU")

        run([
            str(gpu_python), "run.py",
            "--task=configs/task/quick_inference_skeleton_articulationxl_ar_256_rocm.yaml",
            "--seed=12345", f"--input={mesh}", f"--npz_dir={input_data}", f"--output_dir={ar_output}",
        ], source, gpu_env, "Predicting skeleton")
        if not skeleton_npz.is_file():
            raise RuntimeError("Skeleton inference produced no prediction NPZ.")

        run([
            str(gpu_python), "run.py",
            "--task=configs/task/quick_inference_unirig_skin_rocm.yaml",
            "--seed=12345", f"--input={mesh}", f"--npz_dir={ar_output}", f"--output_dir={skin_output}",
            "--data_name=predict_skeleton.npz",
        ], source, gpu_env, "Predicting skin weights")
        if not skin_npz.is_file():
            raise RuntimeError("Skin inference produced no prediction NPZ.")

        run([
            str(cpu_python), "tools/export_rocm_fbx.py",
            f"--source={input_model_data}", f"--skeleton={skeleton_npz}",
            f"--skin={skin_npz}", f"--output={output}",
        ], source, cpu_env, "Exporting FBX")
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("Blender did not create the FBX output.")
        print(f"Created rigged FBX: {output} ({output.stat().st_size:,} bytes)", flush=True)
        return 0
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"[rig] {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
