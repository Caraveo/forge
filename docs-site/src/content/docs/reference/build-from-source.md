---
title: Build from source
---

For contributors who want to build the installers themselves.

## Requirements

* x64 Windows
* **Python 3.12** (3.13 removed the `msilib` module the build uses)
* .NET Framework 4.8 (its C# compiler is part of Windows)

## Build

```
py -3.12 packaging\build.py
.\packaging\check-package.ps1
```

`build.py` compiles `FORGE.exe`, packages the app into `dist\FORGE-v0.05-x64.msi` and wraps it in `dist\FORGE-v0.05-Setup.exe`. `check-package.ps1` verifies the embedded MSI and its files, and runs the command, conversation and quality routing tests.

Each build is a Windows Installer major upgrade with a fresh product code. It replaces any earlier FORGE in place and keeps the private runtime.

## Repository layout

| Path | Contents |
| --- | --- |
| `desktop/` | The app (`Forge.cs`, `Preview.cs`, `Setup.cs`, `Intent.cs`), the job runner, setup scripts and helpers |
| `packaging/` | Build, package checks, routing tests, runtime bundler and icon generator |
| `runtime/unirig/` | UniRig source with the AMD compatibility changes |
| `docs/` | This documentation |

## Runtime archives

The release installer uses the checksum-pinned `desktop/manifest-v004.json` to install its portable runtimes. Maintainers can rebuild those archives with `packaging/bundle-runtime.py` from verified local UniRig runtimes. The archives hold code and Python runtimes only; `desktop/setup-extras.py` downloads the model weights from Hugging Face.

## Icon

To change the app icon, run `packaging\make-icon.py <image.png>` (needs Pillow), then build again.
