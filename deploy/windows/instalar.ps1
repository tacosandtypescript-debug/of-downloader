$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
& (Join-Path $Root "instalar-windows.ps1") @args
exit $LASTEXITCODE

