$ErrorActionPreference = 'Stop'
$setupMutex = New-Object System.Threading.Mutex($false, 'Local\FORGE-Runtime-Setup')
try { $ownsSetup = $setupMutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $ownsSetup = $true }
if (!$ownsSetup) { throw 'FORGE setup is already running. Wait for that setup window to finish.' }
& (Join-Path $PSScriptRoot 'FORGE.exe') --check --quiet | Out-Null
if ($LASTEXITCODE) { throw 'Requires AMD CPU and GPU, 16 GB dedicated VRAM and 32 GB system RAM.' }
$data = Join-Path $env:LOCALAPPDATA 'FORGE-Data'
$runtime = Join-Path $data 'runtime'
$weights = Join-Path $data 'models'
$origin = 'https://github.com/Caraveo/forge/releases/download/runtime-v0.01'
$owner = Join-Path $runtime '.forge-owned'
$parked = Join-Path $runtime '.forge-upgrade'
if ((Test-Path -LiteralPath $parked) -and !(Test-Path -LiteralPath $owner)) { Move-Item -LiteralPath $parked -Destination $owner }
if ((Test-Path -LiteralPath $runtime) -and !(Test-Path -LiteralPath $owner)) { throw "Existing unrecognized directory: $runtime" }
New-Item -ItemType Directory -Force -Path $runtime, $weights | Out-Null
New-Item -ItemType File -Force -Path $owner | Out-Null
Start-Transcript -Path (Join-Path $data 'setup.log') -Append
$hashMap = @{}
function Sync-Hashes($manifest) {
    $hashMap.Clear()
    if ($manifest.hashes) {
        foreach ($item in $manifest.hashes.PSObject.Properties) { $hashMap[$item.Name] = ([string]$item.Value).ToUpperInvariant() }
    }
}
function Get-ForgeFile($name, $dest) {
    $expect = $hashMap[$name]
    if ((Test-Path -LiteralPath $dest) -and $expect -and ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash -eq $expect)) { return }
    if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Force }
    $part = "$dest.partial"
    $url = "$origin/$([uri]::EscapeDataString($name))"
    & curl.exe -fL --retry 5 --retry-all-errors --retry-delay 2 -o $part $url
    if ($LASTEXITCODE) { throw "Could not download $name from the FORGE project." }
    Move-Item -LiteralPath $part -Destination $dest -Force
    if ($expect -and (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash -ne $expect) {
        Remove-Item -LiteralPath $dest -Force
        throw "Downloaded $name does not match the FORGE project checksum."
    }
}
function Expand-ForgeZip($zip, $dest) {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    & tar.exe -xf $zip -C $dest
    if ($LASTEXITCODE) { throw "Could not extract $(Split-Path -Leaf $zip)" }
}
function Get-Tool($dir, $zipName, $binary) {
    $dest = Join-Path $runtime $dir
    $found = Get-ChildItem -LiteralPath $dest -Recurse -Filter $binary -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$found) {
        $zip = Join-Path $runtime "$dir.zip"
        Get-ForgeFile $zipName $zip
        Expand-ForgeZip $zip $dest
        Remove-Item -LiteralPath $zip -Force
        $found = Get-ChildItem -LiteralPath $dest -Recurse -Filter $binary | Select-Object -First 1
        if (!$found) { throw "Missing $binary in $dir" }
    }
    $found.FullName
}
try {
    Write-Output "Runtime code: $origin"
    $manifestPath = Join-Path $runtime 'manifest.json'
    $part = "$manifestPath.partial"
    & curl.exe -fL --retry 5 --retry-all-errors --retry-delay 2 -o $part "$origin/manifest.json"
    if ($LASTEXITCODE) { throw 'Could not download the runtime manifest from the FORGE project.' }
    Move-Item -LiteralPath $part -Destination $manifestPath -Force
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    Sync-Hashes $manifest

    $pyRoot = Join-Path $runtime 'python'
    $basePy = Join-Path $pyRoot ($manifest.pythonExe -replace '/', '\')
    if (!(Test-Path -LiteralPath $basePy)) {
        $zip = Join-Path $runtime 'python.zip'
        Get-ForgeFile $manifest.pythonZip $zip
        Expand-ForgeZip $zip $pyRoot
        Remove-Item -LiteralPath $zip -Force
    }
    $uvDir = Join-Path $runtime 'uv'
    $uvCmd = Get-ChildItem -LiteralPath $uvDir -Recurse -Filter uv.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$uvCmd) {
        $zip = Join-Path $runtime 'uv.zip'
        Get-ForgeFile $manifest.uvZip $zip
        Expand-ForgeZip $zip $uvDir
        Remove-Item -LiteralPath $zip -Force
        $uvCmd = Get-ChildItem -LiteralPath $uvDir -Recurse -Filter uv.exe | Select-Object -First 1
        if (!$uvCmd) { throw 'uv.exe is missing from the FORGE runtime archive.' }
    }
    $uv = $uvCmd.FullName
    $venv = Join-Path $runtime 'env'
    $py = Join-Path $venv 'Scripts\python.exe'
    if (!(Test-Path -LiteralPath $py)) {
        & $uv venv --python $basePy $venv
        if ($LASTEXITCODE) { throw 'Private Python installation failed.' }
    }
    # Redirected native stderr is a terminating error under Stop, even when the probe is meant to fail.
    $pref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $py -c "import torch,diffusers,transformers,accelerate; assert torch.version.hip" 2>$null
    $probe = $LASTEXITCODE
    $ErrorActionPreference = $pref
    if ($probe) {
        $house = Join-Path $runtime 'wheelhouse'
        New-Item -ItemType Directory -Force -Path $house | Out-Null
        $req = Join-Path $house 'requirements.txt'
        Get-ForgeFile $manifest.requirements $req
        foreach ($wheel in @($manifest.wheels)) { Get-ForgeFile $wheel (Join-Path $house $wheel) }
        & $uv pip install --python $py --offline --no-index --find-links $house -r $req
        if ($LASTEXITCODE) { throw 'Runtime packages failed to install from the FORGE project.' }
    }
    $torchLog = Join-Path $runtime 'torch-check.log'
    $ErrorActionPreference = 'Continue'
    & $py -c "import torch; assert torch.version.hip and torch.cuda.is_available(); print(torch.cuda.get_device_name(0), torch.ones(1, device='cuda').cpu())" 2>$torchLog
    $torchCode = $LASTEXITCODE
    $ErrorActionPreference = $pref
    if ($torchCode) { throw "The AMD driver failed the ROCm tensor test. $(if (Test-Path -LiteralPath $torchLog) { Get-Content -LiteralPath $torchLog -Raw })" }
    $tools = @{}
    foreach ($tool in @($manifest.tools)) { $tools[$tool.dir] = Get-Tool $tool.dir $tool.zip $tool.binary }

    $env:HF_HUB_CACHE = Join-Path $weights 'hf'
    $env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    $fluxLog = Join-Path $runtime 'flux-download.log'
    $ErrorActionPreference = 'Continue'
    $flux = & $py -c "from huggingface_hub import snapshot_download; print(snapshot_download('black-forest-labs/FLUX.1-schnell',revision='169573f54945f633efbe126a40a5676b4228363c',allow_patterns=['model_index.json','scheduler/*','tokenizer*/*','text_encoder*/*.json','text_encoder*/*.safetensors','transformer/*.json','transformer/*.safetensors','vae/*.json','vae/*.safetensors']))" 2>$fluxLog
    $fluxCode = $LASTEXITCODE
    $ErrorActionPreference = $pref
    if ($fluxCode) { throw "FLUX download failed. Accept the FLUX.1-schnell license on Hugging Face and sign in on this PC. $(if (Test-Path -LiteralPath $fluxLog) { Get-Content -LiteralPath $fluxLog -Raw })" }
    $models = Join-Path $weights 'trellis'
    $trellisLog = Join-Path $runtime 'trellis-download.log'
    $ErrorActionPreference = 'Continue'
    & $py -c "import sys; from huggingface_hub import snapshot_download; snapshot_download('ilintar/trellis2-gguf', local_dir=sys.argv[1], allow_patterns=['birefnet.gguf','dinov3.gguf','ss_flow.gguf','ss_dec.gguf','shape_flow_512.gguf','shape_flow_1024.gguf','shape_dec.gguf','tex_flow_512.gguf','tex_flow_1024.gguf','tex_dec.gguf'])" $models 2>$trellisLog
    $trellisCode = $LASTEXITCODE
    $ErrorActionPreference = $pref
    if ($trellisCode) { throw "TRELLIS weight download failed. $(if (Test-Path -LiteralPath $trellisLog) { Get-Content -LiteralPath $trellisLog -Raw })" }
    $config = @{
        python = $py
        enhancerPython = $py
        flux = $flux.Trim()
        models = $models
        trellis = $tools['trellis']
        blender = $tools['blender']
        upscaler = $tools['upscale']
        output = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'FORGE')
    }
    $config | ConvertTo-Json | Set-Content (Join-Path $runtime 'config.json') -Encoding UTF8
    Write-Output 'Runtime setup finished.'
    & $py (Join-Path $PSScriptRoot 'setup-extras.py') $runtime
    if ($LASTEXITCODE) { throw 'FORGE chat and rigging tools could not be installed. Open FORGE to resume.' }
} catch {
    Write-Output ("SETUP FAILED: " + $_.Exception.Message)
    throw
} finally { Stop-Transcript; $setupMutex.ReleaseMutex(); $setupMutex.Dispose() }
