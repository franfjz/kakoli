# Build local de kakoli para Windows con Nuitka.
#
# La lógica de compilación y empaquetado vive en build.py (fuente ÚNICA, compartida
# con el CI de GitHub Actions). Este script solo comprueba los requisitos de Windows
# (MSVC) y llama a build.py, para que los flags no se dupliquen ni se desincronicen.
#
#   .\build_nuitka.ps1                 # build + paquete .zip en dist\
#   .\build_nuitka.ps1 -Version v1.8.0-alpha
#   .\build_nuitka.ps1 -DryRun         # solo muestra el comando de Nuitka
#   .\build_nuitka.ps1 -Limpiar        # borra builds anteriores y recompila

param(
    [string]$Version = "",
    [switch]$Limpiar = $false,
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"
Write-Host "=== Build kakoli (Windows) con Nuitka ===" -ForegroundColor Cyan

# Nuitka disponible en el venv
& .\.venv\Scripts\python.exe -m nuitka --version | Out-Null
if (-not $?) {
    Write-Host "ERROR: Nuitka no esta instalado. Ejecuta: .\.venv\Scripts\python.exe -m pip install nuitka" -ForegroundColor Red
    exit 1
}

# Compilador C (MSVC)
$msvcPath = Get-Command cl.exe -ErrorAction SilentlyContinue
if (-not $msvcPath) {
    Write-Host "ADVERTENCIA: No se encontro cl.exe (MSVC). Instala Microsoft C++ Build Tools:" -ForegroundColor Yellow
    Write-Host "  https://visualstudio.microsoft.com/visual-cpp-build-tools/" -ForegroundColor Yellow
}

if ($Limpiar) {
    Write-Host "Eliminando builds anteriores..."
    foreach ($d in @("dist", "build_out", "kakoli.build", "kakoli.dist", "kakoli.onefile-build")) {
        if (Test-Path $d) { Remove-Item -Recurse -Force $d }
    }
}

# Argumentos para build.py
$py_args = @("build.py")
if ($Version) { $py_args += @("--version", $Version) }
if ($DryRun)  { $py_args += "--dry-run" }

Write-Host "Compilando (esto puede tardar varios minutos la primera vez)..." -ForegroundColor Green
& .\.venv\Scripts\python.exe @py_args
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: build fallo" -ForegroundColor Red
    exit 1
}
Write-Host "BUILD OK" -ForegroundColor Green
