# Rigging

FORGE rigs models with [UniRig](https://github.com/VAST-AI-Research/UniRig): it predicts a skeleton and skin weights on your GPU and exports an FBX.

## Rig a model

* Click **Rig** under any 3D result, or
* attach a **GLB** or **FBX** and click **🦴 Rig** (or type `rig it`), or
* attach an **image**: FORGE builds the 3D model first, then rigs it.

The result is an **FBX** with bones and skin weights, which you can save or open in its folder. On the test PC (Radeon RX 9060 XT), rigging a model took about 2–3 minutes.

## How it works

1. A GLB is converted for rigging with Blender.
2. UniRig extracts the mesh, predicts the skeleton, then the skin weights, on the GPU through ROCm.
3. Blender exports the rigged FBX.

## Good to know

* Only **one rig runs at a time**. Starting a second gives *"UniRig is already processing another model."*
* UniRig temporarily maps a free drive letter (Z: down to U:) to keep its file paths short. If none are free, it stops with *"No free drive letter is available for the UniRig runtime."*
* Rigging needs the UniRig tools that setup installs. Until they're installed, FORGE says *"Rigging is still installing"*.

From the command line: `rig.cmd model.glb model-rigged.fbx`. The output must end in `.fbx` and must not already exist.
