"""Provision UniRig and chat for FORGE v0.04, then commit their config.

Code and Python runtimes come from the FORGE runtime-v0.04 release (checksum
pinned in manifest-v004.json); model weights come from Hugging Face.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile

def extended(path):
    """Use the \\\\?\\ prefix so Windows allows paths longer than MAX_PATH (260).

    The UniRig ROCm libraries contain entries near 200 characters, which exceed
    MAX_PATH once placed under %LOCALAPPDATA% unless LongPathsEnabled is set.
    """
    text = os.path.abspath(str(path))
    if os.name != 'nt' or text.startswith('\\\\?\\'):
        return text
    if text.startswith('\\\\'):
        return '\\\\?\\UNC\\' + text[2:]
    return '\\\\?\\' + text


# Model weights come from Hugging Face at pinned revisions, like FLUX and TRELLIS.
# The FORGE runtime release only carries code and Python runtimes.
# (repo, revision, files, destination relative to the tool directory)
WEIGHTS = {
    'unirig': [
        ('VAST-AI/UniRig', '36842e2b5947e9e60f89275b83208c8e74071c63',
         ['skeleton/articulation-xl_quantization_256/model.ckpt', 'skin/articulation-xl/model.ckpt'],
         'UniRig-main/experiments'),
        ('facebook/opt-350m', '08ab08cc4b72ff5593870b5d527cf4230323703c', ['config.json'],
         'UniRig-main/models/opt'),
    ],
    'chat': [
        ('Qwen/Qwen3-0.6B', 'c1899de289a04d12100db370d81485cdf75e47ca',
         ['config.json', 'generation_config.json', 'LICENSE', 'merges.txt', 'model.safetensors',
          'tokenizer.json', 'tokenizer_config.json', 'vocab.json'], '.'),
    ],
}


def install_bundle(bundle, target):
    print('Installing ' + bundle['directory'], flush=True)
    archive = runtime / (bundle['directory'] + '.zip')
    with archive.open('wb') as output:
        for part in bundle['parts']:
            cached = runtime / part['name']
            if not cached.exists() or hashlib.file_digest(cached.open('rb'), 'sha256').hexdigest() != part['sha256']:
                partial = cached.with_suffix('.partial')
                urllib.request.urlretrieve(origin + part['name'], partial)
                with partial.open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != part['sha256']:
                        raise ValueError('Checksum failed for ' + part['name'])
                partial.replace(cached)
            with cached.open('rb') as stream:
                shutil.copyfileobj(stream, output)
    staging = runtime / (bundle['directory'] + '-installing')
    staging.mkdir(exist_ok=True)
    root = os.path.normcase(os.path.normpath(str(staging)))
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            path = os.path.normcase(os.path.normpath(os.path.join(root, item.filename)))
            if os.path.commonpath([root, path]) != root:
                raise ValueError('Invalid runtime archive path')
        z.extractall(extended(staging))
    if target.exists():
        shutil.copytree(extended(staging), extended(target), dirs_exist_ok=True)
        shutil.rmtree(extended(staging))
    else:
        os.replace(extended(staging), extended(target))
    if bundle['directory'] == 'unirig':
        cfg = target / 'python312-rocm721/venv/pyvenv.cfg'
        lines = cfg.read_text().splitlines()
        base = target / 'python312-rocm721/python/cpython-3.12.10-windows-x86_64-none'
        cfg.write_text('\n'.join('home = ' + str(base) if line.startswith('home = ') else line for line in lines) + '\n')
    archive.unlink()
    for part in bundle['parts']:
        (runtime / part['name']).unlink()


def download_weights(directory, target):
    from huggingface_hub import snapshot_download
    for repo, revision, files, destination in WEIGHTS.get(directory, []):
        folder = target / destination
        if all((folder / name).is_file() for name in files):
            continue
        print('Downloading ' + repo + ' from Hugging Face', flush=True)
        snapshot_download(repo, revision=revision, allow_patterns=files, local_dir=str(folder))
        missing = [name for name in files if not (folder / name).is_file()]
        if missing:
            raise FileNotFoundError(repo + ' is missing ' + ', '.join(missing))


runtime = Path(sys.argv[1]).resolve()
manifest_path = Path(__file__).with_name('manifest-v004.json')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
origin = 'https://github.com/Caraveo/forge/releases/download/runtime-v0.04/'
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
bundles = {bundle['directory']: bundle for bundle in manifest['bundles']}
for directory in ('unirig', 'chat'):
    target = runtime / directory
    # .complete-v004 is written only once code and weights are both in place,
    # so a failed weight download is retried on the next launch.
    if (target / '.complete-v004').is_file():
        continue
    if directory in bundles and not (target / '.bundle-v004').is_file():
        install_bundle(bundles[directory], target)
        (target / '.bundle-v004').write_text('0.04')
    target.mkdir(parents=True, exist_ok=True)
    download_weights(directory, target)
    (target / '.complete-v004').write_text('0.04')
config_path = runtime / 'config.json'
cfg = json.loads(config_path.read_text(encoding='utf-8-sig'))
cfg['chat'] = str(runtime / 'chat')
cfg['unirig'] = str(runtime / 'unirig')
cfg['version'] = '0.04'
temporary = config_path.with_suffix('.tmp')
temporary.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
temporary.replace(config_path)
print('FORGE v0.04 runtime ready.', flush=True)
