#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
tasks/eliminar/motor.py — Borra una carpeta y todo su contenido de forma
recursiva, empezando por los niveles más bajos y subiendo hasta eliminar la
carpeta principal.

AVISO: el borrado es definitivo. Los archivos NO van a la papelera de reciclaje
y no hay forma de recuperarlos desde el programa.

Es pausable (se para entre carpetas) y relanzable: si se corta a medias, volver
a lanzarlo continúa borrando lo que quede.

Uso directo por consola:
    python -m tasks.eliminar.motor CARPETA [--simular] [-y]
"""

from __future__ import annotations

import os
import stat
import sys
import time
from core import recursos
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Todo lo que usa este motor es genérico: se importa del núcleo (ya no depende de
# motor_comprimir).
from core.cli import correr_cli
from core.formato import PASO_REGISTRO, duracion, humano
from core.opciones import OpcionesBase
from core.resultado import Resultado
from core.control import Control

PAUSE_NAME = "PAUSA"


@dataclass
class Opciones(OpcionesBase):
    # detallado/politica + recorrido de FS se heredan de OpcionesBase.
    simular: bool = False        # no borra nada, solo enumera
    estricto: bool = False       # abortar al primer error
    max_entradas: int = 0        # parar tras N elementos (0 = sin límite)
    contar: bool = True          # Fase 6: contar antes (barra exacta) o ir ligero


def ejecutar(entradas: dict, opts: Opciones, *, log: Callable[[str], None] = print,
             progreso=None, pausar=None, cancelar=None, confirmar=None) -> Resultado:
    """Contrato uniforme para la GUI (B). `entradas` = {"origen": <carpeta>};
    mapea a procesar() (el destino se ignora: eliminar opera in situ)."""
    carpeta = entradas["origen"]
    log(f"Carpeta: {carpeta}")
    if opts.simular:
        log("Modo simulación: no se borrará nada.")
    return procesar(carpeta, opts, log=log, progreso=progreso,
                    pausar=pausar, cancelar=cancelar, confirmar=confirmar)


# --------------------------------------------------------------------------
# Comprobaciones de seguridad
# --------------------------------------------------------------------------

def rutas_validadas(carpeta: Path) -> Path:
    """Devuelve la carpeta absoluta. Lanza ValueError si borrarla sería temerario."""
    p = Path(carpeta).expanduser()
    if not p.is_absolute():
        p = p.resolve()
    if p.is_symlink():
        raise ValueError("La ruta es un enlace simbólico; elige la carpeta real.")
    p = p.resolve()
    if not p.exists():
        raise ValueError(f"'{carpeta}' no existe.")
    if not p.is_dir():
        raise ValueError(f"'{carpeta}' no es una carpeta.")
    if p.parent == p:
        raise ValueError("No se puede borrar la raíz del sistema de archivos.")
    try:
        if p == Path.home().resolve():
            raise ValueError("No se puede borrar la carpeta personal del usuario.")
    except (OSError, RuntimeError):
        pass
    if len(p.parts) <= 2:
        raise ValueError(f"'{p}' está demasiado arriba en el sistema de archivos "
                         f"como para borrarla con esta herramienta.")
    try:
        if Path.cwd().resolve().is_relative_to(p):
            raise ValueError("Estás dentro de esa carpeta; sal de ella antes de borrarla.")
    except OSError:
        pass
    return p


def contar(carpeta: Path) -> tuple[int, int, int]:
    """(archivos, carpetas, bytes) que se van a eliminar."""
    archivos = bytes_tot = 0
    carpetas = 1
    for dirpath, dirnames, filenames in os.walk(carpeta, followlinks=False):
        carpetas += len(dirnames)
        for nombre in filenames:
            archivos += 1
            try:
                bytes_tot += os.lstat(os.path.join(dirpath, nombre)).st_size
            except OSError:
                pass
    return archivos, carpetas, bytes_tot


def _borrar_archivo(ruta: str) -> None:
    try:
        os.unlink(ruta)
    except PermissionError:
        os.chmod(ruta, stat.S_IWRITE | stat.S_IREAD)
        os.unlink(ruta)


# --------------------------------------------------------------------------
# Motor
# --------------------------------------------------------------------------

def procesar(carpeta: Path, opts: Opciones, *,
             log: Callable[[str], None] = print,
             progreso: Callable[[int, int, float, str], None] | None = None,
             pausar: Callable[[], bool] | None = None,
             cancelar: Callable[[], bool] | None = None,
             confirmar: Callable[[str, bool], bool] | None = None) -> Resultado:
    """
    Borra la carpeta entera de abajo arriba.
    Misma interfaz de callbacks que los otros motores.
    """
    t0 = time.monotonic()
    pausar = pausar or (lambda: False)
    cancelar = cancelar or (lambda: False)

    # Fase 6: contar antes da una barra de progreso exacta, pero en árboles
    # enormes duplica el recorrido; "sin contar" (opts.contar=False) va más
    # ligero. La simulación siempre cuenta (es justo lo que enumera).
    if opts.contar or opts.simular:
        log("Contando lo que hay dentro...")
        archivos, carpetas, bytes_tot = contar(carpeta)
        total = archivos + carpetas
        log(f"  {archivos} archivos y {carpetas} carpetas, {humano(bytes_tot)}")
    else:
        archivos = carpetas = bytes_tot = total = 0
        log("Borrado sin contar antes (más ligero); la barra de progreso será "
            "aproximada.")

    if opts.simular:
        log("[Simulación] No se borrará nada.")
    elif confirmar:
        pregunta = (f"Se borrarán DEFINITIVAMENTE {archivos} archivos y {carpetas} "
                    f"carpetas de '{carpeta}'. No van a la papelera. ¿Continuar?"
                    if opts.contar else
                    f"Se borrará DEFINITIVAMENTE todo el contenido de '{carpeta}'. "
                    f"No va a la papelera. ¿Continuar?")
        if not confirmar(pregunta, False):
            return Resultado("cancelado", total=total)

    if not opts.simular:
        # Fase 2: perfil COMÚN de la máquina + modo ligero (borrado secuencial).
        recursos.preparar(carpeta, opts.politica, log=log)

    hechas = 0
    arch_borr = carp_borr = 0        # borrados reales (para el modo sin contar)
    carpetas_vistas = 0
    errores: list[str] = []

    def avanzar(etiqueta: str) -> None:
        nonlocal hechas
        hechas += 1
        if progreso and (hechas % 25 == 0 or (total and hechas == total)):
            frac = (hechas / total) if total else 0.0
            progreso(hechas, total, min(1.0, frac), etiqueta)

    ctrl = Control(pausar=pausar, cancelar=cancelar,
                   pausa_ruta=carpeta.parent / PAUSE_NAME,
                   limite=opts.max_entradas, contador=lambda: hechas,
                   nombre_unidad="elementos")

    try:
        # topdown=False: cada carpeta se visita después de sus subcarpetas.
        for dirpath, dirnames, filenames in os.walk(carpeta, topdown=False,
                                                    followlinks=False):
            if ctrl.debe_parar():
                break

            rel = os.path.relpath(dirpath, carpeta.parent)
            carpetas_vistas += 1
            if opts.detallado:
                log(f"  {rel}  ({len(filenames)} archivos)")
            elif carpetas_vistas % PASO_REGISTRO == 0:
                marcador = f"{hechas}/{total}" if total else str(hechas)
                log(f"  {rel}  — {marcador} elementos")

            for nombre in filenames:
                ruta = os.path.join(dirpath, nombre)
                if opts.simular:
                    avanzar(rel)
                    continue
                try:
                    _borrar_archivo(ruta)
                except OSError as e:
                    errores.append(f"{ruta}: {e}")
                    log(f"[!] No se pudo borrar {nombre}: {e}")
                    if opts.estricto:
                        raise
                else:
                    arch_borr += 1
                avanzar(rel)

            # Enlaces a carpetas: se quitan sin entrar en ellos.
            for nombre in dirnames:
                ruta = os.path.join(dirpath, nombre)
                if os.path.islink(ruta) and not opts.simular:
                    try:
                        os.unlink(ruta)
                    except OSError as e:
                        errores.append(f"{ruta}: {e}")

            if opts.simular:
                avanzar(rel)
                continue
            try:
                os.rmdir(dirpath)
            except OSError as e:
                errores.append(f"{dirpath}: {e}")
                log(f"[!] No se pudo borrar la carpeta {rel}: {e}")
                if opts.estricto:
                    raise
            else:
                carp_borr += 1
            avanzar(rel)

    except KeyboardInterrupt:
        return Resultado("pausado", hechas, max(0, total - hechas), total, errores,
                         carpeta, "Proceso cortado.", time.monotonic() - t0)
    except OSError as e:
        return Resultado("error", hechas, max(0, total - hechas), total, errores,
                         carpeta, str(e), time.monotonic() - t0)

    seg = time.monotonic() - t0
    if ctrl.motivo:
        log(ctrl.motivo)
        log("Vuelve a lanzarlo para seguir borrando lo que queda.")
        return Resultado(ctrl.estado, hechas, max(0, total - hechas), total, errores,
                         carpeta, ctrl.motivo, seg)

    if opts.simular:
        log(f"[Simulación] Se habrían borrado {total} elementos ({humano(bytes_tot)}).")
        return Resultado("completado", hechas, 0, total, errores, carpeta,
                         "simulación", seg)

    if carpeta.exists():
        errores.append(f"{carpeta}: la carpeta principal no se pudo borrar")
        log(f"[!] La carpeta principal sigue existiendo: {carpeta}")
        return Resultado("error", hechas, 0, total, errores, carpeta,
                         "Quedan elementos sin borrar (permisos o archivos en uso).", seg)

    if progreso:
        progreso(hechas, hechas, 1.0, carpeta.name)
    if opts.contar:
        log(f"Eliminado: {archivos} archivos y {carpetas} carpetas, "
            f"{humano(bytes_tot)} liberados en {duracion(seg)}.")
    else:
        log(f"Eliminado: {arch_borr} archivos y {carp_borr} carpetas "
            f"en {duracion(seg)}.")
    if errores:
        log(f"[!] {len(errores)} elementos dieron error.")
    return Resultado("completado", hechas, 0, total, errores, carpeta, "", seg)


# --------------------------------------------------------------------------
# Consola
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Borra una carpeta entera de abajo arriba. El borrado es "
                    "definitivo: no pasa por la papelera.")
    p.add_argument("carpeta", type=Path)
    p.add_argument("-y", "--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--simular", action="store_true", help="enumerar sin borrar")
    p.add_argument("--estricto", action="store_true", help="abortar al primer error")
    p.add_argument("--max-entradas", type=int, default=0, metavar="N")
    p.add_argument("--sin-contar", action="store_true",
                   help="no contar antes de borrar (más ligero; barra aproximada)")
    p.add_argument("--resumido", action="store_true",
                   help="una línea de registro cada 50 carpetas")
    args = p.parse_args(argv)

    try:
        carpeta = rutas_validadas(args.carpeta)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    opts = Opciones(simular=args.simular, estricto=args.estricto,
                    max_entradas=args.max_entradas, detallado=not args.resumido,
                    contar=not args.sin_contar)
    aviso = (None if args.simular else
             "AVISO: el borrado es definitivo y no usa la papelera de reciclaje.")
    return correr_cli(ejecutar, {"origen": carpeta}, opts, si=args.si, antes=aviso)


if __name__ == "__main__":
    sys.exit(main())
