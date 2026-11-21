"""Build portable v0.04 runtime archives from the verified Windows runtimes."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist' / 'runtime-v004'
OUT.mkdir(parents=True, exist_ok=True)
LOCAL = Path.home() / 'unirig'
CACHE = Path.home() / '.cache/huggingface/hub'

def add_tree(archive, source, target):
    # Filter on the path relative to the source: the Hugging Face sources live under
    # ~/.cache, so testing absolute parts silently dropped every model checkpoint.
    skip = {'.git', '__pycache__', '.cache', 'logs', 'lightning_logs'}
    count = 0
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if path.is_file() and not skip.intersection(relative.parts):
            archive.write(path, str(Path(target) / relative))
            count += 1
    if count == 0:
        raise SystemExit('No files bundled from ' + str(source))

def bundle(name, entries):
    archive = OUT / (name + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for source, target in entries:
            add_tree(z, source, target)
    parts = []
    with archive.open('rb') as stream:
        index = 0
        while data := stream.read(512 * 1024 * 1024):
            part = OUT / (name + '.part' + str(index))
            part.write_bytes(data)
            parts.append({'name': part.name, 'sha256': hashlib.sha256(data).hexdigest()})
            index += 1
    archive.unlink()
    return {'directory': name, 'parts': parts}

unirig = [(ROOT / 'runtime/unirig', ''),
          (LOCAL / 'python311-rocm', 'python311-rocm'),
          (LOCAL / 'python312-rocm721', 'python312-rocm721')]
unirig.append((CACHE / 'models--VAST-AI--UniRig/snapshots/36842e2b5947e9e60f89275b83208c8e74071c63', 'UniRig-main/experiments'))
unirig.append((CACHE / 'models--facebook--opt-350m/snapshots/08ab08cc4b72ff5593870b5d527cf4230323703c', 'UniRig-main/models/opt'))
manifest = {'version': '0.04', 'bundles': [bundle('unirig', unirig), bundle('chat', [(ROOT / 'dist/chat-model', '')])]}
(OUT / 'manifest-v004.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(OUT, flush=True)
