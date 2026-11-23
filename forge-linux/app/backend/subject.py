"""Local, subject-only Qwen inference in a disposable worker process."""
import argparse
import gc
import json
from pathlib import Path

try:
    from .memory import MemoryUnavailable, require_memory
except ImportError:
    from memory import MemoryUnavailable, require_memory

MODEL = "Qwen/Qwen3-VL-8B-Instruct"
INSTRUCTIONS = (
    "Return valid JSON only. Produce an enhanced subject description and independent creative "
    "ideas for a later revision. The subject field must be one concise paragraph that preserves "
    "the user's intent and reference image's recognizable features. Cover relevant geometry, "
    "proportions, anatomy, materials, color, texture and artistic style. Avoid unrelated objects, "
    "accessories, background, lighting, camera framing and production instructions. The suggestions "
    "field must be an array of three concise, optional ideas. Across the array, cover useful "
    "geometry, material or colour, visual identity, and a design variation when relevant. The "
    "question field must be one short optional question that helps choose a later revision. "
    "Use exactly this schema: {\"subject\": string, \"suggestions\": [string], \"question\": string}."
)


def messages(subject, image):
    content = [{"type": "image", "image": image}] if image is not None else []
    content.append({"type": "text", "text": subject or "Describe the subject in the reference image."})
    return [{"role": "system", "content": [{"type": "text", "text": INSTRUCTIONS}]},
            {"role": "user", "content": content}]


def enhance(subject, reference, cache, revision, memory_config=None):
    import torch
    from PIL import Image
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    processor = AutoProcessor.from_pretrained(MODEL, cache_dir=cache, revision=revision)
    image = None
    if reference:
        with Image.open(reference) as opened:
            opened.thumbnail((768, 768))
            image = opened.convert("RGB")
    inputs = processor.apply_chat_template(
        messages(subject, image), tokenize=True, add_generation_prompt=True,
        return_dict=True, return_tensors="pt",
    )
    # Prefer GPU while FORGE is idle/preparing a job. If another application
    # owns too much VRAM, CPU placement is allowed only after a separate RAM
    # preflight succeeds. Generation never overlaps this worker: it exits and
    # releases Qwen before FLUX or TRELLIS can start.
    gpu = False
    gpu_reason = ""
    if torch.cuda.is_available():
        try:
            require_memory("subject", memory_config or {})
            gpu = True
        except MemoryUnavailable as exc:
            gpu_reason = str(exc)
    if not gpu:
        require_memory("subject-cpu", memory_config or {})
        if gpu_reason:
            print("[model-placement] Qwen GPU memory is busy; using CPU/RAM for this request.", flush=True)
    # Keep VRAM headroom for vision activations, KV cache and ROCm workspaces.
    # Accelerate places the remaining GPU weights in RAM without CUDA quantizers.
    options = {"device_map": "auto" if gpu else "cpu", "dtype": torch.bfloat16}
    if gpu:
        free, _ = torch.cuda.mem_get_info(0)
        options["max_memory"] = {0: min(10 * 1024**3, max(0, free - 3 * 1024**3)), "cpu": "18GiB"}
        options["offload_folder"] = str(Path(cache) / "qwen-offload")
    model = None
    try:
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            MODEL, cache_dir=cache, revision=revision, **options
        )
        inputs = inputs.to("cuda:0" if gpu else "cpu")
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=256, do_sample=False)
        reply = processor.decode(output[0, inputs.input_ids.shape[1]:], skip_special_tokens=True)
        start, end = reply.find("{"), reply.rfind("}") + 1
        result = json.loads(reply[start:end])
        if not isinstance(result.get("subject"), str) or not result["subject"].strip():
            raise ValueError("Qwen returned no subject")
        raw_suggestions = result.get("suggestions")
        if not isinstance(raw_suggestions, list):
            raw_suggestions = [result.get("suggestion", "")]
        suggestions = []
        for suggestion in raw_suggestions:
            if isinstance(suggestion, str):
                suggestion = " ".join(suggestion.split())[:240]
                if suggestion and suggestion not in suggestions:
                    suggestions.append(suggestion)
        question = result.get("question")
        return {"subject": " ".join(result["subject"].split()),
                "suggestions": suggestions[:4],
                "question": " ".join(question.split())[:240] if isinstance(question, str) else "",
                "revision": getattr(model.config, "_commit_hash", None) or revision}
    finally:
        # This process owns Qwen exclusively. Releasing its allocations here
        # gives the next generation stage a clean handoff without touching any
        # other process or application.
        del model
        gc.collect()
        if gpu:
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
        print("[model-released] Qwen subject assistant", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    try:
        result = enhance(
            request["subject"], request["reference"], request["cache"], request["revision"],
            request.get("memory", {}),
        )
    except MemoryUnavailable:
        # The parent treats this exit status as a hard preflight rejection.
        # It must never be converted into a prompt-enhancer fallback.
        raise SystemExit(76)
    args.result.write_text(json.dumps(result), encoding="utf-8")
