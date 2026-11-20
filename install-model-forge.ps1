[CmdletBinding()]
param([switch]$VerifyOnly)
$ErrorActionPreference='Stop'
$project=(Resolve-Path $PSScriptRoot).Path
$cfg=Get-Content (Join-Path $project 'model_forge_local\model_forge_config.json') -Raw | ConvertFrom-Json
$checks=@($cfg.python,$cfg.commands.infer,$cfg.commands.background,$cfg.commands.dimension,$cfg.commands.transit,$cfg.commands.rig)
foreach($p in $checks){ if(Test-Path $p){Write-Host "OK  $p" -ForegroundColor Green}else{Write-Warning "MISSING  $p"} }
$py=$cfg.python
if(!(Test-Path $py)){throw "ROCm Python runtime not found: $py"}
& $py -c "import torch; print('Torch:',torch.__version__); print('ROCm:',torch.version.hip); print('GPU available:',torch.cuda.is_available()); print('GPU:',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
if($VerifyOnly){exit 0}
$env:PATH='C:\Projects\Structure;C:\Projects\Img;C:\Projects\Background;'+$env:PATH
$env:PYTHONPATH=(Join-Path $project 'model_forge_local')
Write-Host 'Model Forge local AMD environment verified.' -ForegroundColor Cyan
Write-Host 'No Ollama, network service, or cloud dependency is configured.' -ForegroundColor Cyan
Write-Host 'Use ModelForge.cmd to launch the UI.' -ForegroundColor Cyan
