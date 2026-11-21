# Logs and diagnostics

FORGE writes down what it does. When something goes wrong, these files explain why.

| What | Where |
| --- | --- |
| A build in progress | Press **Ctrl + L** in FORGE to show or hide the live build log |
| A finished or failed project | `pipeline.log` in the project's folder under **Documents\FORGE** |
| Runtime setup | `%LOCALAPPDATA%\FORGE-Data\setup.log` |
| Installer (Setup.exe) | `%LOCALAPPDATA%\FORGE-Data\install.log` |
| GPU test during setup | `%LOCALAPPDATA%\FORGE-Data\runtime\torch-check.log` |
| FLUX download | `%LOCALAPPDATA%\FORGE-Data\runtime\flux-download.log` |
| TRELLIS weight download | `%LOCALAPPDATA%\FORGE-Data\runtime\trellis-download.log` |

Paste `%LOCALAPPDATA%\FORGE-Data` into the File Explorer address bar to open the folder.

## Reading a build log

Lines that start with a tag show the build's progress:

* `[stage]` the step that started, such as `Generating image` or `Building textured model (high quality)`
* `[quality]` the quality preset in use, and any fallback
* `[prompt]` the enhanced prompt
* `[show]` a file that is ready (reference image, model)

An error near the end, often a Python `Traceback` or a line with `Error`, usually explains a failure.

## Reading the installer log

Search `install.log` for `Return value 3`. The lines just above it name the action that failed. `error status: 0` at the end means the install succeeded.

## Reporting a problem

Open an issue on [GitHub](https://github.com/Caraveo/forge/issues) with:

* your FORGE version (shown in the window title),
* your GPU model and driver version,
* what you typed, and
* the relevant log, with anything private removed.
