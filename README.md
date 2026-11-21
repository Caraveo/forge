# FORGE ANYTHING ON AMD/AMD

![FORGE Anything on AMD/AMD](docs/banner.png)

[![Windows release](https://github.com/Caraveo/forge/actions/workflows/release.yml/badge.svg)](https://github.com/Caraveo/forge/actions/workflows/release.yml)
[![Latest release](https://img.shields.io/github/v/release/Caraveo/forge?label=release)](https://github.com/Caraveo/forge/releases/latest)
[![License](https://img.shields.io/github/license/Caraveo/forge)](LICENSE)

**From a thought to a game ready 3D asset.** Describe it once. FORGE enhances the prompt, creates the image, shapes a textured model on your Radeon GPU, and prepares files for Unity. Watch the work move through the queue, then orbit and zoom the finished model right in the conversation.

### Dream it. Describe it. Forge it.

Private, local generation built around AMD hardware and Vulkan acceleration. Type `forge a friendly golden dog named Buddy` and follow the build from first image to Unity ready model. Or type `generate a wooden toy boat` to create an image.

> **WARNING: DO NOT INSTALL ON YOUR MAIN COMPUTER UNLESS YOU KNOW WHAT YOU ARE DOING.** FORGE installs a private Python/ROCm runtime, downloads large AI models, and uses substantial GPU memory, system memory, and disk space. Review the requirements and installation behavior below before proceeding.

FORGE turns a description into a textured 3D game asset on your Windows PC. Use forge, build, make, or mold followed by a model description and press Enter. Drag the finished model to orbit, zoom with Ctrl + wheel, or reset the camera. Scroll through the conversation to revisit earlier results.

![FORGE v0.04 with a textured character model and an attached reference image](docs/screenshot.png)

## Install v0.04

Download **[FORGE-v0.04-Setup.exe](https://github.com/Caraveo/forge/releases/download/v0.04/FORGE-v0.04-Setup.exe)** from the [v0.04 release](https://github.com/Caraveo/forge/releases/tag/v0.04). Setup checks your hardware, installs or repairs the app, and provisions its private runtime. You can also download and install the [MSI](https://github.com/Caraveo/forge/releases/download/v0.04/FORGE-v0.04-x64.msi) directly, then launch **FORGE** from Start to provision the runtime.

Requires Windows x64, an AMD CPU, a ROCm-compatible Radeon GPU with **16 GB dedicated VRAM**, **32 GB system RAM**, an AMD driver with Vulkan support, and at least **100 GB free storage** for the private runtime, downloaded models, caches, and temporary generation files. The check allows 256 MiB of driver-reserved VRAM on a nominal 16 GB board.

The EXE provisions private Python 3.12 and AMD ROCm PyTorch 7.2.1 under **%LOCALAPPDATA%\FORGE-Data\runtime**. With direct MSI installation, provisioning starts on first launch. Runtime code is downloaded from the [FORGE runtime release](https://github.com/Caraveo/forge/releases/tag/runtime-v0.01): CPython, uv, the ROCm and PyTorch wheels, trellis.cpp, Blender, and Real-ESRGAN. That release is the copy FORGE installs, so setup still works if the original project sites are offline. Model weights are the exception. FLUX.1-schnell and the TRELLIS.2 GGUFs still come from Hugging Face. FLUX.1-schnell is gated: accept its license and sign in on this PC before the first launch. Allow several dozen GB for downloads and caches. The v0.04 setup also installs portable UniRig runtimes with their checkpoints and the Qwen3-0.6B chat model from the [FORGE runtime-v0.04 release](https://github.com/Caraveo/forge/releases/tag/runtime-v0.04), about 12 GB more. Installing over an earlier FORGE version keeps the runtime that is already there. Chat runs on the CPU. Generation and rigging use local weights. If setup fails, open FORGE again to retry. See **%LOCALAPPDATA%\FORGE-Data\setup.log** for diagnostics.

## Use FORGE

- **forge**, **build**, **make**, or **mold** followed by a description creates a 3D model.
- **generate**, **create**, or **imagine** followed by a description creates an image.
- Use **+**, or drag a file onto the window, to attach a PNG, JPEG, WebP, GLB, or FBX. It appears as a chip in the message field; hover it and click the red **×** to clear it. Select an existing result to use it in another action.
- **remove background** creates a transparent PNG. **upscale** enlarges an image or texture 4x.
- **rig** runs UniRig on the selected model. With an image, FORGE builds the model first. Rigged models export as FBX.
- Ordinary messages go to the local Qwen chat model. Explicit tool commands start jobs. Chat offers image and 3D buttons when you want to act on an idea.
- **Save** exports an image or model to a location you choose. **Expand** opens a model preview that fills its resizable window.
- **Build log** shows stage changes and live process output. Jobs run one at a time.

Each installed-app job saves its prompt, log and artifacts under **Documents\FORGE**. A model build includes a source image, textured GLB and Unity asset folder containing the FBX and textures. From the app directory, use **forge.cmd**, **generate.cmd**, **enhance.cmd**, **background.cmd**, **upscale.cmd**, or **rig.cmd**. For example, run `rig.cmd model.glb model-rigged.fbx` or `upscale.cmd image.png --out larger.png`.

![Generated asset in the desktop viewer](docs/model.png)

## Uninstall

Use **Settings > Apps > Installed apps > FORGE > Uninstall**. Windows Installer removes the app, Start menu shortcut and private runtime. Generated models and downloaded weights are retained. FORGE launches on demand.

## Build from source

On x64 Windows with Python 3.12 (3.13 removed `msilib`) and .NET Framework 4.8, run `py -3.12 packaging\build.py`, then `.\packaging\check-package.ps1` in PowerShell. Each build is a Windows Installer major upgrade: it replaces any earlier FORGE version in place and keeps the private runtime. To install the local build or repair an installation that stopped during runtime setup, open `dist\FORGE-v0.04-Setup.exe`. The EXE refreshes the installed app files and retries incomplete runtime setup. For a fresh installation, you can also open `dist\FORGE-v0.04-x64.msi` and launch FORGE from Start to finish setup.

UniRig source and the AMD compatibility changes are included under `runtime/unirig`. The release installer uses the checksum-pinned `desktop/manifest-v004.json` to install its portable runtimes. Maintainers can rebuild those archives with `packaging/bundle-runtime.py` from the verified local UniRig runtimes and model caches.

Runtime and model sources include [AMD ROCm](https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/), [FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell), [trellis.cpp](https://github.com/pwilkin/trellis.cpp), [TRELLIS.2 GGUFs](https://huggingface.co/ilintar/trellis2-gguf), [Blender](https://www.blender.org/) and [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN).

## THANK YOU TO THESE AMAZING PROJECTS

FORGE is possible because of the people who build and share these tools and models.

- [PyTorch](https://github.com/pytorch/pytorch) — BSD 3-Clause
- [AMD ROCm for Windows](https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/) — review AMD's component license notices
- [FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell) — Apache 2.0 model license
- [Diffusers](https://github.com/huggingface/diffusers) — Apache 2.0
- [Transformers](https://github.com/huggingface/transformers) — Apache 2.0
- [trellis.cpp](https://github.com/pwilkin/trellis.cpp) — MIT
- [TRELLIS.2 GGUF weights](https://huggingface.co/ilintar/trellis2-gguf) — review the model repository's license and terms
- [Blender](https://www.blender.org/) — GNU GPL 3.0 or later
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — BSD 3-Clause
- [UniRig](https://github.com/VAST-AI-Research/UniRig) — MIT
- [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) — Apache 2.0
- [uv](https://github.com/astral-sh/uv) — MIT or Apache 2.0

> **PLEASE READ THE COMMERCIAL LICENSES FOR EACH PROJECT.** Code, model weights, and generated output can have different license terms. Verify the current terms for every dependency and model, and confirm they fit your intended commercial use before distributing or selling anything made with FORGE.
