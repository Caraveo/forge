---
title: Before you install
---

:::danger
**Do not install FORGE on your main computer unless you know what you are doing.** FORGE installs a private Python/ROCm runtime, downloads large AI models, and uses substantial GPU memory, system memory and disk space.
:::

## What FORGE changes on your PC

| Where | What | Removed on uninstall? |
| --- | --- | --- |
| `%LOCALAPPDATA%\Programs\FORGE` | The app (about 18 small files) | Yes |
| Start menu | A **FORGE** shortcut | Yes |
| `%LOCALAPPDATA%\FORGE-Data\runtime` | Private Python, ROCm PyTorch, Blender, trellis.cpp, Real-ESRGAN, UniRig and the chat model | Yes |
| `%LOCALAPPDATA%\FORGE-Data\models` | FLUX.1-schnell and TRELLIS.2 weights | **No**, kept so a reinstall doesn't download them again |
| `Documents\FORGE` | Your projects | **No** |

FORGE installs for your Windows account only and doesn't need administrator rights. It doesn't replace or modify Python, drivers or other AI tools you already have.

## Plan for

* **Disk:** about 75 GB once fully set up, plus your projects. Keep 100 GB free.
* **Time:** first setup downloads tens of gigabytes. A standard 3D build takes several minutes; high quality takes considerably longer.
* **GPU:** a build uses most of your GPU's memory, so close games and other GPU-heavy apps while FORGE works.
* **One-time sign-in:** a Hugging Face account that has accepted the FLUX.1-schnell license (see [Install](../../getting-started/install/)).

## Commercial use

Code, model weights and generated output can each have different license terms. **Read the license of every project and model** before you distribute or sell anything made with FORGE. See [Licenses](../licenses/).
