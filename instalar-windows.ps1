param(
    [switch]$InstallFFmpeg
)

$ErrorActionPreference = "Stop"

function Run-Checked($FilePath, $Arguments, $FailureMessage) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Get-RepoRoot {
    if ($env:OFDOWNLOADER_REPO -and (Test-Path (Join-Path $env:OFDOWNLOADER_REPO "ofbackup_cli.py"))) {
        return (Resolve-Path $env:OFDOWNLOADER_REPO).Path
    }
    if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "ofbackup_cli.py"))) {
        return $PSScriptRoot
    }
    $defaultRepo = Join-Path $env:USERPROFILE "of-downloader"
    if (-not (Test-Path (Join-Path $defaultRepo "ofbackup_cli.py"))) {
        if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
            throw "No encontre GitHub CLI. Instala gh desde https://cli.github.com/ y ejecuta: gh auth login"
        }
        if (Test-Path $defaultRepo) {
            throw "Existe $defaultRepo pero no parece ser OF Downloader. Borra esa carpeta o define OFDOWNLOADER_REPO."
        }
        Write-Host "Clonando repositorio privado en $defaultRepo..." -ForegroundColor Cyan
        Run-Checked "gh" @("repo", "clone", "tacosandtypescript-debug/of-downloader", $defaultRepo) "No se pudo clonar el repositorio privado."
    }
    if (Test-Path (Join-Path $defaultRepo ".git")) {
        Run-Checked "git" @("-C", $defaultRepo, "pull", "--ff-only", "origin", "main") "No se pudo actualizar el repositorio."
    }
    return $defaultRepo
}

function Step-Info($Text) {
    Write-Host ""
    Write-Host $Text -ForegroundColor Cyan
}

function Python-Candidates {
    $items = @(
        @{ Command = "py"; Args = @("-3.12") },
        @{ Command = "py"; Args = @("-3.11") },
        @{ Command = "python"; Args = @() }
    )
    $localPrograms = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $localPrograms) {
        Get-ChildItem -Path $localPrograms -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
            ForEach-Object { $items += @{ Command = $_.FullName; Args = @() } }
    }
    $programFiles = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    foreach ($root in $programFiles) {
        $pythonRoot = Join-Path $root "Python312"
        $exe = Join-Path $pythonRoot "python.exe"
        if (Test-Path $exe) {
            $items += @{ Command = $exe; Args = @() }
        }
    }
    return $items
}

function Install-Python312 {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        return $false
    }
    Write-Host "No encontre Python 3.12/3.11. Intentare instalar Python 3.12 con winget..." -ForegroundColor Yellow
    Run-Checked "winget" @(
        "install",
        "--id", "Python.Python.3.12",
        "-e",
        "--accept-package-agreements",
        "--accept-source-agreements"
    ) "No se pudo instalar Python 3.12 automaticamente con winget."
    return $true
}

function Find-Python {
    foreach ($candidate in (Python-Candidates)) {
        $command = $candidate.Command
        $candidateArgs = @($candidate.Args)
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
            continue
        }
        $args = @($candidateArgs)
        $args += @("-c", "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,13) else 1)")
        try {
            & $command @args > $null 2> $null
        } catch {
            continue
        }
        if ($LASTEXITCODE -eq 0) {
            return @{ Command = $command; Args = $candidateArgs }
        }
    }
    if (Install-Python312) {
        foreach ($candidate in (Python-Candidates)) {
            $command = $candidate.Command
            $candidateArgs = @($candidate.Args)
            if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
                continue
            }
            $args = @($candidateArgs)
            $args += @("-c", "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,13) else 1)")
            try {
                & $command @args > $null 2> $null
            } catch {
                continue
            }
            if ($LASTEXITCODE -eq 0) {
                return @{ Command = $command; Args = $candidateArgs }
            }
        }
    }
    throw "No encontre Python 3.11 o 3.12. En Windows no uses Python 3.13 para esta app porque varias dependencias pueden intentar compilarse. Instala Python 3.12 desde https://www.python.org/downloads/windows/ y marca 'Add Python to PATH'."
}

