---
title: Projects and jobs
---

## Naming a project

Before an image or 3D build starts, FORGE asks you to **name the project**:

* Suggestions taken from your prompt appear immediately.
* The local chat model adds its own ideas a moment later.
* Or type a name and press **Enter** (or **Start**).

The name labels the result in the conversation and names its folder: `Documents\FORGE\<Name>_<date>_<time>`. Names can use letters, numbers, spaces and hyphens, up to 40 characters. Other characters are removed, and spaces become underscores in the folder name.

Jobs made from an existing file are named for you: rigging `Buddy` creates `Buddy Rigged`, and upscaling creates `… Upscaled`.

## Job cards

Every project gets a card just above the message field:

| State | Meaning |
| --- | --- |
| **Queued** | Waiting for the job ahead of it |
| **Working** | Running. The card shows the current stage, elapsed time and progress |
| **Done ✓** | Finished, with the total time |
| **Failed** | Stopped with an error. The conversation says why |
| **Cancelled** | Stopped by you |

* Jobs run **one at a time, oldest first**, because each one uses most of the GPU.
* **Click a card** to jump to that project in the conversation.
* When a job ends, its **Cancel** button becomes **×**, which dismisses the card.

## Cancelling

* **Cancel** on a queued job removes it before it starts.
* **Cancel** on a running job stops it along with everything it started (FLUX, TRELLIS, Blender, UniRig) and **deletes its unfinished folder**.
* If you close FORGE while a build is running, it asks whether to cancel and close.

## Following along

While a project builds, the conversation shows each step with what it produced: the polished prompt, the reference image, the background-removed cutout, the model as soon as it exists, and what comes next. Click an image to open it in your image viewer.
