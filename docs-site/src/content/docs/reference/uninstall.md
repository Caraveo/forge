---
title: Uninstall
---

Open **Settings → Apps → Installed apps → FORGE → Uninstall**.

Windows Installer removes:

* the app (`%LOCALAPPDATA%\Programs\FORGE`) and its Start menu shortcut, and
* the private runtime (`%LOCALAPPDATA%\FORGE-Data\runtime`), including UniRig and the chat model.

It **keeps**:

* your projects in **Documents\FORGE**, and
* the downloaded FLUX.1-schnell and TRELLIS.2 weights in `%LOCALAPPDATA%\FORGE-Data\models`, so reinstalling doesn't download them again.

To free that space too, delete `%LOCALAPPDATA%\FORGE-Data` after uninstalling. Delete **Documents\FORGE** only if you no longer need your projects.

:::note
Upgrading to a newer version doesn't count as an uninstall: your runtime is kept.
:::
