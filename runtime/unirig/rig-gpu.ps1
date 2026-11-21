param(
    [Parameter(Mandatory)] [string] $Mesh,
    [Parameter(Mandatory)] [string] $Output
)

$ErrorActionPreference = 'Stop'
$meshPath = (Resolve-Path -LiteralPath $Mesh).Path
$outputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
if ([IO.Path]::GetExtension($outputPath) -ne '.fbx') {
    throw 'The output path must end in .fbx.'
}
if (Test-Path -LiteralPath $outputPath) {
    throw "Output already exists. Choose a new FBX path: $outputPath"
}

$root = $PSScriptRoot
$source = Join-Path $root 'UniRig-main'
$cpuPython = Join-Path $root 'python311-rocm\python.exe'
$gpuPython = Join-Path $root 'python312-rocm721\venv\Scripts\python.exe'
$work = Join-Path $root ('tmp\gpu-rig-' + [guid]::NewGuid().ToString('N'))
$inputData = Join-Path $work 'input'
$arOutput = Join-Path $work 'ar'
$skinOutput = Join-Path $work 'skin'
$modelName = [IO.Path]::GetFileNameWithoutExtension($meshPath)
$inputModelData = Join-Path (Join-Path $inputData $modelName) 'raw_data.npz'
$skeletonNpz = Join-Path (Join-Path $arOutput $modelName) 'predict_skeleton.npz'
$skinNpz = Join-Path (Join-Path $skinOutput $modelName) 'predict_skin.npz'

if (!(Test-Path -LiteralPath $cpuPython -PathType Leaf)) { throw "Blender/bpy Python runtime not found: $cpuPython" }
if (!(Test-Path -LiteralPath $gpuPython -PathType Leaf)) { throw "ROCm Python 3.12 runtime not found: $gpuPython" }
New-Item -ItemType Directory -Path $inputData, $arOutput, $skinOutput, (Split-Path -Parent $outputPath) -Force | Out-Null

$previousRocm = $env:UNIRIG_ROCM
$previousCpu = $env:UNIRIG_CPU
$drive = $null
$mutex = New-Object System.Threading.Mutex($false, 'Local\FORGE-UniRig')
if (!$mutex.WaitOne(0)) { throw 'UniRig is already processing another model.' }
try {
    Push-Location $source

    # Keep Blender's Python 3.11 isolated to import/export. Model execution is
    # performed only by AMD's supported Python 3.12 + ROCm environment below.
    $env:UNIRIG_ROCM = '0'
    $env:UNIRIG_CPU = '0'
    $stamp = Get-Date -Format 'yyyy_MM_dd_HH_mm_ss'
    & $cpuPython -m src.data.extract '--config=configs/data/quick_inference.yaml' `
        '--require_suffix=obj,fbx,FBX,dae,glb,gltf,vrm' `
        '--faces_target_count=50000' '--num_runs=1' '--force_override=true' '--id=0' `
        "--time=$stamp" "--input=$meshPath" "--output_dir=$inputData"
    if ($LASTEXITCODE -ne 0) { throw "Mesh extraction stopped with exit code $LASTEXITCODE." }
    if (!(Test-Path -LiteralPath $inputModelData -PathType Leaf)) { throw 'Mesh extraction produced no raw_data.npz.' }

    # The model's portable operators run on the AMD GPU. Export is disabled in
    # these configs because bpy's Python ABI differs from the ROCm Python ABI.
    $drive = @('Z:', 'Y:', 'X:', 'W:', 'V:', 'U:') | Where-Object { !(Test-Path ($_ + '\')) } | Select-Object -First 1
    if (!$drive) { throw 'No free drive letter is available for the UniRig runtime.' }
    subst $drive (Join-Path $root 'python312-rocm721')
    if ($LASTEXITCODE) { $drive = $null; throw 'Could not mount the UniRig runtime.' }
    $gpuPythonDrive = Join-Path $drive 'venv\Scripts\python.exe'
    $env:UNIRIG_ROCM = '1'
    $env:UNIRIG_CPU = '0'
    & $gpuPythonDrive -c "import torch; assert torch.version.hip and torch.cuda.is_available(), 'ROCm GPU unavailable'; x=torch.ones(4,device='cuda'); print('GPU preflight:',torch.cuda.get_device_name(0),'| tensor:',(x+1).sum().item())"
    if ($LASTEXITCODE -ne 0) { throw 'The RX 9060 XT did not pass the ROCm tensor preflight.' }

    & $gpuPythonDrive run.py '--task=configs/task/quick_inference_skeleton_articulationxl_ar_256_rocm.yaml' `
        '--seed=12345' "--input=$meshPath" "--npz_dir=$inputData" "--output_dir=$arOutput"
    if ($LASTEXITCODE -ne 0) { throw "UniRig skeleton inference stopped with exit code $LASTEXITCODE." }
    if (!(Test-Path -LiteralPath $skeletonNpz -PathType Leaf)) { throw 'Skeleton inference produced no prediction NPZ.' }

    & $gpuPythonDrive run.py '--task=configs/task/quick_inference_unirig_skin_rocm.yaml' `
        '--seed=12345' "--input=$meshPath" "--npz_dir=$arOutput" "--output_dir=$skinOutput" `
        '--data_name=predict_skeleton.npz'
    if ($LASTEXITCODE -ne 0) { throw "UniRig skin inference stopped with exit code $LASTEXITCODE." }
    if (!(Test-Path -LiteralPath $skinNpz -PathType Leaf)) { throw 'Skin inference produced no prediction NPZ.' }

    $env:UNIRIG_ROCM = '0'
    & $cpuPython tools/export_rocm_fbx.py "--source=$inputModelData" "--skeleton=$skeletonNpz" `
        "--skin=$skinNpz" "--output=$outputPath"
    if ($LASTEXITCODE -ne 0) { throw "Blender FBX export stopped with exit code $LASTEXITCODE." }
    Get-Item -LiteralPath $outputPath
}
finally {
    if ((Get-Location).Path -eq $source) { Pop-Location }
    $env:UNIRIG_ROCM = $previousRocm
    $env:UNIRIG_CPU = $previousCpu
    if ($drive) { subst $drive /d }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
