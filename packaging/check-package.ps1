param([string]$Dist=(Join-Path (Split-Path $PSScriptRoot -Parent) 'dist'),
      [string]$AppDir=(Join-Path $Dist 'payload'))
$ErrorActionPreference='Stop'
$msi=Join-Path $Dist 'FORGE-v0.05-x64.msi'
$exe=Join-Path $Dist 'FORGE-v0.05-Setup.exe'
$assembly=[Reflection.Assembly]::LoadFile((Resolve-Path $exe).Path)
$stream=$assembly.GetManifestResourceStream('FORGE.msi')
try {
    $embedded=(Get-FileHash -InputStream $stream).Hash
    if($embedded -ne (Get-FileHash $msi).Hash){throw 'Embedded MSI hash mismatch.'}
} finally {$stream.Dispose()}
$installer=New-Object -ComObject WindowsInstaller.Installer
$db=$installer.OpenDatabase($msi,0)
$view=$db.OpenView('SELECT FileName, FileSize FROM File')
$view.Execute()
$count=0
while($record=$view.Fetch()){
    $name=($record.StringData(1) -split '\|')[-1]
    $source=Get-Item -LiteralPath (Join-Path $AppDir $name)
    if($source.Length -ne $record.IntegerData(2)){throw "Wrong size for $name"}
    $count++
}
if($count -lt 10){throw 'Incomplete MSI payload'}
Write-Host "Verified embedded MSI SHA256 $embedded and $count file records."
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$routing=Join-Path $Dist 'check-routing.exe'
& $compiler /nologo /target:exe "/out:$routing" (Join-Path $PSScriptRoot 'check-routing.cs') (Join-Path (Split-Path $PSScriptRoot -Parent) 'desktop\Intent.cs')
if($LASTEXITCODE){throw 'Routing test compilation failed'}
& $routing
if($LASTEXITCODE){throw 'Routing tests failed'}
