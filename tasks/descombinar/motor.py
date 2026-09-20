#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
tasks/descombinar/motor.py — Deshace una combinación hecha con Combinar: a partir
del índice guardado en el directorio combinado (`.kakoli_combinacion.json`),
reconstruye los directorios ORIGINALES (uno por origen: el principal + cada
fuente) restaurando la estructura y los NOMBRES de archivo originales (deshace el
sufijo de renombrado).

Los archivos que se descartaron al combinar (por 'mantener' o 'reemplazar') no
están en el combinado y NO se pueden reconstruir; se informa de ellos.

No borra el directorio combinado. Uso por consola:
    python -m tasks.descombinar.motor COMBINADO [-d DESTINO]
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core import recursos
from core.cli import correr_cli
from core.formato import duracion
from core.opciones import OpcionesBase
from core.resultado import Resultado
from core.control import Control
# El formato del índice lo define motor_combinar (como descomprimir usa
# leer_marca de comprimir): se importa su lector.
from tasks.formatos.indice_combinacion import INDICE_NOMBRE, cargar_indice

PAUSE_NAME = "PAUSA"


@dataclass
class Opciones(OpcionesBase):
    # detallado/politica + recorrido de FS se heredan de OpcionesBase.
    sobrescribir: bool = False        # si el destino ya tiene el archivo, rehacerlo


# ==========================================================================
# Utilidades
# ==========================================================================
def _copiar(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)


def _etiquetas(indice: dict) -> dict[str, str]:
    """id de origen -> nombre de carpeta de salida (basename original, único)."""
    out: dict[str, str] = {}
    vistos: dict[str, int] = {}
    for oid, info in indice.get("origenes", {}).items():
        base = Path(info.get("ruta", "")).name or oid
        if base in vistos:
            vistos[base] += 1
            base = f"{base}_{vistos[base]}"
        else:
            vistos[base] = 1
        out[oid] = base
    return out


def _destino_seguro(base: Path, *partes: str) -> Path | None:
    """Une base/partes evitando fugas (`..`, rutas absolutas, ':' en Windows)."""
    base_res = base.resolve()
    rel = Path(*[p.replace("\\", "/") for p in partes])
    if rel.is_absolute() or ".." in rel.parts:
        return None
    if os.name == "nt" and any(":" in p for p in rel.parts):
        return None
    destino = (base_res / rel).resolve()
    if os.path.commonpath([str(base_res), str(destino)]) != str(base_res):
        return None
    return destino


def rutas_validadas(combinado: Path, destino: Path | None) -> tuple[Path, Path]:
    """Comprueba que `combinado` tiene índice de combinación y decide el destino."""
    c = Path(combinado).expanduser().resolve()
    if not c.is_dir():
        raise ValueError(f"'{combinado}' no es una carpeta.")
    if not (c / INDICE_NOMBRE).exists():
        raise ValueError(
            f"Ese directorio no tiene índice de combinación ({INDICE_NOMBRE}); no "
            "parece un resultado de Combinar (o se combinó sin crear índice).")
    if cargar_indice(c) is None:
        raise ValueError("El índice de combinación está dañado o es de otra versión.")
    d = (Path(destino).expanduser().resolve() if destino
         else c.parent / f"{c.name}_descombinado")
    return c, d


# ==========================================================================
# Motor
# ==========================================================================
def ejecutar(entradas: dict, opts: Opciones, *, log: Callable[[str], None] = print,
             progreso=None, pausar=None, cancelar=None, confirmar=None) -> Resultado:
    """Contrato uniforme para la GUI (B). `entradas` = {"origen": <combinado>,
    "destino": <carpeta>}."""
    combinado, destino = entradas["origen"], entradas["destino"]
    log(f"Combinado: {combinado}")
    log(f"Destino  : {destino}")
    return procesar(combinado, destino, opts, log=log, progreso=progreso,
                    pausar=pausar, cancelar=cancelar, confirmar=confirmar)


