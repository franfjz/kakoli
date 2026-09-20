#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
tasks/desaplanar/motor.py — Reconstruye un árbol de directorios a partir de una carpeta
APLANADA, usando ÚNICAMENTE los nombres de archivo (no hay índice).

Cada nombre se parte por el separador (`-` por defecto): el último segmento es el
nombre del archivo y los anteriores son las carpetas. Ejemplo:
    nivel1-nivel2-archivo.txt  ->  nivel1/nivel2/archivo.txt
Un nombre sin separador queda en la raíz del destino.

Es una reconstrucción POR CONVENIÓN DE NOMBRE, no un undo exacto: si un nombre real
contenía el separador (`mi-informe.txt`), se interpretará como carpeta (`mi/
informe.txt`). Esta ambigüedad es inherente al método (elegido así a propósito).

Reutiliza `aplanar_nombre` NO; solo comparte el separador por defecto con
motor_aplanar (que define la transformación directa).

Uso por consola:
    python -m tasks.desaplanar.motor CARPETA_APLANADA DESTINO [--sep -] ...
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator

from core import paralelo
from core import recursos
from core.cli import correr_cli
from core.formato import duracion
from core.opciones import OpcionesBase
from core.resultado import Resultado
from core.control import Control
from core.reanudable import RegistroReanudable
from core.cache_arbol import CacheArbol
from tasks.formatos.nombres_aplanado import (ARBOL_APLANADO, ARBOL_DESAPLANADO,
                               REGISTRO_APLANADO, REGISTRO_DESAPLANADO,
                               desaplanar_nombre, separador_ok)

CONFLICTOS = ("renombrar", "mantener", "reemplazar")
PAUSE_NAME = "PAUSA"
REGISTRO_NOMBRE = REGISTRO_DESAPLANADO         # registro de progreso reanudable
ARBOL_NOMBRE = ARBOL_DESAPLANADO               # caché del árbol explorado
TAREA = "desaplanar"
# Ficheros de control que NUNCA se reconstruyen (R6): los registros y las cachés de
# árbol (propios y de aplanar, que pueden haber quedado en la carpeta aplanada si
# aquel proceso se pausó).
_EXCLUIR = {REGISTRO_DESAPLANADO, REGISTRO_APLANADO, ARBOL_DESAPLANADO, ARBOL_APLANADO}


@dataclass
class Opciones(OpcionesBase):
    separador: str = "-"                   # debe coincidir con el usado al aplanar
    conflicto: str = "renombrar"           # renombrar | mantener | reemplazar
    # seguir_enlaces / omitir_ocultos se heredan de OpcionesBase.
    reiniciar: bool = False                # ignorar el progreso guardado y empezar de cero


def _firma(opts: Opciones) -> dict:
    """Opciones que afectan al RESULTADO: si cambian, el progreso guardado no vale."""
    return {"separador": opts.separador, "conflicto": opts.conflicto,
            "omitir_ocultos": opts.omitir_ocultos}


def _firma_arbol(opts: Opciones) -> dict:
    """Opciones que cambian LO QUE PRODUCE el recorrido de la carpeta aplanada: si
    cambian, la caché del árbol no vale (el separador o el conflicto afectan al
    destino, no a qué archivos de la carpeta aplanada se enumeran)."""
    return {"omitir_ocultos": opts.omitir_ocultos}


def info_reanudable(entradas: dict, opts: Opciones) -> "dict | None":
    """¿Hay un desaplanado A MEDIAS que reanudar? (para el modal de la GUI). El
    registro se borra al completar (R4), así que solo existe si quedó pendiente."""
    try:
        origen, destino = Path(entradas["origen"]), Path(entradas["destino"])
    except (KeyError, TypeError):
        return None
    return RegistroReanudable.inspeccionar(destino / REGISTRO_NOMBRE, TAREA,
                                           origen, _firma(opts))


