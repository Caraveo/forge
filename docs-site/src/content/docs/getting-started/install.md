---
title: Install FORGE
---

## Before you start

1. Make sure your PC meets the [requirements](../requirements/), and read [Before you install](../../important/before-you-install/).
2. **Accept the FLUX.1-schnell license.** FORGE paints its reference images with [FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell), a gated model. Sign in to Hugging Face, open the model page and accept its terms.
3. **Sign in to Hugging Face on this PC.** If you already use the Hugging Face CLI, run `hf auth login` and paste an access token from your [Hugging Face settings](https://huggingface.co/settings/tokens). If you don't, you can sign in during setup instead (see step 4 below).

## Install

1. Download **FORGE-v0.05-Setup.exe** from the [latest release](https://github.com/Caraveo/forge/releases/latest).
2. Run it. Setup checks your hardware and asks you to confirm.
3. Setup installs the app for your Windows account only, in `%LOCALAPPDATA%\Programs\FORGE`. It doesn't need administrator rights.
4. A setup window opens and provisions FORGE's private runtime. This is the long part:

   | Step | Source | Space used |
   | --- | --- | --- |
   | Python 3.12, uv, AMD ROCm PyTorch 7.2.1 | [FORGE runtime-v0.01](https://github.com/Caraveo/forge/releases/tag/runtime-v0.01) | About 8 GB |
   | trellis.cpp, Blender, Real-ESRGAN | FORGE runtime-v0.01 | About 1 GB |
   | FLUX.1-schnell (gated) | Hugging Face | About 31 GB |
   | TRELLIS.2 GGUF weights | Hugging Face | About 15 GB |
   | Portable UniRig runtimes | [FORGE runtime-v0.04](https://github.com/Caraveo/forge/releases/tag/runtime-v0.04) | About 5 GB download, 11 GB installed |
   | UniRig checkpoints and Qwen3-0.6B chat model | Hugging Face | About 7 GB |

   On the test PC, a complete install uses about **75 GB**. Downloaded parts are deleted after they're unpacked.

   If the FLUX download fails because you aren't signed in, sign in with the copy of the CLI inside FORGE's runtime, then open FORGE again:

   ```
   "%LOCALAPPDATA%\FORGE-Data\runtime\env\Scripts\hf.exe" auth login
   ```

5. When setup finishes, Setup says **FORGE is ready**. Open **FORGE** from the Start menu.

You can also install the MSI (`FORGE-v0.05-x64.msi`) directly. The runtime is then provisioned the first time you open FORGE.

## If setup stops

Setup is safe to resume. **Open FORGE again** and it picks up where it left off; files that already downloaded and passed their checksums aren't downloaded again. The full setup log is at `%LOCALAPPDATA%\FORGE-Data\setup.log`. See [Common problems](../../troubleshooting/common-problems/) for specific messages.

:::note
If only the chat and rigging tools failed to install, FORGE still opens with image and 3D generation available, and finishes installing those tools the next time you open it.
:::

## Upgrading

Run the new version's Setup over your current install. Every version replaces the previous one in place and **keeps your private runtime**, so an upgrade from v0.04 to v0.05 downloads nothing new. Installing an older version over a newer one is refused with *"A newer version of FORGE is already installed."*
