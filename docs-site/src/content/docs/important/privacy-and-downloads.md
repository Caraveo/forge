---
title: Privacy and downloads
---

## Everything runs on your PC

Prompts, images, models and chat stay on your computer. FORGE generates, sculpts, rigs and chats with local models; it doesn't send your prompts or files to any online service.

* The chat model can only reply with text. It can't run commands, start jobs or touch your files. Builds start only when you send a command or click a button.
* Hugging Face telemetry is disabled for every download FORGE makes, and generation runs with Hugging Face set to offline.

## What FORGE downloads, and from where

FORGE downloads only during setup (and when it resumes an unfinished setup):

| Source | What |
| --- | --- |
| [FORGE runtime-v0.01](https://github.com/Caraveo/forge/releases/tag/runtime-v0.01) on GitHub | CPython, uv, the ROCm and PyTorch wheels, trellis.cpp, Blender, Real-ESRGAN |
| [FORGE runtime-v0.04](https://github.com/Caraveo/forge/releases/tag/runtime-v0.04) on GitHub | Portable UniRig runtimes (code and Python only) |
| Hugging Face | Model weights: FLUX.1-schnell, TRELLIS.2 GGUFs, UniRig checkpoints, OPT-350m config, Qwen3-0.6B |

Runtime code comes from the FORGE project's own releases, so setup still works if the original project sites are offline. Every runtime part is checked against a SHA-256 checksum before it's used. Model weights are fetched from Hugging Face at pinned revisions.

Your Hugging Face sign-in is used only to download the gated FLUX.1-schnell model.
