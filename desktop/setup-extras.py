"""Provision the portable UniRig and chat runtimes, then commit their config."""
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


runtime = Path(sys.argv[1]).resolve()
manifest_path = Path(__file__).with_name('manifest-v004.json')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
origin = 'https://github.com/Caraveo/forge/releases/download/runtime-v0.04/'
for bundle in manifest['bundles']:
    target = runtime / bundle['directory']
    marker = target / '.complete-v004'
    if marker.is_file():
        continue
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
    marker.write_text('0.04')
    archive.unlink()
    for part in bundle['parts']:
        (runtime / part['name']).unlink()
config_path = runtime / 'config.json'
cfg = json.loads(config_path.read_text(encoding='utf-8-sig'))
cfg['chat'] = str(runtime / 'chat')
cfg['unirig'] = str(runtime / 'unirig')
cfg['version'] = '0.04'
temporary = config_path.with_suffix('.tmp')
temporary.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
temporary.replace(config_path)
print('FORGE v0.04 runtime ready.', flush=True)