# `desaplanar_nombre` (y su `_sanea_seg`) viven en nombres_aplanado.py, compartidos
# con Aplanar; se importan arriba y se reexponen como atributos del módulo.


def _walk_archivos(base: Path, omitir_ocultos: bool) -> Iterator[Path]:
    """Todos los archivos bajo `base` (robusto: la carpeta aplanada debería ser
    plana, pero se recorre lo que haya; A6)."""
    for dirpath, dirnames, filenames in os.walk(base):
        if omitir_ocultos:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for nombre in filenames:
            if nombre in _EXCLUIR:                  # no reconstruir los registros (R6)
                continue
            if omitir_ocultos and nombre.startswith("."):
                continue
            yield Path(dirpath) / nombre


def _copiar(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)


def _destino_seguro(destino: Path, rel: str) -> Path:
    """Resuelve `destino/rel` garantizando que queda DENTRO de `destino`.
    Comprobación puramente LÉXICA (os.path.normpath, sin tocar el disco): así es
    segura entre hilos (`.resolve()` consulta el FS y compite con la creación de
    carpetas en paralelo, dando falsos positivos). `rel` ya viene saneado
    (sin `..`) por `desaplanar_nombre`; esto es defensa en profundidad."""
    raiz = os.path.normpath(destino)
    ruta = os.path.normpath(os.path.join(raiz, rel))
    if ruta != raiz and not ruta.startswith(raiz + os.sep):
        raise ValueError(f"ruta insegura fuera del destino: {rel}")
    return Path(ruta)


def _sin_colision(destino: Path, rel: str) -> str:
    """Ruta relativa con sufijo numérico si ya existe (para 'renombrar')."""
    p = PurePosixPath(rel)
    cand = rel
    n = 2
    while (destino / cand).exists():
        cand = (p.parent / f"{p.stem}_{n}{p.suffix}").as_posix()
        n += 1
    return cand


def rutas_validadas(origen: Path, destino: Path | None = None) -> tuple[Path, Path]:
    """Normaliza y valida. Si `destino` es None se usa `<origen>_desaplanado` al
    lado. Lanza ValueError si algo falla."""
    o = Path(origen).expanduser().resolve()
    if not o.exists():
        raise ValueError(f"La carpeta aplanada no existe: {origen}")
    if not o.is_dir():
        raise ValueError(f"'{origen}' no es una carpeta.")
    d = (Path(destino).expanduser().resolve() if destino
         else o.parent / f"{o.name}_desaplanado")
    if d.exists() and not d.is_dir():
        raise ValueError(f"'{destino}' no es una carpeta.")
    if d == o or o in d.parents:
        raise ValueError("El destino no puede estar dentro del origen.")
    d.mkdir(parents=True, exist_ok=True)
    return o, d


# ==========================================================================
# Motor
# ==========================================================================
def ejecutar(entradas: dict, opts: Opciones, *, log: Callable[[str], None] = print,
             progreso=None, pausar=None, cancelar=None, confirmar=None) -> Resultado:
    """Contrato uniforme para la GUI (B). `entradas` = {"origen", "destino"}."""
    origen, destino = entradas["origen"], entradas["destino"]
    log(f"Aplanada: {origen}")
    log(f"Destino : {destino}")
    return procesar(origen, destino, opts, log=log, progreso=progreso,
                    pausar=pausar, cancelar=cancelar, confirmar=confirmar)


