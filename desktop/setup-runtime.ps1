$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'FORGE.exe') --check --quiet | Out-Null
if ($LASTEXITCODE) { throw 'Requires AMD CPU and GPU, 16 GB dedicated VRAM and 32 GB system RAM.' }
$data = Join-Path $env:LOCALAPPDATA 'FORGE Data'
$runtime = Join-Path $data 'runtime'
$weights = Join-Path $data 'models'
$owner = Join-Path $runtime '.forge-owned'
if ((Test-Path $runtime) -and !(Test-Path $owner)) { throw "Existing unrecognized directory: $runtime" }
New-Item -ItemType Directory -Force -Path $runtime,$weights | Out-Null
New-Item -ItemType File -Force $owner | Out-Null
Start-Transcript -Path (Join-Path $data 'setup.log') -Append
function Get-ArchiveTool($name,$url,$binary) {
    $dest = Join-Path $runtime $name
    $found = Get-ChildItem $dest -Recurse -Filter $binary -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$found) {
        $zip = Join-Path $runtime "$name.zip"
        Invoke-WebRequest $url -OutFile $zip -UseBasicParsing
        Expand-Archive $zip $dest -Force
        $found = Get-ChildItem $dest -Recurse -Filter $binary | Select-Object -First 1
        if (!$found) { throw "Missing $binary in $name archive" }
        Remove-Item -LiteralPath $zip
    }
    $found.FullName
}
try {
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $runtime 'python'
    $env:UV_CACHE_DIR = Join-Path $runtime 'cache'
    $env:UV_PYTHON_BIN_DIR = Join-Path $runtime 'bin'
    $uv = Get-ArchiveTool 'uv' 'https://github.com/astral-sh/uv/releases/download/0.9.10/uv-x86_64-pc-windows-msvc.zip' 'uv.exe'
    $venv = Join-Path $runtime 'env'
    $py = Join-Path $venv 'Scripts\python.exe'
    if (!(Test-Path $py)) {
        & $uv venv --managed-python --python 3.12.10 $venv
        if ($LASTEXITCODE) { throw 'Private Python installation failed.' }
    }
    $base = 'https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/'
    $wheels = @('rocm_sdk_core-7.2.1-py3-none-win_amd64.whl','rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl','rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl','rocm-7.2.1.tar.gz','torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl','torchvision-0.24.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl') | ForEach-Object { $base+$_ }
    & $uv pip install --python $py @wheels 'diffusers==0.37.1' 'transformers==4.57.6' 'accelerate>=1.10,<2' 'huggingface-hub==0.36.2' rich Pillow protobuf safetensors
    if ($LASTEXITCODE) { throw 'ROCm packages failed to install.' }
    & $py -c "import torch; assert torch.version.hip and torch.cuda.is_available(); print(torch.cuda.get_device_name(0),torch.ones(1,device='cuda').cpu())"
    if ($LASTEXITCODE) { throw 'The AMD driver failed the ROCm tensor test.' }
    $cli = Get-ArchiveTool 'trellis' 'https://github.com/pwilkin/trellis.cpp/releases/latest/download/trellis-vulkan-windows-x64.zip' 'trellis-cli.exe'
    $scale = Get-ArchiveTool 'upscale' 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip' 'realesrgan-ncnn-vulkan.exe'
    $blender = Get-ArchiveTool 'blender' 'https://download.blender.org/release/Blender4.5/blender-4.5.0-windows-x64.zip' 'blender.exe'
    $env:HF_HOME = Join-Path $weights 'hf'
    $flux = & $py -c "from huggingface_hub import snapshot_download; print(snapshot_download('black-forest-labs/FLUX.1-schnell',revision='169573f54945f633efbe126a40a5676b4228363c',allow_patterns=['model_index.json','scheduler/*','tokenizer*/*','text_encoder*/*.json','text_encoder*/*.safetensors','transformer/*.json','transformer/*.safetensors','vae/*.json','vae/*.safetensors']))"
    if ($LASTEXITCODE) { throw 'FLUX download failed. Check network access and any model access requirements.' }
    $models = Join-Path $weights 'trellis'
    & $py -c "import sys;from huggingface_hub import snapshot_download;snapshot_download('ilintar/trellis2-gguf',local_dir=sys.argv[1],allow_patterns=['birefnet.gguf','dinov3.gguf','ss_flow.gguf','ss_dec.gguf','shape_flow_512.gguf','shape_flow_1024.gguf','shape_dec.gguf','tex_flow_512.gguf','tex_flow_1024.gguf','tex_dec.gguf'])" $models
    if ($LASTEXITCODE) { throw 'TRELLIS weight download failed.' }
    $config = @{python=$py; enhancerPython=$py; flux=$flux.Trim(); models=$models; trellis=$cli; blender=$blender; upscaler=$scale; output=(Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'FORGE')}
    $config | ConvertTo-Json | Set-Content (Join-Path $runtime 'config.json') -Encoding UTF8
} finally { Stop-Transcript }
