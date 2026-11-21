---
title: Requirements
---

FORGE checks your hardware before it installs, and again before it sets up its runtime. If a requirement isn't met, setup stops and tells you what it detected.

| Requirement | Minimum | Checked by Setup |
| --- | --- | --- |
| Windows | 64-bit Windows (x64) | Yes |
| CPU | AMD | Yes |
| GPU | AMD Radeon with **16 GB dedicated VRAM**, supported by ROCm | Yes (vendor and VRAM) |
| System memory | **32 GB** installed RAM | Yes |
| Graphics driver | A current AMD driver with Vulkan support | Tested during setup |
| Free storage | **100 GB** for the runtime, models, caches and temporary files | No, so check before you start |
| Internet | Needed for first setup; generation afterwards is local | No |
| Hugging Face account | Needed once, to download FLUX.1-schnell | No (see [Install](../install/)) |

:::note
The VRAM check allows 256 MiB of driver-reserved memory, so a card sold as 16 GB passes even if Windows reports slightly less.
:::

## What gets checked

The hardware check reads the CPU vendor, the installed RAM and every display adapter. It passes when it finds an AMD adapter (vendor `0x1002`) with at least 15.75 GB of dedicated memory. During runtime setup, FORGE also runs a small tensor test on the GPU through ROCm. If the driver can't run it, setup stops with *"The AMD driver failed the ROCm tensor test"* (see [Common problems](../../troubleshooting/common-problems/#the-amd-driver-failed-the-rocm-tensor-test)).

## Tested hardware

FORGE v0.05 was tested on Windows 11 with an AMD Radeon RX 9060 XT (16 GB).
