#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build.py — compila kakoli con Nuitka y empaqueta el resultado, en Windows y Linux,
desde una ÚNICA fuente de verdad (este script).

Es el corazón del sistema de build/release: tanto el workflow de GitHub Actions
(`.github/workflows/release.yml`) como el atajo local de Windows (`build_nuitka.ps1`)
lo invocan, así que los flags de Nuitka y el empaquetado no se duplican ni se
desincronizan entre plataformas.

Uso:
    python build.py [--version X.Y.Z] [--dry-run] [--no-package]

- `--version`  versión a incrustar y a usar en el nombre del paquete. Por defecto se
               lee de `gui/constantes.py` (VERSION). Acepta el nombre del tag con o
               sin la `v` inicial (p. ej. `v1.8.0-alpha` -> `1.8.0-alpha`).
- `--dry-run`  imprime el comando de Nuitka y sale (no compila). Para verificar.
- `--no-package`  compila pero no genera el .zip/.tar.gz (deja el binario en build_out/).

Salida (por defecto): `dist/kakoli-<version>-<plataforma>-x64.(zip|tar.gz)`, donde
<plataforma> es `windows-x64` o `linux-x64`.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

APP = "kakoli"
RAIZ = Path(__file__).resolve().parent
DIR_BUILD = RAIZ / "build_out"       # salida intermedia de Nuitka
DIR_DIST = RAIZ / "dist"             # paquetes finales (.zip / .tar.gz)


# ---------------------------------------------------------------- versión
def _version_de_constantes() -> str:
    """Lee VERSION de gui/constantes.py sin importar el módulo (evita cargar Tk)."""
    texto = (RAIZ / "gui" / "constantes.py").read_text(encoding="utf-8")
    m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', texto, re.MULTILINE)
    return m.group(1) if m else "0.0.0"


def normalizar_version(v: "str | None") -> str:
    """Quita la `v` inicial de un tag (`v1.8.0-alpha` -> `1.8.0-alpha`)."""
    v = (v or _version_de_constantes()).strip()
    return v[1:] if re.match(r"^v\d", v) else v


def version_numerica(v: str) -> str:
    """Cuádruple numérico X.Y.Z.0 para los metadatos de Windows (que no admiten
    sufijos como `-alpha`). `1.8.0-alpha` -> `1.8.0.0`; sin número -> `0.0.0.0`."""
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}.0" if m else "0.0.0.0"


# ---------------------------------------------------------------- plataforma
def plataforma() -> tuple[str, str]:
    """(etiqueta, formato_de_archivo) para esta plataforma."""
    if sys.platform.startswith("win"):
        return "windows-x64", "zip"
    if sys.platform.startswith("linux"):
        return "linux-x64", "gztar"
    if sys.platform == "darwin":
        return "macos-x64", "gztar"
    return "unknown-x64", "gztar"


# ---------------------------------------------------------------- flags Nuitka
def comando_nuitka(version: str) -> list[str]:
    """Construye el comando de Nuitka: comunes + específicos de la plataforma."""
    comunes = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--assume-yes-for-downloads",
        "--enable-plugin=tk-inter",
        "--include-package=core",
        "--include-package=gui",
        "--include-package=tasks",
        # Arrastrar y soltar (opcional en runtime; degrada si el nativo no carga).
        "--include-package=tkinterdnd2",
        "--include-package-data=tkinterdnd2",
        # Datos: fuente Space Mono e iconos.
        "--include-data-dir=fuentes=fuentes",
        "--include-data-dir=iconos=iconos",
        "--lto=yes",
        f"--output-dir={DIR_BUILD}",
        f"--output-filename={APP}",
    ]
    if sys.platform.startswith("win"):
        num = version_numerica(version)
        especificos = [
            "--windows-console-mode=attach",
            "--windows-icon-from-ico=iconos/kakoli.ico",
            # Extrae a una carpeta cacheada por versión (arranque rápido en HDD).
            "--onefile-tempdir-spec={CACHE_DIR}/kakoli/{VERSION}",
            f"--windows-product-version={num}",
            f"--windows-file-version={num}",
            "--windows-product-name=Kakoli",
            "--windows-company-name=Kakoli Project",
            "--windows-file-description=Herramientas de gestion de directorios y archivos",
        ]
    else:
        especificos = [
            "--linux-icon=iconos/icono_piramide_jungla_256.png",
        ]
    return comunes + especificos + ["kakoli.py"]


# ---------------------------------------------------------------- empaquetado
def _binario_generado() -> Path:
    """Localiza el ejecutable que dejó Nuitka en build_out/ (kakoli o kakoli.exe)."""
    for nombre in (f"{APP}.exe", APP, f"{APP}.bin"):
        ruta = DIR_BUILD / nombre
        if ruta.exists():
            return ruta
    encontrados = [p for p in DIR_BUILD.glob(f"{APP}*") if p.is_file()]
    if encontrados:
        return encontrados[0]
    raise FileNotFoundError(f"No se encontró el binario de Nuitka en {DIR_BUILD}")


def empaquetar(version: str, etiqueta: str, formato: str) -> Path:
    """Crea `dist/kakoli-<version>-<etiqueta>.(zip|tar.gz)` con el binario, la
    licencia y el README dentro de una carpeta con el mismo nombre."""
    binario = _binario_generado()
    nombre_pkg = f"{APP}-{version}-{etiqueta}"
    stage = DIR_DIST / "stage" / nombre_pkg
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    shutil.copy2(binario, stage / binario.name)
    for extra in ("LICENSE", "README.md"):
        if (RAIZ / extra).exists():
            shutil.copy2(RAIZ / extra, stage / extra)

    base = DIR_DIST / nombre_pkg
    archivo = shutil.make_archive(str(base), formato,
                                  root_dir=str(DIR_DIST / "stage"),
                                  base_dir=nombre_pkg)
    shutil.rmtree(DIR_DIST / "stage", ignore_errors=True)
    return Path(archivo)


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="Build y empaquetado de kakoli (Nuitka).")
    ap.add_argument("--version", help="versión a incrustar (por defecto: gui/constantes.py)")
    ap.add_argument("--dry-run", action="store_true",
                    help="imprime el comando de Nuitka y sale (no compila)")
    ap.add_argument("--no-package", action="store_true",
                    help="compila pero no genera el .zip/.tar.gz")
    args = ap.parse_args()

    version = normalizar_version(args.version)
    etiqueta, formato = plataforma()
    cmd = comando_nuitka(version)

    print(f"kakoli build — versión {version} — plataforma {etiqueta}")
    print("Nuitka:\n  " + " \\\n  ".join(cmd))
    if args.dry_run:
        return 0

    DIR_BUILD.mkdir(exist_ok=True)
    subprocess.run(cmd, cwd=RAIZ, check=True)

    if args.no_package:
        print(f"Binario en {_binario_generado()}")
        return 0

    DIR_DIST.mkdir(exist_ok=True)
    paquete = empaquetar(version, etiqueta, formato)
    tam_mb = paquete.stat().st_size / 1024 / 1024
    print(f"\nPaquete: {paquete}  ({tam_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
