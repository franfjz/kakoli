#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
tasks/renombrar/motor.py — Renombra archivos en bloque (en un directorio o,
opcionalmente, en sus subdirectorios), SIN tocar la extensión:

  nuevo_nombre = prefijo + reemplazar(stem) + sufijo  (+ extensión intacta)

- prefijo: texto al inicio del nombre.
- reemplazar: sustituye un fragmento interno del nombre (`buscar` -> `reemplazar`),
  todas las ocurrencias o solo la primera, sensible o no a mayúsculas.
- sufijo: texto al final del nombre, ANTES de la extensión.

La extensión se preserva, incluidas las COMPUESTAS conocidas (`.tar.gz`, `.tar.bz2`…).

Modo `simular`: muestra `antes -> después` en el log sin tocar el disco (vista previa).
Conflictos (el nuevo nombre ya existe): `numerar` (nombre_2.ext) u `omitir`.

Uso por consola:
    python -m tasks.renombrar.motor CARPETA [--prefijo P] [--sufijo S]
        [--buscar B --reemplazar R] [--no-subdirectorios] [--simular] ...
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from core import recursos
from core.cli import correr_cli
from core.formato import duracion
from core.opciones import OpcionesBase
from core.resultado import Resultado
from core.control import Control

CONFLICTOS = ("numerar", "omitir")
PAUSE_NAME = "PAUSA"

# Extensiones COMPUESTAS que se preservan enteras (N2). El orden no importa; se
# compara en minúsculas y se elige la que case (todas empiezan por otra extensión).
EXT_COMPUESTAS = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst", ".tar.lz4",
                  ".tar.z", ".tar.lz", ".tar.lzma", ".user.js", ".d.ts")


@dataclass
class Opciones(OpcionesBase):
    prefijo: str = ""
    sufijo: str = ""
    buscar: str = ""
    reemplazar: str = ""
    sensible_mayusculas: bool = True
    solo_primera: bool = False
    recursivo: bool = True
    # seguir_enlaces / omitir_ocultos se heredan de OpcionesBase.
    conflicto: str = "numerar"            # numerar | omitir
    simular: bool = False


# ==========================================================================
# Transformación de nombre (pura, fácil de testear)
# ==========================================================================
def dividir_ext(nombre: str) -> tuple[str, str]:
    """Divide `nombre` en (stem, extensión), preservando extensiones compuestas
    conocidas. Un nombre que empieza por '.' sin más punto (p. ej. `.gitignore`) se
    considera sin extensión."""
    bajo = nombre.lower()
    for ce in EXT_COMPUESTAS:
        if bajo.endswith(ce) and len(nombre) > len(ce):
            return nombre[:-len(ce)], nombre[-len(ce):]
    stem, ext = os.path.splitext(nombre)
    return stem, ext


def _reemplazar(stem: str, opts: Opciones) -> str:
    if not opts.buscar:
        return stem
    if opts.sensible_mayusculas:
        cuenta = 1 if opts.solo_primera else -1
        return stem.replace(opts.buscar, opts.reemplazar, cuenta)
    # insensible a mayúsculas: regex con reemplazo LITERAL (sin backreferences)
    pat = re.compile(re.escape(opts.buscar), re.IGNORECASE)
    return pat.sub(lambda _m: opts.reemplazar, stem,
                   count=(1 if opts.solo_primera else 0))


def nuevo_nombre(nombre: str, opts: Opciones) -> str:
    """Aplica prefijo + reemplazo(stem) + sufijo, conservando la extensión."""
    stem, ext = dividir_ext(nombre)
    stem = opts.prefijo + _reemplazar(stem, opts) + opts.sufijo
    return stem + ext


# ==========================================================================
# Utilidades
# ==========================================================================
def _archivos(origen: Path, opts: Opciones) -> Iterator[Path]:
    """Archivos bajo `origen` (recursivo o solo el primer nivel)."""
    origen = Path(origen)
    if opts.recursivo:
        for dirpath, dirnames, filenames in os.walk(origen):
            if opts.omitir_ocultos:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for nombre in sorted(filenames):
                if opts.omitir_ocultos and nombre.startswith("."):
                    continue
                yield Path(dirpath) / nombre
    else:
        for p in sorted(origen.iterdir()):
            if p.is_file():
                if opts.omitir_ocultos and p.name.startswith("."):
                    continue
                yield p


