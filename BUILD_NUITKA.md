# Build y release de kakoli (Nuitka, multiplataforma)

kakoli se distribuye como un único ejecutable nativo compilado con **Nuitka**
(Python → C), para **Windows x64** y **Linux x64**. La lógica de compilación y
empaquetado está centralizada en **[`build.py`](build.py)** (una sola fuente de
verdad), que usan tanto el CI como el build local.

## Arquitectura

```
                    git tag vX.Y.Z ─► GitHub Actions (.github/workflows/release.yml)
                                         │
                          ┌──────────────┴──────────────┐
                     Windows runner                 Linux runner
                     Python 3.14                    Python 3.14
                     python build.py                python build.py
                          │                              │
                   kakoli-…-windows-x64.zip       kakoli-…-linux-x64.tar.gz
                          └──────────────┬──────────────┘
                                   GitHub Release (ambos assets)
```

Un mismo tag genera un único Release con los dos paquetes.

## Release automático (recomendado)

Basta con crear y empujar un tag de versión:

```bash
git tag v1.8.0-alpha
git push origin v1.8.0-alpha
```

Esto dispara el workflow, que compila en paralelo en Windows y Linux y publica un
Release con:

```
kakoli-1.8.0-alpha-windows-x64.zip
kakoli-1.8.0-alpha-linux-x64.tar.gz
```

Los tags con sufijo (`-alpha`, `-beta`, `-rc1`…) se marcan como *pre-release*.
`workflow_dispatch` (pestaña **Actions → Release → Run workflow**) permite un ensayo
manual: compila y deja los paquetes como *artifacts*, sin crear Release.

## Build local (Windows)

Requiere **Microsoft C++ Build Tools** (MSVC) y Nuitka en el entorno virtual
(`./.venv/Scripts/python.exe -m pip install nuitka tkinterdnd2`).

```powershell
.\build_nuitka.ps1 -Limpiar        # build + paquete .zip en dist\
.\build_nuitka.ps1 -DryRun         # solo muestra el comando de Nuitka
.\build_nuitka.ps1 -Version v1.8.0-alpha
```

`build_nuitka.ps1` solo comprueba MSVC y llama a `build.py`.

## Build local (Linux)

```bash
sudo apt-get install -y python3-tk tk-dev patchelf
python -m pip install nuitka tkinterdnd2
python build.py --version v1.8.0-alpha     # genera dist/kakoli-…-linux-x64.tar.gz
```

## Qué incluye el build (`build.py`)

- `--onefile` (en Windows, con `--onefile-tempdir-spec` cacheado por versión para
  arranque rápido en disco mecánico).
- Fuente Space Mono e iconos (`--include-data-dir`).
- Arrastrar y soltar (`tkinterdnd2`, con degradación elegante si el nativo no carga).
- `--lto=yes` (binario más pequeño y algo más rápido).
- En Windows: icono `.ico`, metadatos de versión de producto/archivo.
- En Linux: icono PNG.

## Notas

- La versión se toma del tag (`--version`), o de `gui/constantes.py` (`VERSION`) si
  no se indica. Los metadatos de Windows usan el cuádruple numérico `X.Y.Z.0`.
- El ejecutable NO requiere Python en la máquina destino ni contiene los `.py`.
- La primera compilación tarda unos minutos (descarga utilidades de Nuitka).

## Troubleshooting

- **`cl.exe` no encontrado** (Windows): instala Microsoft C++ Build Tools.
- **Falla en Linux por Tk**: asegúrate de `python3-tk` / `tk-dev` en el runner.
- **`ModuleNotFoundError` en runtime**: añade el paquete a `--include-package` en
  `build.py`.
