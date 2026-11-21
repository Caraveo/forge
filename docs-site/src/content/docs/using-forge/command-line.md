---
title: Command line
---

FORGE's tools also run from a terminal. They're installed in `%LOCALAPPDATA%\Programs\FORGE`:

```
cd /d "%LOCALAPPDATA%\Programs\FORGE"
```

| Command | Does |
| --- | --- |
| `forge.cmd a small forest cat` | Builds a 3D model |
| `generate.cmd a wooden toy boat --out boat.png` | Paints an image |
| `enhance.cmd a small forest cat` | Prints the enhanced prompt only |
| `background.cmd photo.png --out cutout.png` | Removes the background |
| `upscale.cmd image.png --out larger.png` | Upscales 4× |
| `rig.cmd model.glb model-rigged.fbx` | Rigs a model |

## Options

| Option | For | Meaning |
| --- | --- | --- |
| `--out PATH` | `forge`, `generate`, `background`, `upscale` | Where to write the main result |
| `--quality auto\|draft\|standard\|high` | `forge`, `generate` | Quality preset; `auto` (default) reads words like *super* from the prompt |
| `--res 512\|1024` | `forge` | Geometry resolution, overriding the preset |
| `--steps N` | `forge`, `generate` | Sampler steps, overriding the preset |
| `--seed N` | `forge`, `generate` | Random seed (default 42) |

Without `--out`, a command creates a job folder in the current directory, named like `forge_<date>_<time>`. Run it from a folder you don't mind filling.

Command-line jobs don't ask for a project name and don't appear in the app.
