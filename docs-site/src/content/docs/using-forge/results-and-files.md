---
title: Results and files
---

## In the app

Each result has one row of actions:

| Result | Actions |
| --- | --- |
| 3D model | **Rig** · **Save** · **Select** · **Expand** · **Zoom out** · **Zoom in** · **Reset** · **Open folder** |
| Image | **Save image** · **Select image** · **Open folder** |
| Rigged model | **Save rigged FBX** · **Open folder** |

* **Drag** a model to rotate it. Hold **Ctrl** and scroll to zoom.
* **Expand** opens the model in its own resizable window.
* **Save** copies the file anywhere you choose.
* **Select** attaches the result so you can use it in another action.

## On disk

Every project is saved in its own folder under **Documents\FORGE**, named `<Project name>_<date>_<time>`. A 3D build contains:

```
Documents\FORGE\Buddy_20261121_143000_1234567\
├── prompt.txt                     your message
├── pipeline.log                   everything the build printed
├── Buddy_…png                     reference image
├── Buddy_…_cutout.png             background-removed cutout
├── Buddy_…glb                     textured model
└── Buddy_…-asset\                 Unity-ready folder
    ├── Buddy_….fbx
    └── textures (PNG)
```

Image projects contain the PNG, and rigging adds an `.fbx`. If you attached a file, a copy is kept as `input.<ext>`.

## Using the model in Unity

Copy the whole `-asset` folder into your Unity project's `Assets` folder. It holds the FBX and its textures. On standard and high quality the textures are 4096 px, so check Unity's **Max Size** import setting if they look soft.
