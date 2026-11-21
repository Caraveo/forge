param(
    [Parameter(Mandatory, Position=0)][string]$Mesh,
    [Parameter(Position=1)][string]$Output
)
$ErrorActionPreference = 'Stop'
$inputPath = (Resolve-Path -LiteralPath $Mesh).Path
if (!$Output) { $Output = Join-Path (Get-Location) ([IO.Path]::GetFileNameWithoutExtension($inputPath) + '-rigged.fbx') }
$runtime = Join-Path $env:LOCALAPPDATA 'FORGE-Data\runtime\unirig'
$launcher = Join-Path $runtime 'rig-gpu.ps1'
if (!(Test-Path -LiteralPath $launcher)) { throw 'UniRig runtime is missing. Run FORGE setup to install it.' }
& $launcher -Mesh $inputPath -Output $Output