function Test-CompatibleVenv($PythonPath) {
    if (-not (Test-Path $PythonPath)) {
        return $false
    }
    & $PythonPath -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,13) else 1)" > $null 2> $null
    return ($LASTEXITCODE -eq 0)
}

function Add-UserPath($PathToAdd) {
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($current) {
        $parts = $current -split ";" | Where-Object { $_ }
    }
    if ($parts -notcontains $PathToAdd) {
        $next = (@($parts) + $PathToAdd) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $next, "User")
        $env:Path = "$env:Path;$PathToAdd"
        Write-Host "PATH de usuario actualizado. Abre una terminal nueva para usar 'of' desde cualquier carpeta." -ForegroundColor Yellow
    }
}

if ($env:OS -ne "Windows_NT") {
    throw "Este instalador es solo para Windows."
}

$repo = Get-RepoRoot
$venv = Join-Path $repo ".venv"
$python = Find-Python
$downloads = Join-Path $env:USERPROFILE "Downloads\OFDownloader"
$binDir = Join-Path $env:LOCALAPPDATA "Programs\OFDownloader\bin"
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"

Write-Host "OF Downloader - instalacion para Windows" -ForegroundColor Cyan
Write-Host "Puede tardar varios minutos en la primera ejecucion."

Step-Info "[1/5] Preparando carpetas..."
New-Item -ItemType Directory -Force -Path $downloads, $binDir | Out-Null

Step-Info "[2/5] Creando entorno privado de Python..."
$venvPython = Join-Path $venv "Scripts\python.exe"
if ((Test-Path $venv) -and -not (Test-CompatibleVenv $venvPython)) {
    Write-Host "La .venv existente usa una version de Python no compatible. Se recreara." -ForegroundColor Yellow
    Remove-Item -LiteralPath $venv -Recurse -Force
}
if (-not (Test-Path $venvPython)) {
    Run-Checked $python.Command @($python.Args + @("-m", "venv", $venv)) "No se pudo crear el entorno privado de Python."
}

Step-Info "[3/5] Instalando dependencias..."
Run-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip") "No se pudo actualizar pip."
Run-Checked $venvPython @("-m", "pip", "install", "-r", (Join-Path $repo "requirements.txt")) "No se pudieron instalar las dependencias. Si ves errores de Microsoft Visual C++, borra .venv e instala Python 3.12 o 3.11."

Step-Info "[4/5] Creando comandos..."
$ofTarget = Join-Path $binDir "of.cmd"
$guiTarget = Join-Path $binDir "of-downloader.cmd"
Set-Content -Path $ofTarget -Encoding ASCII -Value "@echo off`r`ncall `"$repo\of-windows.cmd`" %*`r`n"
Set-Content -Path $guiTarget -Encoding ASCII -Value "@echo off`r`ncall `"$repo\of-downloader-windows.cmd`" %*`r`n"
Add-UserPath $binDir

Step-Info "[5/5] Creando acceso del menu Inicio..."
$shortcutPath = Join-Path $startMenu "OF Downloader.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $guiTarget
$shortcut.WorkingDirectory = $repo
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,146"
$shortcut.Save()

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "AVISO: FFmpeg no esta instalado o no esta en PATH." -ForegroundColor Yellow
    if ($InstallFFmpeg) {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "Instalando FFmpeg con winget..."
            winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
        } else {
            Write-Host "No encontre winget. Instala FFmpeg manualmente: https://www.gyan.dev/ffmpeg/builds/" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Para videos, instala FFmpeg o ejecuta desde la carpeta del repo: .\instalar-windows.ps1 -InstallFFmpeg" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "OK: OF Downloader quedo instalado para Windows." -ForegroundColor Green
Write-Host "Abre una terminal nueva y ejecuta:"
Write-Host "  of"
Write-Host "  of-downloader"
Write-Host "Descargas: $downloads"
