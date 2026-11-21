# Developer build on the existing workstation. This file is excluded from the MSI.
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
$py='C:\Projects\Hunyuan3D-2\.venv\Scripts\python.exe'
& $py (Join-Path $PSScriptRoot 'build.py') --app-dir (Join-Path $project 'dist\app')
if ($LASTEXITCODE) { throw 'Desktop build failed' }
$config=@{
    python=$py
    enhancerPython=(Join-Path $env:USERPROFILE 'unirig\python311-rocm\python.exe')
    blender=(Get-ChildItem 'C:\Program Files\Blender Foundation' -Recurse -Filter blender.exe | Select-Object -Last 1).FullName
    trellis=(Join-Path $env:LOCALAPPDATA 'trellis-studio\runtime\trellis-cli.exe')
    models=(Join-Path $env:LOCALAPPDATA 'trellis-studio\models')
    flux='C:\Projects\Img\models\hf\models--black-forest-labs--FLUX.1-schnell\snapshots\169573f54945f633efbe126a40a5676b4228363c'
    upscaler=(Join-Path $env:USERPROFILE 'Super Pokemon World\.codex\realesrgan\realesrgan-ncnn-vulkan.exe')
    output=$project
    cache=(Join-Path $project 'dist\cache')
}
$config | ConvertTo-Json | Set-Content (Join-Path $project 'dist\app\development.json') -Encoding UTF8
