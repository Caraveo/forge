# Attachments

Attach a file to work with it: click **+** next to the message field, or drag the file anywhere onto the window.

## What you can attach

| File | Becomes | Suggested next steps |
| --- | --- | --- |
| **PNG, JPEG, WebP** | An attachment chip with a thumbnail | 🧱 Build 3D · ✂️ Remove background · 🔍 Upscale |
| **GLB** | An attachment chip | 👀 Preview · 🦴 Rig |
| **FBX** | An attachment chip | 🦴 Rig (FBX can't be previewed) |
| **TXT** | Your prompt, placed in the message field for you to review and send | — |

Anything else (videos, executables, configuration files and so on) is refused with a message listing what FORGE can use. While you drag an unsupported file, the cursor shows that it can't be dropped.

The suggested actions appear just above the message field. Clicking one runs it right away.

## Text files

A `.txt` file is read in as a prompt, not attached:

* Line breaks become spaces, and control characters are removed.
* Text longer than 2,000 characters is trimmed. Files over 64 KB are refused.
* Nothing runs until you press **Enter**.

## Clearing an attachment

Hover the chip and click the red **×** (or press **Tab** to reach it and **Enter**). Starting a job also clears the attachment.

## Using earlier results

Every result has a **Select** button that attaches it, so you can chain steps: build a model, then **Select** it and type `rig it`.

## Rules

* **Remove background** and **upscale** need an image.
* **generate** with an image attached is refused: use **forge** to build from the image, or clear it first.
* A GLB or FBX can only be **rigged** (or previewed).