def procesar(origen: Path, destino: Path, opts: Opciones, *,
             log: Callable[[str], None] = print,
             progreso: Callable[[int, int, float, str], None] | None = None,
             pausar: Callable[[], bool] | None = None,
             cancelar: Callable[[], bool] | None = None,
             confirmar: Callable[[str, bool], bool] | None = None) -> Resultado:
    """Reconstruye el árbol en `destino` partiendo los nombres por el separador.
    Paraleliza por archivo si el perfil lo aconseja, serializando por RUTA
    reconstruida (D7)."""
    t0 = time.monotonic()
    pausar = pausar or (lambda: False)
    cancelar = cancelar or (lambda: False)
    origen, destino = Path(origen), Path(destino)
    err = separador_ok(opts.separador)        # el separador siempre se usa aquí
    if err:
        log(f"[!] {err}")
        return Resultado("error", 0, 0, 0, [err], destino, err, 0.0)
    perf = recursos.preparar(origen, opts.politica, log=log)

    # Registro de progreso reanudable (roadmap_reanudar.md): salta lo ya hecho.
    ruta_reg = destino / REGISTRO_NOMBRE
    cache = CacheArbol(destino / ARBOL_NOMBRE, _firma_arbol(opts))
    firma = _firma(opts)
    if opts.reiniciar:
        viejo = RegistroReanudable.cargar(ruta_reg, TAREA, origen, firma, log=log)
        for ent in viejo.hechos.values():
            salida = ent.get("salida")
            if not salida:
                continue
            try:
                (destino / salida).unlink()
            except OSError:
                pass
        registro = RegistroReanudable.cargar(ruta_reg, TAREA, origen, firma,
                                             reiniciar=True, log=log)
    else:
        registro = RegistroReanudable.cargar(ruta_reg, TAREA, origen, firma, log=log)
    procesados = registro.procesados()

    # El recorrido de la carpeta aplanada se cachea (rutas relativas a `origen`): al
    # reanudar no se vuelve a recorrer el disco. El progreso filtra lo ya hecho.
    def _explorar():
        log("Leyendo la carpeta aplanada...")
        return [src.relative_to(origen).as_posix()
                for src in _walk_archivos(origen, opts.omitir_ocultos)]

    todos = cache.obtener(_explorar, reiniciar=opts.reiniciar, log=log)
    items = [origen / rel for rel in todos if rel not in procesados]
    total = len(items)
    if procesados:
        log(f"  Reanudando: {len(procesados)} ya hechos; quedan {total}.")
    n_hilos = recursos.calcular_hilos(perf, opts.politica, unidades=total)
    log(f"  {total} archivos; separador '{opts.separador}'; "
        + (f"en paralelo con {n_hilos} hilos." if n_hilos > 1 else "secuencial (1 hilo)."))

    cont = {"hechos": 0, "reconstruidos": 0, "mantenidos": 0, "reemplazados": 0,
            "raiz": 0}
    errores: list[str] = []
    ilock = threading.Lock()
    locks_rel: dict[str, threading.Lock] = {}
    guard = threading.Lock()
    pausa_ruta = destino.parent / PAUSE_NAME

    def _lock_rel(rel: str) -> threading.Lock:
        with guard:                          # un cerrojo por ruta reconstruida
            lk = locks_rel.get(rel)
            if lk is None:
                lk = locks_rel[rel] = threading.Lock()
            return lk

    def _desaplanar_uno(src: Path) -> None:
        unidad = src.relative_to(origen).as_posix()
        rel = desaplanar_nombre(src.name, opts.separador)
        es_raiz = "/" not in rel
        escrita = None       # ruta que ESTE proceso escribió (para el registro/undo)
        descartada = None    # motivo si NO se escribió (mantener)
        try:
            with _lock_rel(rel):
                dest = _destino_seguro(destino, rel)
                if dest.exists() and opts.conflicto == "mantener":
                    descartada = "mantenido"
                    with ilock:
                        cont["mantenidos"] += 1
                elif dest.exists() and opts.conflicto == "reemplazar":
                    _copiar(src, dest)
                    escrita = rel
                    with ilock:
                        cont["reemplazados"] += 1
                else:
                    if dest.exists():        # renombrar (por defecto)
                        rel = _sin_colision(destino, rel)
                        dest = _destino_seguro(destino, rel)
                    _copiar(src, dest)
                    escrita = rel
                    with ilock:
                        cont["reconstruidos"] += 1
        except (OSError, ValueError) as e:
            with ilock:
                errores.append(f"{src}: {e}")
            log(f"[!] No se pudo desaplanar {src.name}: {e}")
        else:
            if escrita is not None:
                registro.anota(unidad, escrita)
            elif descartada is not None:
                registro.descarta(unidad, descartada)
        if opts.detallado:
            log(f"  {src.name} -> {rel}")
        with ilock:
            if es_raiz:
                cont["raiz"] += 1
            cont["hechos"] += 1
            h = cont["hechos"]
            if progreso and (h % 25 == 0 or h == total):
                progreso(h, total, min(1.0, (h / total) if total else 0.0), rel)

    ctrl = Control(pausar=pausar, cancelar=cancelar, pausa_ruta=pausa_ruta)
    try:
        if n_hilos <= 1:
            for src in items:
                if ctrl.debe_parar():
                    break
                _desaplanar_uno(src)
        else:
            plan = paralelo.PlanLista(items)
            ejec = paralelo.Ejecutor(n_hilos)
            limite = (recursos.regulador_carga(perf.cpu, n_hilos)
                      if opts.politica.throttling else None)
            ctrl.desde_ejecutor(ejec.ejecutar(plan, _desaplanar_uno, ctrl.debe_pausar,
                                              limite_activos=limite, cancelar=cancelar))
    except KeyboardInterrupt:
        ctrl.motivo = "Proceso cortado."

    seg = time.monotonic() - t0
    hechos = cont["hechos"]
    if ctrl.motivo:
        registro.guardar()                   # persiste el progreso para reanudar
        log(ctrl.motivo)
        return Resultado(ctrl.estado, hechos, max(0, total - hechos), total, errores,
                         destino, ctrl.motivo, seg)

    log(f"Desaplanado: {cont['reconstruidos']} reconstruidos "
        f"({cont['raiz']} en la raíz), {cont['mantenidos']} mantenidos, "
        f"{cont['reemplazados']} reemplazados, en {duracion(seg)}.")
    if errores:
        registro.guardar()                   # conserva el progreso: al reintentar salta los OK
        log(f"[!] {len(errores)} archivos dieron error.")
    else:
        registro.completar(borrar=True)      # tarea completa: se borra el registro (R4)
        cache.borrar()                       # ...y la caché del árbol (ya no hace falta)
    return Resultado("completado", hechos, 0, total, errores, destino, "", seg)


