# Script para compilar kakoli con Nuitka
# Requisitos: Microsoft C++ Build Tools instalados

param(
    [switch]$Limpiar = $false,
    [switch]$Debug = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=== Build kakoli con Nuitka ===" -ForegroundColor Cyan

# Verificar que Nuitka esté disponible
Write-Host "Verificando Nuitka..."
& .\.venv\Scripts\python.exe -m nuitka --version | Out-Null
if (-not $?) {
    Write-Host "ERROR: Nuitka no esta instalado. Ejecuta: pip install nuitka" -ForegroundColor Red
    exit 1
}

# Verificar MSVC
Write-Host "Verificando compilador C (MSVC)..."
$msvcPath = Get-Command cl.exe -ErrorAction SilentlyContinue
if (-not $msvcPath) {
    Write-Host "ADVERTENCIA: No se encontro cl.exe (MSVC)." -ForegroundColor Yellow
    Write-Host "Descarga e instala Microsoft C++ Build Tools desde:" -ForegroundColor Yellow
    Write-Host "  https://visualstudio.microsoft.com/visual-cpp-build-tools/" -ForegroundColor Yellow
    Write-Host "Continuando... (el build fallara si MSVC no esta disponible)" -ForegroundColor Yellow
}

# Limpiar builds anteriores si se pide
if ($Limpiar) {
    Write-Host "Eliminando builds anteriores..."
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "kakoli.build") { Remove-Item -Recurse -Force "kakoli.build" }
}

# Argumentos base
$args_build = @(
    "--onefile",
    # Onefile extrae a una carpeta CACHEADA por version (no a un %TEMP% nuevo en cada
    # arranque): en un HDD lento el primer arranque descomprime una vez y los
    # siguientes reutilizan, evitando la re-extraccion que penaliza a equipos antiguos.
    "--onefile-tempdir-spec={CACHE_DIR}/kakoli/{VERSION}",
    "--windows-console-mode=attach",
    "--include-package=core",
    "--include-package=gui",
    "--include-package=tasks",
    # Datos empaquetados (fuente Space Mono e iconos): sin esto la app cae a la fuente
    # del sistema y al icono por defecto de Tk.
    "--include-data-dir=fuentes=fuentes",
    "--include-data-dir=iconos=iconos",
    "--plugin-enable=tk-inter",
    # Optimizacion en el enlace: binario mas pequeno y algo mas rapido.
    "--lto=yes",
    "--windows-icon-from-ico=iconos/kakoli.ico",
    "--windows-product-version=1.8.0.0",
    "--windows-file-version=1.8.0.0",
    "--windows-product-name=Kakoli",
    "--windows-company-name=Kakoli Project",
    "--windows-file-description=Herramienta de compresion de archivos",
    "--assume-yes-for-downloads",
    "--output-dir=dist",
    "kakoli.py"
)

# Agregar modo debug si se pide
if ($Debug) {
    Write-Host "Modo debug habilitado (mas lento, mas info)" -ForegroundColor Yellow
    $args_build += "--debug"
    $args_build += "--show-modules"
}

Write-Host ""
Write-Host "Comenzando compilacion..." -ForegroundColor Green
Write-Host "Esto puede tomar 2-5 minutos la primera vez."
Write-Host ""

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
& .\.venv\Scripts\python.exe -m nuitka @args_build

if ($LASTEXITCODE -eq 0) {
    $stopwatch.Stop()
    $exe = Get-Item "dist\kakoli.exe" -ErrorAction SilentlyContinue
    if ($exe) {
        $size_bytes = $exe.Length
        $size_mb = $size_bytes / 1024 / 1024
        $size_mb = [Math]::Round($size_mb, 2)
        $tiempo_s = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 1)
        Write-Host ""
        Write-Host "BUILD EXITOSO" -ForegroundColor Green
        Write-Host "  Ejecutable: dist\kakoli.exe" -ForegroundColor Green
        Write-Host "  Tamano: $size_mb MB" -ForegroundColor Green
        Write-Host "  Tiempo: $tiempo_s segundos" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "ERROR: Build completo pero no se encontro kakoli.exe" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "ERROR: BUILD FALLO" -ForegroundColor Red
    exit 1
}
