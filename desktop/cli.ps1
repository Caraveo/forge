# No param() block on purpose: [Parameter] attributes make this an advanced script, and
# PowerShell then binds runner flags such as --out to -OutVariable/-OutBuffer and fails.
$ErrorActionPreference='Stop'
$modes=@('image','model','enhance','upscale','background')
if($args.Count -lt 1 -or $modes -notcontains $args[0]){
    Write-Error ("Usage: cli.ps1 <" + ($modes -join '|') + "> [description or file] [--out PATH] [runner options]")
    exit 2
}
$Mode=[string]$args[0]
[string[]]$Words=@($args | Select-Object -Skip 1)
$cfg=Join-Path $PSScriptRoot 'development.json'
if(!(Test-Path $cfg)){
    $cfg=Join-Path $env:LOCALAPPDATA 'FORGE-Data\runtime\config.json'
    if(!(Test-Path $cfg)){& (Join-Path $PSScriptRoot 'setup-runtime.ps1')}
}
$setup=Get-Content -LiteralPath $cfg -Raw | ConvertFrom-Json
if ($Mode -in @('upscale','background') -and $Words.Count -gt 0 -and !$Words[0].StartsWith('--')) {
    $Words = @('--input', $Words[0]) + @($Words | Select-Object -Skip 1)
}
& $setup.python -u (Join-Path $PSScriptRoot 'runner.py') --config $cfg --mode $Mode @Words
exit $LASTEXITCODE
