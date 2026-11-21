"""Build the portable v0.04 UniRig runtime archive (code and Python runtimes, no model weights)."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist' / 'runtime-v004'
OUT.mkdir(parents=True, exist_ok=True)
LOCAL = Path.home() / 'unirig'

def add_tree(archive, source, target):
    # Filter on the path relative to the source, so a source that itself lives under a
    # skipped name (such as ~/.cache) is not silently dropped.
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

# Code and Python runtimes only. Model weights (UniRig checkpoints, the OPT
# config, Qwen3) are downloaded from Hugging Face by desktop/setup-extras.py.
unirig = [(ROOT / 'runtime/unirig', ''),
          (LOCAL / 'python311-rocm', 'python311-rocm'),
          (LOCAL / 'python312-rocm721', 'python312-rocm721')]
manifest = {'version': '0.04', 'bundles': [bundle('unirig', unirig)]}
(OUT / 'manifest-v004.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(OUT, flush=True)
