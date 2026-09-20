#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
tasks/aplanar/motor.py — Aplana un árbol de directorios: copia TODOS los archivos a una
sola carpeta de destino (un único nivel, sin subcarpetas).

Dos modos de nombre (`modo_nombre`):
  - ruta (por defecto): la ruta relativa se codifica en el nombre uniendo los
    niveles con el separador (`-`). `nivel1/nivel2/archivo.txt` -> `nivel1-nivel2-
    archivo.txt`. Es el único modo que luego permite DESAPLANAR (reconstruir el
    árbol a partir de los nombres).
  - final: solo el nombre del archivo (`archivo.txt`). Cómodo pero propenso a
    colisiones; no es desaplanable.

Aplanar SIEMPRE copia (nunca mueve): el origen se conserva intacto (A1).

Conflictos (dos archivos aterrizan con el mismo nombre destino) — `conflicto`:
  - renombrar (por defecto): se añade el nombre de la carpeta padre al nombre
    (A4) y, si aún colisiona, un sufijo numérico de respaldo.
  - mantener: se queda el primero; el segundo se omite.
  - reemplazar: gana uno según `criterio_reemplazo` (mayor/menor/reciente/
    antiguo); el perdedor se descarta (IRREVERSIBLE, A8).

Uso por consola:
    python -m tasks.aplanar.motor ORIGEN DESTINO [--modo ruta|final] [--sep -] ...
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
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
from tasks.formatos.nombres_aplanado import (ARBOL_APLANADO, REGISTRO_APLANADO,
                               aplanar_nombre, separador_ok)

MODOS_NOMBRE = ("ruta", "final")
CONFLICTOS = ("renombrar", "mantener", "reemplazar")
CRITERIOS = ("mayor", "menor", "mas_reciente", "mas_antiguo")
PAUSE_NAME = "PAUSA"
REGISTRO_NOMBRE = REGISTRO_APLANADO            # registro de progreso reanudable
ARBOL_NOMBRE = ARBOL_APLANADO                  # caché del árbol explorado
TAREA = "aplanar"


@dataclass
class Opciones(OpcionesBase):
    # detallado/politica + recorrido de FS se heredan de OpcionesBase.
    modo_nombre: str = "ruta"             # ruta | final (A3, por defecto ruta)
    separador: str = "-"                  # A2
    conflicto: str = "renombrar"          # renombrar | mantener | reemplazar
    criterio_reemplazo: str = "mas_reciente"   # mayor | menor | mas_reciente | mas_antiguo
    # seguir_enlaces / omitir_ocultos se heredan de OpcionesBase.
    reiniciar: bool = False               # ignorar el progreso guardado y empezar de cero


def _firma(opts: Opciones) -> dict:
    """Opciones que afectan al RESULTADO: si cambian, el progreso guardado no vale."""
    return {"modo_nombre": opts.modo_nombre, "separador": opts.separador,
            "conflicto": opts.conflicto, "criterio_reemplazo": opts.criterio_reemplazo,
            "omitir_ocultos": opts.omitir_ocultos, "seguir_enlaces": opts.seguir_enlaces}


def _firma_arbol(opts: Opciones) -> dict:
    """Opciones que cambian LO QUE PRODUCE el recorrido del origen: si cambian, la
    caché del árbol no vale (el modo de nombre o el conflicto afectan al destino,
    no a qué archivos de origen se enumeran)."""
    return {"seguir_enlaces": opts.seguir_enlaces, "omitir_ocultos": opts.omitir_ocultos}


def info_reanudable(entradas: dict, opts: Opciones) -> "dict | None":
    """¿Hay un aplanado A MEDIAS que reanudar? (para el modal de la GUI). El registro
    se borra al completar (R4), así que solo existe si quedó pendiente."""
    try:
        origen, destino = Path(entradas["origen"]), Path(entradas["destino"])
    except (KeyError, TypeError):
        return None
    return RegistroReanudable.inspeccionar(destino / REGISTRO_NOMBRE, TAREA,
                                           origen, _firma(opts))


# `aplanar_nombre` y `separador_ok` viven en nombres_aplanado.py (compartidos con
# Desaplanar); se importan arriba y se reexponen como atributos del módulo.