def _mismo(a: Path, b: Path) -> bool:
    """¿`a` y `b` son el mismo archivo? (p. ej. renombrado que solo cambia de
    mayúsculas en Windows)."""
    try:
        if a.resolve() == b.resolve():
            return True
        return os.path.samefile(a, b)
    except OSError:
        return False


def _ocupado(dest: Path, src: Path, reservados: set[str]) -> bool:
    return (dest.as_posix() in reservados
            or (dest.exists() and not _mismo(src, dest)))


def _resolver(src: Path, nuevo: str, opts: Opciones,
              reservados: set[str]) -> str | None:
    """Devuelve el nombre final (numerado si hace falta) o None si se omite."""
    dest = src.with_name(nuevo)
    if not _ocupado(dest, src, reservados):
        return nuevo
    if opts.conflicto == "omitir":
        return None
    stem, ext = dividir_ext(nuevo)            # numerar preservando la extensión
    n = 2
    while True:
        cand = f"{stem}_{n}{ext}"
        if not _ocupado(src.with_name(cand), src, reservados):
            return cand
        n += 1


def rutas_validadas(origen: Path) -> Path:
    o = Path(origen).expanduser().resolve()
    if not o.exists():
        raise ValueError(f"La carpeta no existe: {origen}")
    if not o.is_dir():
        raise ValueError(f"'{origen}' no es una carpeta.")
    return o


def _hay_operacion(opts: Opciones) -> bool:
    return bool(opts.prefijo or opts.sufijo or opts.buscar)


# ==========================================================================
# Motor
# ==========================================================================
def ejecutar(entradas: dict, opts: Opciones, *, log: Callable[[str], None] = print,
             progreso=None, pausar=None, cancelar=None, confirmar=None) -> Resultado:
    """Contrato uniforme para la GUI (B). `entradas` = {"origen"}."""
    origen = entradas["origen"]
    log(f"Carpeta: {origen}")
    return procesar(origen, opts, log=log, progreso=progreso,
                    pausar=pausar, cancelar=cancelar, confirmar=confirmar)


