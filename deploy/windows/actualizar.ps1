$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "instalar.ps1") @args
exit $LASTEXITCODE