# ==========================================================================
# Utilidades
# ==========================================================================
def _walk_rel(base: Path, opts: Opciones) -> Iterator[str]:
    """Rutas relativas (posix) de los ARCHIVOS bajo `base` (salta ocultos si
    `omitir_ocultos`)."""
    base = Path(base)
    for dirpath, dirnames, filenames in os.walk(base, followlinks=opts.seguir_enlaces):
        if opts.omitir_ocultos:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(base)
        for nombre in filenames:
            if opts.omitir_ocultos and nombre.startswith("."):
                continue
            yield (rel_dir / nombre).as_posix()


def _copiar(src: Path, dest: Path) -> None:
    """Copia preservando metadatos (mtime) con temporal + replace atómico."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)


def _nombre_destino(rel: str, opts: Opciones) -> str:
    """Nombre plano de destino según el modo (sin resolver colisiones)."""
    if opts.modo_nombre == "final":
        return rel.split("/")[-1]
    return aplanar_nombre(rel, opts.separador)


def _renombrar(nombre: str, rel: str, destino: Path) -> str:
    """Renombra en colisión: añade la carpeta padre al nombre (A4) y, si aún
    colisiona, un sufijo numérico de respaldo."""
    p = Path(nombre)
    partes = rel.split("/")
    padre = partes[-2] if len(partes) >= 2 else ""     # carpeta padre en el árbol
    base = f"{p.stem}_{padre}" if padre else p.stem
    cand = f"{base}{p.suffix}"
    n = 2
    while (destino / cand).exists():
        cand = f"{base}_{n}{p.suffix}"
        n += 1
    return cand


def _gana_entrante(src: Path, dest: Path, criterio: str) -> bool:
    """¿Gana el archivo entrante frente al que ya está en el destino? (empate -> no)."""
    ss, ds = src.stat(), dest.stat()
    if criterio == "mayor":
        return ss.st_size > ds.st_size
    if criterio == "menor":
        return ss.st_size < ds.st_size
    if criterio == "mas_antiguo":
        return ss.st_mtime < ds.st_mtime
    return ss.st_mtime > ds.st_mtime          # mas_reciente (por defecto)


def rutas_validadas(origen: Path, destino: Path | None = None) -> tuple[Path, Path]:
    """Normaliza origen/destino y comprueba que se puede aplanar. Si `destino` es
    None se usa `<origen>_aplanado` al lado. Lanza ValueError."""
    o = Path(origen).expanduser().resolve()
    if not o.exists():
        raise ValueError(f"El directorio a aplanar no existe: {origen}")
    if not o.is_dir():
        raise ValueError(f"'{origen}' no es una carpeta.")
    d = (Path(destino).expanduser().resolve() if destino
         else o.parent / f"{o.name}_aplanado")
    if d.exists() and not d.is_dir():
        raise ValueError(f"'{destino}' no es una carpeta.")
    if d == o or o in d.parents:
        raise ValueError("El destino no puede estar dentro del origen (recursión).")
    if d in o.parents:
        raise ValueError("El origen no puede estar dentro del destino.")
    d.mkdir(parents=True, exist_ok=True)
    return o, d


# ==========================================================================
# Motor
# ==========================================================================
def ejecutar(entradas: dict, opts: Opciones, *, log: Callable[[str], None] = print,
             progreso=None, pausar=None, cancelar=None, confirmar=None) -> Resultado:
    """Contrato uniforme para la GUI (B). `entradas` = {"origen", "destino"}."""
    origen, destino = entradas["origen"], entradas["destino"]
    log(f"Origen : {origen}")
    log(f"Destino: {destino}")
    return procesar(origen, destino, opts, log=log, progreso=progreso,
                    pausar=pausar, cancelar=cancelar, confirmar=confirmar)


def procesar(origen: Path, destino: Path, opts: Opciones, *,
             log: Callable[[str], None] = print,
             progreso: Callable[[int, int, float, str], None] | None = None,
             pausar: Callable[[], bool] | None = None,
             cancelar: Callable[[], bool] | None = None,
             confirmar: Callable[[str, bool], bool] | None = None) -> Resultado:
    """Copia todos los archivos de `origen` a `destino` en un solo nivel.
    Paraleliza por archivo si el perfil lo aconseja (SSD), serializando la
    resolución de conflicto + copia por NOMBRE de destino (D7)."""
    t0 = time.monotonic()
    pausar = pausar or (lambda: False)
    cancelar = cancelar or (lambda: False)
    origen, destino = Path(origen), Path(destino)
    if opts.modo_nombre == "ruta":            # el separador solo se usa en modo ruta
        err = separador_ok(opts.separador)
        if err:
            log(f"[!] {err}")
            return Resultado("error", 0, 0, 0, [err], destino, err, 0.0)
    perf = recursos.preparar(origen, opts.politica, log=log)

    # Registro de progreso reanudable (roadmap_reanudar.md): salta lo ya hecho.
    ruta_reg = destino / REGISTRO_NOMBRE
    cache = CacheArbol(destino / ARBOL_NOMBRE, _firma_arbol(opts))
    firma = _firma(opts)
    if opts.reiniciar:
        # "Empezar de cero": deshace lo que ESTE aplanado escribió (según el registro)
        # y borra el registro, para que un re-run no duplique.
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

    # El recorrido del origen se cachea: al reanudar no se vuelve a recorrer el disco
    # (la caché común lo valida por firma y `--reiniciar` la descarta). El progreso
    # (`procesados`) sigue filtrando lo ya hecho.
    def _explorar():
        log("Explorando el árbol a aplanar...")
        return list(_walk_rel(origen, opts))

    todos = cache.obtener(_explorar, reiniciar=opts.reiniciar, log=log)
    items = [rel for rel in todos if rel not in procesados]
    total = len(items)
    if procesados:
        log(f"  Reanudando: {len(procesados)} ya hechos; quedan {total}.")
    n_hilos = recursos.calcular_hilos(perf, opts.politica, unidades=total)
    log(f"  {total} archivos. Modo: "
        + ("ruta en el nombre" if opts.modo_nombre == "ruta" else "solo el nombre final")
        + f", separador '{opts.separador}'; "
        + (f"en paralelo con {n_hilos} hilos." if n_hilos > 1 else "secuencial (1 hilo)."))

    # Estado compartido entre hilos (serializado con cerrojos, D7).
    cont = {"hechos": 0, "copiados": 0, "renombrados": 0, "mantenidos": 0,
            "reemplazados": 0}
    errores: list[str] = []
    ilock = threading.Lock()                 # contadores + errores + progreso
    locks_nombre: dict[str, threading.Lock] = {}
    guard = threading.Lock()
    pausa_ruta = destino.parent / PAUSE_NAME

    def _lock_nombre(nombre: str) -> threading.Lock:
        with guard:                          # un cerrojo por NOMBRE de destino
            lk = locks_nombre.get(nombre)
            if lk is None:
                lk = locks_nombre[nombre] = threading.Lock()
            return lk

    def _aplanar_uno(rel: str) -> None:
        src = origen / rel
        nombre = _nombre_destino(rel, opts)
        escrita = None       # nombre que ESTE proceso escribió (para el registro/undo)
        descartada = None    # motivo si NO se escribió (mantener / reemplazar-perdedor)
        try:
            with _lock_nombre(nombre):       # solo se serializan items del MISMO nombre
                dest = destino / nombre
                if not dest.exists():
                    _copiar(src, dest)
                    escrita = nombre
                    with ilock:
                        cont["copiados"] += 1
                elif opts.conflicto == "mantener":
                    descartada = "mantenido"
                    with ilock:
                        cont["mantenidos"] += 1
                elif opts.conflicto == "reemplazar":
                    if _gana_entrante(src, dest, opts.criterio_reemplazo):
                        _copiar(src, dest)
                        escrita = nombre
                    else:
                        descartada = "reemplazado"
                    with ilock:
                        cont["reemplazados"] += 1
                else:                          # renombrar (por defecto)
                    nrel = _renombrar(nombre, rel, destino)
                    _copiar(src, destino / nrel)
                    escrita = nrel
                    with ilock:
                        cont["renombrados"] += 1
        except OSError as e:
            with ilock:
                errores.append(f"{src}: {e}")
            log(f"[!] No se pudo aplanar {rel}: {e}")
        else:
            # Solo se registra lo que terminó bien (los errores se reintentan al reanudar).
            if escrita is not None:
                registro.anota(rel, escrita)
            elif descartada is not None:
                registro.descarta(rel, descartada)
        if opts.detallado:
            log(f"  {rel} -> {nombre}")
        with ilock:
            cont["hechos"] += 1
            h = cont["hechos"]
            if progreso and (h % 25 == 0 or h == total):
                progreso(h, total, min(1.0, (h / total) if total else 0.0), rel)

    ctrl = Control(pausar=pausar, cancelar=cancelar, pausa_ruta=pausa_ruta)
    try:
        if n_hilos <= 1:
            for rel in items:
                if ctrl.debe_parar():
                    break
                _aplanar_uno(rel)
        else:
            plan = paralelo.PlanLista(items)
            ejec = paralelo.Ejecutor(n_hilos)
            limite = (recursos.regulador_carga(perf.cpu, n_hilos)
                      if opts.politica.throttling else None)
            ctrl.desde_ejecutor(ejec.ejecutar(plan, _aplanar_uno, ctrl.debe_pausar,
                                              limite_activos=limite, cancelar=cancelar))
    except KeyboardInterrupt:
        ctrl.motivo = "Proceso cortado."

    seg = time.monotonic() - t0
    hechos = cont["hechos"]
    if ctrl.motivo:
        registro.guardar()                   # persiste el progreso para reanudar
        log(ctrl.motivo)
        log("Vuelve a lanzarlo para seguir aplanando lo que queda.")
        return Resultado(ctrl.estado, hechos, max(0, total - hechos), total, errores,
                         destino, ctrl.motivo, seg)

    log(f"Aplanado: {cont['copiados']} copiados, {cont['renombrados']} renombrados, "
        f"{cont['mantenidos']} mantenidos, {cont['reemplazados']} por reemplazo, "
        f"en {duracion(seg)}.")
    if opts.modo_nombre == "final":
        log("[!] Modo 'solo nombre final': este resultado NO se podrá desaplanar.")
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
        description="Aplana un árbol de directorios: copia todos los archivos a una "
                    "sola carpeta de destino.")
    p.add_argument("origen", type=Path, help="directorio a aplanar")
    p.add_argument("destino", type=Path, help="carpeta de salida (un solo nivel)")
    p.add_argument("-y", "--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--modo", choices=MODOS_NOMBRE, default="ruta",
                   help="ruta: codifica la ruta en el nombre; final: solo el nombre")
    p.add_argument("--sep", default="-", help="separador de niveles (por defecto '-')")
    p.add_argument("--conflicto", choices=CONFLICTOS, default="renombrar")
    p.add_argument("--criterio", choices=CRITERIOS, default="mas_reciente",
                   help="para --conflicto reemplazar")
    p.add_argument("--omitir-ocultos", action="store_true")
    p.add_argument("--seguir-enlaces", action="store_true")
    p.add_argument("--reiniciar", action="store_true",
                   help="ignora el progreso guardado y empieza de cero")
    p.add_argument("--detallado", action="store_true")
    args = p.parse_args(argv)

    try:
        origen, destino = rutas_validadas(args.origen, args.destino)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    opts = Opciones(modo_nombre=args.modo, separador=args.sep,
                    conflicto=args.conflicto, criterio_reemplazo=args.criterio,
                    omitir_ocultos=args.omitir_ocultos,
                    seguir_enlaces=args.seguir_enlaces, reiniciar=args.reiniciar,
                    detallado=args.detallado)

    avisos = []
    if args.conflicto == "reemplazar":
        avisos.append("AVISO: 'reemplazar' descarta archivos DE FORMA IRREVERSIBLE.")
    if args.modo == "final":
        avisos.append("AVISO: modo 'final', el resultado NO se podrá desaplanar.")
    return correr_cli(ejecutar, {"origen": origen, "destino": destino}, opts,
                      si=args.si, antes=("\n".join(avisos) or None))


if __name__ == "__main__":
    sys.exit(main())