def procesar(origen: Path, opts: Opciones, *,
             log: Callable[[str], None] = print,
             progreso: Callable[[int, int, float, str], None] | None = None,
             pausar: Callable[[], bool] | None = None,
             cancelar: Callable[[], bool] | None = None,
             confirmar: Callable[[str, bool], bool] | None = None) -> Resultado:
    """Renombra los archivos bajo `origen`. En modo `simular` no toca el disco."""
    t0 = time.monotonic()
    pausar = pausar or (lambda: False)
    cancelar = cancelar or (lambda: False)
    origen = Path(origen)
    if not _hay_operacion(opts):
        msg = "Indica al menos un cambio (prefijo, buscar/reemplazar o sufijo)."
        log(f"[!] {msg}")
        return Resultado("nada", 0, 0, 0, [msg], origen, msg, 0.0)

    # Registra el perfil de la máquina en el log y aplica el modo ligero
    # (transparencia); renombrar es secuencial, así que no se usa el retorno.
    recursos.preparar(origen, opts.politica, log=log)
    log("Explorando los archivos..." + (" (simulación)" if opts.simular else ""))
    items = list(_archivos(origen, opts))
    total = len(items)

    cont = {"hechos": 0, "renombrados": 0, "sin_cambios": 0, "omitidos": 0}
    errores: list[str] = []
    reservados: set[str] = set()               # rutas destino ya elegidas (para simular)
    pausa_ruta = origen.parent / PAUSE_NAME
    ctrl = Control(pausar=pausar, cancelar=cancelar, pausa_ruta=pausa_ruta)

    for src in items:
        if ctrl.debe_parar():
            break
        nombre = src.name
        nuevo = nuevo_nombre(nombre, opts)
        rel = src.relative_to(origen).as_posix()
        if not nuevo or nuevo == nombre:
            cont["sin_cambios"] += 1
        else:
            final = _resolver(src, nuevo, opts, reservados)
            if final is None:                  # conflicto -> omitir
                cont["omitidos"] += 1
                if opts.detallado or opts.simular:
                    log(f"  (omitido, ya existe) {rel} -> {nuevo}")
            else:
                dest = src.with_name(final)
                reservados.add(dest.as_posix())
                try:
                    if opts.simular:
                        log(f"  {rel} -> {final}")
                    else:
                        os.rename(src, dest)
                    cont["renombrados"] += 1
                    if opts.detallado and not opts.simular:
                        log(f"  {rel} -> {final}")
                except OSError as e:
                    errores.append(f"{src}: {e}")
                    log(f"[!] No se pudo renombrar {rel}: {e}")
        cont["hechos"] += 1
        h = cont["hechos"]
        if progreso and (h % 25 == 0 or h == total):
            progreso(h, total, min(1.0, (h / total) if total else 0.0), rel)

    seg = time.monotonic() - t0
    hechos = cont["hechos"]
    if ctrl.motivo:
        log(ctrl.motivo)
        return Resultado(ctrl.estado, hechos, max(0, total - hechos), total, errores,
                         origen, ctrl.motivo, seg)

    verbo = "Se renombrarían" if opts.simular else "Renombrados"
    log(f"{verbo}: {cont['renombrados']}; sin cambios: {cont['sin_cambios']}; "
        f"omitidos: {cont['omitidos']}; en {duracion(seg)}.")
    if opts.simular:
        log("(Simulación: no se ha modificado ningún archivo.)")
    if errores:
        log(f"[!] {len(errores)} archivos dieron error.")
    estado = "nada" if (cont["renombrados"] == 0 and not opts.simular) else "completado"
    return Resultado(estado, hechos, 0, total, errores, origen, "", seg)


# ==========================================================================
# Consola
# ==========================================================================
def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Renombra archivos en bloque sin tocar la extensión "
                    "(prefijo, reemplazo interno, sufijo).")
    p.add_argument("origen", type=Path, help="carpeta con los archivos a renombrar")
    p.add_argument("-y", "--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--prefijo", default="", help="texto al inicio del nombre")
    p.add_argument("--sufijo", default="", help="texto al final (antes de la extensión)")
    p.add_argument("--buscar", default="", help="fragmento interno a reemplazar")
    p.add_argument("--reemplazar", default="", help="texto de reemplazo")
    p.add_argument("--ignorar-mayusculas", action="store_true",
                   help="el 'buscar' no distingue mayúsculas")
    p.add_argument("--solo-primera", action="store_true",
                   help="reemplaza solo la primera ocurrencia")
    p.add_argument("--no-subdirectorios", action="store_true",
                   help="solo el primer nivel (no recursivo)")
    p.add_argument("--omitir-ocultos", action="store_true")
    p.add_argument("--conflicto", choices=CONFLICTOS, default="numerar")
    p.add_argument("--simular", action="store_true",
                   help="vista previa: muestra antes -> después sin renombrar")
    p.add_argument("--detallado", action="store_true")
    args = p.parse_args(argv)

    try:
        origen = rutas_validadas(args.origen)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    opts = Opciones(prefijo=args.prefijo, sufijo=args.sufijo, buscar=args.buscar,
                    reemplazar=args.reemplazar,
                    sensible_mayusculas=not args.ignorar_mayusculas,
                    solo_primera=args.solo_primera,
                    recursivo=not args.no_subdirectorios,
                    omitir_ocultos=args.omitir_ocultos, conflicto=args.conflicto,
                    simular=args.simular, detallado=args.detallado)

    aviso = None if args.simular else (
        "AVISO: renombrado en bloque. Prueba antes con --simular (vista previa).")
    return correr_cli(ejecutar, {"origen": origen}, opts, si=args.si, antes=aviso)


if __name__ == "__main__":
    sys.exit(main())
