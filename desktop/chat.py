"""Local conversation service. Responses cannot execute tools or shell commands."""
import json
import sys
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
cfg = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig'))
torch.set_num_threads(8)
path = cfg['chat']
tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(path, local_files_only=True, torch_dtype=torch.float32)
messages = [{'role': 'system', 'content': 'You are FORGE, a concise friendly assistant for making game assets locally. Discuss ideas and answer questions. Tools available through buttons: generate image, build 3D model, remove image background, upscale image, rig model with UniRig. Never claim you have performed a tool action. For an unclear request ask one short question. For an action request suggest the appropriate tool. The selected file is ' + request.get('attachment', 'none') + '.'}]
messages += request['messages'][-10:]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
inputs = tokenizer(text, return_tensors='pt', truncation=True, max_length=2048)
with torch.inference_mode():
    result = model.generate(**inputs, max_new_tokens=180, do_sample=False, pad_token_id=tokenizer.eos_token_id)
reply = tokenizer.decode(result[0, inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
Path(sys.argv[3]).write_text(reply, encoding='utf-8')
