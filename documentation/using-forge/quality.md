# Quality

FORGE reads quality from the words in your prompt. There's no setting to change.

| Preset | Say | Geometry | Sampler steps | Texture atlas | Unity textures |
| --- | --- | --- | --- | --- | --- |
| **High** | super, superior, supreme, premium, prime, quality, high quality, HQ, ultra, best, detailed, hi-res, masterpiece | 1024 | 20 | 2048 px | 4096 px |
| **Standard** | *(default)* | 512 | 12 | 1024 px | 4096 px (upscaled 4×) |
| **Draft** | draft, low quality, low-res | 512 | 8 | 1024 px | 1024 px (no upscale) |

```
forge me a super apple        → a high-quality apple
mold a premium sword          → high quality
forge a draft barrel          → draft
```

Quality words steer the build but are removed from the prompt itself, so "a super apple" is built as "an apple". Words that merely contain them, such as *superhero*, don't count.

**High-quality images** (`generate a super lantern`) are painted at 768 px, then upscaled 4× to 3072 px.

## Things to know

* **High quality takes considerably longer**, mostly in the sculpting step, and uses more GPU memory.
* **It falls back instead of failing.** If the 1024 TRELLIS weights are missing, or a high-quality sculpt runs out of GPU memory, FORGE finishes the job at standard quality and says so in the conversation.
* **Reference images stay at 768 px.** ROCm on Windows can't give FLUX the single 4.5 GB memory block a 1024 px image needs, so the extra quality comes from the 3D step instead.

## Command line

`forge.cmd` accepts `--quality auto|draft|standard|high` (default `auto` reads your words), and `--res 512|1024` and `--steps N` to override parts of a preset. See [Command line](command-line.md).
