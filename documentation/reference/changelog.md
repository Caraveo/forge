# Versions and changelog

The current version is **v0.05**. It's shown in the window title. Download any version from [GitHub Releases](https://github.com/Caraveo/forge/releases).

Each version installs over the previous one and keeps your private runtime. Installing an older version over a newer one is refused.

## v0.05 — November 21, 2026

**Building feels like a conversation.**

* **Project names.** Pick a suggested name or type your own before a build starts. It labels the result and its folder.
* **Quality from your words.** *super*, *premium*, *high quality* and similar words build at 1024 geometry with 20 steps, a 2K atlas and 4K Unity textures; *draft* builds faster. Falls back to standard quality if the GPU runs short. See [Quality](../using-forge/quality.md).
* **Narrated builds.** The conversation shows the prompt, reference image, cutout and model as each is ready.
* **Job cards** above the message field, with state, stage, elapsed time and **Cancel**.
* **Messaging layout.** Your messages on the right, FORGE's on the left. Chat answers during builds.
* **Smarter attachments.** Suggested next steps (Preview, Rig, Build 3D, Remove background, Upscale). TXT files become your prompt; other file types are refused.
* **High-quality images** upscaled 4× to 3072 px.
* Result actions, including **Open folder**, on one compact row. Build log hidden until **Ctrl + L**.

**Fixed**

* Saying "hi" could start a project named after the greeting.
* Running Setup over an installed copy of the same version could fail with error 1603. *(The v0.05 installers were replaced with this fix on November 21.)*

## v0.04 — November 21, 2026

**Chat, rigging, upscaling and background removal.**

* Local chat with Qwen3-0.6B, offering image and 3D buttons for ideas.
* Rigging with UniRig on the GPU, exported as FBX.
* Upscale 4× and remove background.
* **mold** starts a 3D model; attachments with **+** or drag and drop; **Save**, **Select** and **Expand** on results.
* New design and the FORGE icon. New `upscale.cmd`, `background.cmd` and `rig.cmd`.

**Fixed:** upgrade failures (error 1625/1603), a setup crash on Windows' 260-character path limit, FORGE not opening when only the new tools failed to install, and command-line `--out` errors.

Introduced the [runtime-v0.04](https://github.com/Caraveo/forge/releases/tag/runtime-v0.04) release (portable UniRig runtimes). Model weights come from Hugging Face.

## v0.03 — November 21, 2026

The FORGE desktop app, with fixes to the installer's runtime setup.

## v0.02 — November 20, 2026

Setup downloads runtime code from the FORGE project's own [runtime-v0.01](https://github.com/Caraveo/forge/releases/tag/runtime-v0.01) release. Model weights still come from Hugging Face.

## v0.01 — November 20, 2026

Initial private release.