# ==========================================================================
# Consola
# ==========================================================================
def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Reconstruye un árbol de directorios a partir de una carpeta "
                    "aplanada, usando los nombres de archivo (separador '-').")
    p.add_argument("origen", type=Path, help="carpeta aplanada")
    p.add_argument("destino", type=Path, help="carpeta de salida (árbol reconstruido)")
    p.add_argument("-y", "--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--sep", default="-", help="separador de niveles (por defecto '-')")
    p.add_argument("--conflicto", choices=CONFLICTOS, default="renombrar")
    p.add_argument("--omitir-ocultos", action="store_true")
    p.add_argument("--reiniciar", action="store_true",
                   help="ignora el progreso guardado y empieza de cero")
    p.add_argument("--detallado", action="store_true")
    args = p.parse_args(argv)

    try:
        origen, destino = rutas_validadas(args.origen, args.destino)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    opts = Opciones(separador=args.sep, conflicto=args.conflicto,
                    omitir_ocultos=args.omitir_ocultos, reiniciar=args.reiniciar,
                    detallado=args.detallado)
    aviso = ("NOTA: el árbol se deduce de los nombres (separador "
             f"'{args.sep}'); los nombres con ese carácter pueden crear carpetas "
             "no deseadas.")
    return correr_cli(ejecutar, {"origen": origen, "destino": destino}, opts,
                      si=args.si, antes=aviso)


if __name__ == "__main__":
    sys.exit(main())
