param([Parameter(Position=0)][ValidateSet('image','model','enhance')]$Mode,[Parameter(ValueFromRemainingArguments=$true)][string[]]$Words)
$ErrorActionPreference='Stop'
$cfg=Join-Path $PSScriptRoot 'development.json'
if(!(Test-Path $cfg)){
    $cfg=Join-Path $env:LOCALAPPDATA 'FORGE Data\runtime\config.json'
    if(!(Test-Path $cfg)){& (Join-Path $PSScriptRoot 'setup-runtime.ps1')}
}
$setup=Get-Content -LiteralPath $cfg -Raw | ConvertFrom-Json
& $setup.python -u (Join-Path $PSScriptRoot 'runner.py') --config $cfg --mode $Mode @Words
exit $LASTEXITCODE
