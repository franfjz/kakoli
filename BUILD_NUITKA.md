# Compilación de kakoli con Nuitka

kakoli se distribuye como un único `.exe` nativo compilado con **Nuitka** (Python → C).
No requiere Python instalado en la máquina destino ni contiene los `.py` fuente.

## Requisitos (solo para compilar)

### Windows
- **Microsoft C++ Build Tools** (necesario)
  - Descarga desde: https://visualstudio.microsoft.com/visual-cpp-build-tools/
  - Selecciona "Desktop development with C++" durante la instalación
- **Nuitka** en el entorno virtual: `./.venv/Scripts/python.exe -m pip install nuitka`
- **Dependency Walker** (lo descarga Nuitka automáticamente la primera vez)

## Compilación

### Build estándar
```powershell
.\build_nuitka.ps1
```
Resultado: `dist\kakoli.exe` (ejecutable nativo, ~10 MB).

### Build limpio
```powershell
.\build_nuitka.ps1 -Limpiar
```
Elimina builds anteriores y recompila desde cero. Recomendado tras cambiar opciones
de empaquetado (datos incluidos, versión, carpeta de extracción…).

### Build con debug
```powershell
.\build_nuitka.ps1 -Debug
```
Muestra información detallada sobre módulos importados y optimizaciones.

## Qué incluye el build (`build_nuitka.ps1`)

- `--onefile` con `--onefile-tempdir-spec={CACHE_DIR}/kakoli/{VERSION}`: extrae a una
  carpeta cacheada por versión (no a un `%TEMP%` nuevo cada arranque), de modo que el
  primer arranque descomprime una vez y los siguientes reutilizan — clave en equipos
  antiguos con disco mecánico.
- `--include-data-dir=fuentes=fuentes` y `--include-data-dir=iconos=iconos`: empaqueta
  la fuente Space Mono y los iconos. Sin esto la app caería a la fuente del sistema y
  al icono por defecto de Tk.
- `--plugin-enable=tk-inter`: soporte de Tkinter.
- `--lto=yes`: optimización en el enlace (binario más pequeño y algo más rápido).
- Metadatos de versión de Windows (producto/empresa/descripción) e icono del `.exe`.

## Uso

Una vez compilado, ejecutar `dist\kakoli.exe` (o doble clic desde el Explorador).

## Notas

- La primera compilación toma 2-5 minutos; las siguientes son más rápidas (caché).
- El ejecutable NO requiere Python instalado ni contiene los archivos fuente (.py).
- Solo x64 de Windows.

## Troubleshooting

### "cl.exe no encontrado"
Instala Microsoft C++ Build Tools desde el enlace de Requisitos.

### "Dependency Walker failed"
Puede ser un problema temporal. Reinicia e intenta de nuevo.

### "ModuleNotFoundError" en tiempo de ejecución
Agrega el package faltante a la lista `--include-package` en `build_nuitka.ps1`.

### La app se ve con otra fuente o sin icono
Falta incluir los datos: comprueba que `build_nuitka.ps1` mantiene los dos
`--include-data-dir` y recompila con `-Limpiar`.
