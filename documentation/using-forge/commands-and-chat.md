# Commands and chat

Everything starts in the message field at the bottom of the window. The first word of your message decides what FORGE does.

| Start with | FORGE does | Needs an attachment? |
| --- | --- | --- |
| **forge**, **build**, **make**, **mold** | Builds a textured 3D model | No. With an image attached, builds from that image |
| **generate**, **create**, **imagine** | Paints an image | No (an attached image is refused) |
| **remove background** | Makes a transparent PNG cutout | An image |
| **upscale** | Enlarges an image 4× | An image |
| **rig** | Rigs a model with UniRig and exports FBX | A GLB, FBX or image |
| Anything else | Chats with the local Qwen model | No |

Polite openers are fine: *"please forge a lantern"* and *"could you upscale it"* work the same way.

## Naming and reusing

* Add `named Buddy` or `called Buddy` to name the project and skip the naming question.
* After you chat about an idea, `make it` or `forge that` builds the idea you last described.

## Chat

Ordinary messages go to **Qwen3-0.6B**, a small model that runs on your CPU. It answers questions, discusses ideas and suggests which tool to use. It **can't start jobs or run anything by itself**.

* Greetings, thanks and questions get a plain reply.
* When your message describes something to make ("a cozy cabin in the woods"), the reply offers **🎨 Image of "…"** and **🧱 3D model of "…"** buttons. Nothing starts until you click one.
* Chat runs beside the build queue, so you can keep talking while a model builds.

{% hint style="info" %}
Chat replies take a while (often 30–60 seconds) because the model runs on the CPU. A **💭 Thinking…** line shows while it works.
{% endhint %}

## What FORGE won't treat as a command

A message that only starts with a command word in a different sense stays a chat message, for example *"make sure this works"*, *"build up the scene"*, *"imagine if…"* or *"don't generate anything"*.
