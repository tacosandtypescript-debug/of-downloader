# Atajo público. Implementación: deploy/windows/instalar.ps1
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
if ($here -and (Test-Path (Join-Path $here "deploy\windows\instalar.ps1"))) {
    & (Join-Path $here "deploy\windows\instalar.ps1") @args
    exit $LASTEXITCODE
}
throw "Ejecuta este script desde el clon del repositorio: .\deploy\windows\instalar.ps1"
