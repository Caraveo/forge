---
title: Common problems
---

Most problems leave a message in the app and a detailed log. See [Logs and diagnostics](../logs/) for where to look.

## Installing

### "FORGE requires 64-bit Windows, an AMD CPU, 32 GB installed RAM and an AMD GPU with 16 GB dedicated VRAM"

The hardware check failed. The message ends with what was detected (CPU vendor, installed RAM or display adapters). FORGE only runs on AMD CPUs with an AMD Radeon GPU that has 16 GB of dedicated memory. See [Requirements](../../getting-started/requirements/).

### Windows Installer error 1603

1603 means the install failed; the reason is in the log.

* **Setup.exe writes a full log** to `%LOCALAPPDATA%\FORGE-Data\install.log`. Search it for `Return value 3` and read the lines just above.
* Setup from **v0.04 or an early v0.05 download** could fail with 1603 when run over an installed copy of the same version, because of a Windows Installer check (*SecureRepair*). This was fixed on November 21: download Setup again from the [latest release](https://github.com/Caraveo/forge/releases/latest).
* If an older FORGE (v0.03 or earlier) is installed and an upgrade fails, uninstall it from **Settings → Apps**, then install again. Your downloaded model weights are kept.

### "A newer version of FORGE is already installed."

You're installing an older version over a newer one. That's blocked on purpose; install the latest version instead.

### "Setup stopped. Open FORGE to retry."

Runtime setup didn't finish. **Open FORGE again** to resume. Finished downloads aren't repeated. The reason is in `%LOCALAPPDATA%\FORGE-Data\setup.log`; the specific messages are below.

### "FLUX download failed. Accept the FLUX.1-schnell license on Hugging Face and sign in on this PC."

1. Open [FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell) while signed in to Hugging Face and accept the license.
2. Sign in on this PC with FORGE's copy of the Hugging Face CLI and paste an [access token](https://huggingface.co/settings/tokens):

   ```
   "%LOCALAPPDATA%\FORGE-Data\runtime\env\Scripts\hf.exe" auth login
   ```

3. Open FORGE again.

### "The AMD driver failed the ROCm tensor test."

The GPU couldn't run a simple ROCm test. Install the latest AMD Adrenalin driver, restart, and open FORGE again. The full error is in `%LOCALAPPDATA%\FORGE-Data\runtime\torch-check.log`.

### "FORGE setup is already running. Wait for that setup window to finish."

Only one setup can run at a time. Let the open setup window finish, or close it and try again.

### "Existing unrecognized directory: …\FORGE-Data\runtime"

A `runtime` folder exists that FORGE didn't create, so it won't overwrite it. Rename or remove `%LOCALAPPDATA%\FORGE-Data\runtime` and open FORGE again.

### "Could not download … from the FORGE project." / "TRELLIS weight download failed."

A download failed or was interrupted. Check your internet connection and free disk space, then open FORGE again to resume.

### "FORGE chat and rigging tools could not be installed. Open FORGE to resume."

The core runtime is ready, so image and 3D generation already work. Open FORGE again to finish installing the chat and rigging tools. Until then, FORGE says *"Chat is still installing"* or *"Rigging is still installing"*.

## Building

### A build failed

The conversation says the build stopped. Press **Ctrl + L** to see the build log, or open `pipeline.log` in the project's folder. Then try again, perhaps with a simpler prompt or standard quality.

### "High quality was too heavy for the GPU this time, so I'm finishing at standard quality."

The high-quality sculpt ran out of GPU memory, so FORGE finished at standard quality. Close other GPU-heavy apps (games, browsers with many tabs, other AI tools) and try again.

### "The image was too large for the GPU; painting it at 768 px."

FLUX couldn't paint at a larger size and fell back to 768 px. The job continues normally.

### Builds take a long time

A standard 3D build takes several minutes; high quality takes considerably longer, mostly while sculpting. The job card shows the current stage and elapsed time. Queued jobs wait their turn.

### Chat is slow

The chat model runs on the CPU, so replies often take 30–60 seconds, longer while a build is also running.

## Rigging

### "UniRig is already processing another model."

Only one rig runs at a time. Wait for it to finish.

### "No free drive letter is available for the UniRig runtime."

UniRig temporarily maps one of the drive letters Z: to U:. Free one up. A rig that was cancelled or crashed can leave its drive mapped; restarting Windows clears it, or remove it with `subst Z: /d` (using the letter it took).

### "Output already exists. Choose a new FBX path"

From the command line, `rig.cmd` won't overwrite an existing FBX. Choose a new output name.

## Attachments

### "FORGE can't work with … files."

FORGE accepts images (PNG, JPEG, WebP), 3D models (GLB, FBX) and text prompts (TXT). See [Attachments](../../using-forge/attachments/).

### "That text file is too large to use as a prompt (64 KB at most)."

Shorten the file, or paste the part you want into the message field.

## Display

### Emoji look flat or single-colour

That's a limitation of how Windows draws text in this kind of app (WPF); the emoji still mean the same thing.
