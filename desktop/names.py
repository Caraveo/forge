"""Suggest short project names with the local Qwen chat model.

Usage: names.py PROMPT_FILE CONFIG_JSON OUTPUT_FILE
Writes up to five names, one per line, each one to three words in Title Case.
The model output is only ever used as text; it cannot run tools or commands.
"""
import json
import re
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

COMMAND = re.compile(r"^(?:(?:please|can you|could you|would you)\s+)*(?:forge|build|make|mold|generate|create|imagine|image)\s+", re.I)


def clean(line):
    """Strip list markers, quotes and punctuation; keep names of one to three words."""
    line = re.sub(r"^\s*(?:[-*•]|\d+[.):])\s*", "", line)
    line = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", line)  # GoldenGlow -> Golden Glow
    line = re.sub(r"[^A-Za-z0-9 '\-]", " ", line).replace("'", "")
    words = line.split()
    if not 1 <= len(words) <= 3:
        return None
    name = " ".join(word[:1].upper() + word[1:] for word in words)
    return name if len(name) <= 32 else None


def main():
    idea = COMMAND.sub("", Path(sys.argv[1]).read_text(encoding="utf-8-sig").strip())
    cfg = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig"))
    torch.set_num_threads(8)
    tokenizer = AutoTokenizer.from_pretrained(cfg["chat"], local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(cfg["chat"], local_files_only=True, torch_dtype=torch.float32)
    messages = [
        {"role": "system", "content": "You name game asset projects. Reply with exactly five short, distinct, "
                                      "memorable names for the user's idea, one per line. Each name is one to three "
                                      "words in Title Case. No numbering, quotes, emoji or explanation."},
        {"role": "user", "content": idea[:500]},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    inputs = tokenizer(text, return_tensors="pt")
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=60, do_sample=True, temperature=0.8, top_p=0.9,
                                pad_token_id=tokenizer.eos_token_id)
    reply = tokenizer.decode(output[0, inputs.input_ids.shape[1]:], skip_special_tokens=True)
    names = []
    for line in reply.splitlines():
        name = clean(line)
        if name and name.lower() not in (existing.lower() for existing in names):
            names.append(name)
    Path(sys.argv[3]).write_text("\n".join(names[:5]), encoding="utf-8")


if __name__ == "__main__":
    main()