def procesar(combinado: Path, destino: Path, opts: Opciones, *,
             log: Callable[[str], None] = print,
             progreso: Callable[[int, int, float, str], None] | None = None,
             pausar: Callable[[], bool] | None = None,
             cancelar: Callable[[], bool] | None = None,
             confirmar: Callable[[str, bool], bool] | None = None) -> Resultado:
    """Reconstruye los directorios de origen a partir del índice del combinado."""
    t0 = time.monotonic()
    pausar = pausar or (lambda: False)
    cancelar = cancelar or (lambda: False)
    combinado, destino = Path(combinado), Path(destino)

    indice = cargar_indice(combinado)
    if not indice:
        return Resultado("error", mensaje="No hay índice legible en el combinado.")
    recursos.preparar(destino, opts.politica, log=log)

    etiquetas = _etiquetas(indice)
    archivos: dict[str, dict] = indice.get("archivos", {})
    total = len(archivos)
    log(f"Reconstruyendo {total} archivos en {len(etiquetas)} directorio(s) de origen...")

    hechos = copiados = saltados = faltan = 0
    errores: list[str] = []
    ctrl = Control(pausar=pausar, cancelar=cancelar,
                   pausa_ruta=combinado.parent / PAUSE_NAME)

    try:
        for combined_rel, e in archivos.items():
            if ctrl.debe_parar():
                break

            etiqueta = etiquetas.get(e["origen"], e["origen"])
            src = combinado / Path(combined_rel)
            dest = _destino_seguro(destino, etiqueta, e["ruta_original"])
            if dest is None:
                errores.append(f"ruta insegura: {etiqueta}/{e['ruta_original']}")
            elif not src.exists():
                faltan += 1
                log(f"[!] Falta en el combinado: {combined_rel}")
            elif dest.exists() and not opts.sobrescribir:
                saltados += 1
            else:
                try:
                    _copiar(src, dest)
                    copiados += 1
                    if opts.detallado:
                        log(f"  {etiqueta}/{e['ruta_original']}")
                except OSError as ex:
                    errores.append(f"{src}: {ex}")
                    log(f"[!] No se pudo reconstruir {combined_rel}: {ex}")

            hechos += 1
            if progreso and (hechos % 25 == 0 or hechos == total):
                progreso(hechos, total, min(1.0, hechos / total if total else 0.0),
                         etiqueta)
    except KeyboardInterrupt:
        return Resultado("pausado", hechos, max(0, total - hechos), total, errores,
                         destino, "Proceso cortado.", time.monotonic() - t0)

    seg = time.monotonic() - t0
    descartados = indice.get("descartados", [])
    if descartados:
        log(f"[!] {len(descartados)} archivos se descartaron al combinar "
            "(mantenidos/reemplazados) y no se pueden reconstruir.")
    if ctrl.motivo:
        log(ctrl.motivo)
        return Resultado(ctrl.estado, hechos, max(0, total - hechos), total, errores,
                         destino, ctrl.motivo, seg)

    log(f"Descombinado: {copiados} archivos reconstruidos"
        + (f", {saltados} ya existían" if saltados else "")
        + (f", {faltan} ausentes" if faltan else "")
        + f", en {duracion(seg)}.")
    return Resultado("completado", hechos, 0, total, errores, destino, "", seg)


# ==========================================================================
# Consola
# ==========================================================================
def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Deshace una combinación: reconstruye los directorios de origen "
                    "a partir del índice del directorio combinado.")
    p.add_argument("combinado", type=Path, help="directorio generado por Combinar")
    p.add_argument("-d", "--destino", type=Path, default=None,
                   help="dónde reconstruir (por defecto, al lado del combinado)")
    p.add_argument("-y", "--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--sobrescribir", action="store_true",
                   help="rehacer los archivos que ya existan en el destino")
    p.add_argument("--detallado", action="store_true")
    args = p.parse_args(argv)

    try:
        combinado, destino = rutas_validadas(args.combinado, args.destino)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    opts = Opciones(sobrescribir=args.sobrescribir, detallado=args.detallado)
    return correr_cli(ejecutar, {"origen": combinado, "destino": destino}, opts,
                      si=args.si)


if __name__ == "__main__":
    sys.exit(main())
