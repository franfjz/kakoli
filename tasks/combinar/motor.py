#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
tasks/combinar/motor.py — Funde (merge) varios árboles de directorios DENTRO de un
directorio principal, manteniendo la estructura común: si coinciden nombre y
nivel de carpeta, se unen los contenidos.

La fusión es IN SITU en el principal (D2: el principal cambia). Cada archivo del
resultado se anota en un ÍNDICE JSON guardado en el propio principal
(`.kakoli_combinacion.json`, D1), que permite deshacer la combinación con
motor_descombinar. El índice es opcional (D9: `--sin-indice` para procesos
enormes que no se van a deshacer; entonces NO será descombinable).

Conflictos (mismo nombre y misma ruta) — opción `conflicto`:
  - renombrar (por defecto): se conservan ambos; el entrante se copia con un
    código de su carpeta de origen añadido al nombre (D3).
  - mantener: se conserva el del principal y se omite el entrante.
  - reemplazar: gana uno según `criterio_reemplazo` (mayor/menor/reciente/
    antiguo); el perdedor se descarta (IRREVERSIBLE, D5).

Uso por consola:
    python -m tasks.combinar.motor PRINCIPAL FUENTE [FUENTE...] [--conflicto ...]
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
from tasks.formatos.indice_combinacion import (ARBOL_NOMBRE, INDICE_FORMATO, INDICE_NOMBRE,
                                 cargar_indice, guardar_indice)
from core.cli import correr_cli
from core.formato import PASO_REGISTRO, ahora, duracion
from core.opciones import OpcionesBase
from core.resultado import Resultado
from core.control import Control
from core.cache_arbol import CacheArbol

PAUSE_NAME = "PAUSA"

CONFLICTOS = ("renombrar", "mantener", "reemplazar")
CRITERIOS = ("mayor", "menor", "mas_reciente", "mas_antiguo")
MODOS_CODIGO = ("basename", "id", "personalizado")


@dataclass
class Opciones(OpcionesBase):
    # detallado/politica + recorrido de FS se heredan de OpcionesBase.
    conflicto: str = "renombrar"          # renombrar | mantener | reemplazar
    criterio_reemplazo: str = "mas_reciente"   # mayor | menor | mas_reciente | mas_antiguo
    modo_codigo: str = "basename"         # basename | id | personalizado (D3)
    codigo_personalizado: str = ""
    crear_indice: bool = True             # D9
    # seguir_enlaces / omitir_ocultos se heredan de OpcionesBase.


# ==========================================================================
# Índice de origen (D1) — el FORMATO y la E/S viven en indice_combinacion.py
# (`INDICE_NOMBRE`/`INDICE_FORMATO`/`cargar_indice`/`guardar_indice`), compartidos
# con motor_descombinar. Aquí solo la lógica específica de combinar.
# ==========================================================================
def _indice_nuevo(principal: Path) -> dict:
    return {"formato": INDICE_FORMATO, "creado": ahora(),
            "principal": str(principal),
            "origenes": {"principal": {"ruta": str(principal), "codigo": ""}},
            "archivos": {}, "descartados": [], "principal_registrado": False}


def _firma_arbol(fuentes: list[Path], opts: Opciones) -> dict:
    """Opciones que cambian LO QUE PRODUCE el recorrido de las fuentes: las propias
    fuentes (en orden: el id de origen es posicional) y las de recorrido de FS. Si
    cambian, la caché del árbol no vale."""
    return {"fuentes": [str(f) for f in fuentes],
            "seguir_enlaces": opts.seguir_enlaces, "omitir_ocultos": opts.omitir_ocultos}


def _procesados(indice: dict) -> set[tuple[str, str]]:
    """(origen, ruta_original) ya combinados o descartados (para reanudar)."""
    s: set[tuple[str, str]] = set()
    for e in indice["archivos"].values():
        if e["origen"] != "principal":
            s.add((e["origen"], e["ruta_original"]))
    for d in indice["descartados"]:
        s.add((d["origen"], d["ruta_original"]))
    return s


# ==========================================================================
# Utilidades
# ==========================================================================
def _walk_rel(base: Path, opts: Opciones) -> Iterator[str]:
    """Rutas relativas (posix) de los ARCHIVOS bajo `base`, saltando el índice
    (y los ocultos si `omitir_ocultos`)."""
    base = Path(base)
    for dirpath, dirnames, filenames in os.walk(base, followlinks=opts.seguir_enlaces):
        if opts.omitir_ocultos:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(base)
        for nombre in filenames:
            if opts.omitir_ocultos and nombre.startswith("."):
                continue
            rel = (rel_dir / nombre).as_posix()
            if rel in (INDICE_NOMBRE, ARBOL_NOMBRE):   # nunca el índice ni la caché
                continue
            yield rel


def _copiar(src: Path, dest: Path) -> None:
    """Copia preservando metadatos (mtime) con temporal + replace atómico."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)


def _sanea(s: str) -> str:
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in s).strip("_")


def _codigos(fuentes: list[Path], opts: Opciones) -> list[str]:
    """Código de origen por fuente (D3), garantizando unicidad."""
    out: list[str] = []
    for i, f in enumerate(fuentes, 1):
        if opts.modo_codigo == "id":
            c = f"d{i}"
        elif opts.modo_codigo == "personalizado":
            base = _sanea(opts.codigo_personalizado) or f"c{i}"
            c = base if len(fuentes) == 1 else f"{base}{i}"
        else:                                 # basename (por defecto)
            c = _sanea(f.name) or f"d{i}"
        out.append(c)
    vistos: dict[str, int] = {}
    for i, c in enumerate(out):
        if c in vistos:
            vistos[c] += 1
            out[i] = f"{c}_{vistos[c]}"
        else:
            vistos[c] = 1
    return out


def _rel_renombrado(rel: str, codigo: str, principal: Path) -> str:
    """Ruta destino con el código de origen añadido al nombre (sin colisionar)."""
    p = Path(rel)
    cand = p.parent / f"{p.stem}_{codigo}{p.suffix}"
    n = 2
    while (principal / cand).exists():
        cand = p.parent / f"{p.stem}_{codigo}_{n}{p.suffix}"
        n += 1
    return cand.as_posix()


def _gana_entrante(src: Path, dest: Path, criterio: str) -> bool:
    """¿Gana el archivo entrante frente al del principal? (empate → no)."""
    ss, ds = src.stat(), dest.stat()
    if criterio == "mayor":
        return ss.st_size > ds.st_size
    if criterio == "menor":
        return ss.st_size < ds.st_size
    if criterio == "mas_antiguo":
        return ss.st_mtime < ds.st_mtime
    return ss.st_mtime > ds.st_mtime          # mas_reciente (por defecto)


def rutas_validadas(principal: Path, fuentes: list[Path]) -> tuple[Path, list[Path]]:
    """Normaliza el principal (se crea si no existe) y comprueba que TODAS las
    fuentes existen y son carpetas. Lanza ValueError si algo falla."""
    p = Path(principal).expanduser()
    p = p.resolve()
    if p.exists() and not p.is_dir():
        raise ValueError(f"'{principal}' no es una carpeta.")
    fs: list[Path] = []
    for f in fuentes:
        q = Path(f).expanduser().resolve()
        if not q.exists():
            raise ValueError(f"El directorio a combinar no existe: {f}")
        if not q.is_dir():
            raise ValueError(f"'{f}' no es una carpeta.")
        if q == p or p in q.parents or q in p.parents:
            raise ValueError(f"El principal y '{f}' no pueden contenerse mutuamente.")
        fs.append(q)
    if not fs:
        raise ValueError("Indica al menos un directorio a combinar.")
    p.mkdir(parents=True, exist_ok=True)      # el principal puede estar vacío o no existir
    return p, fs


# ==========================================================================
# Motor
# ==========================================================================
def ejecutar(entradas: dict, opts: Opciones, *, log: Callable[[str], None] = print,
             progreso=None, pausar=None, cancelar=None, confirmar=None) -> Resultado:
    """Contrato uniforme para la GUI (B). `entradas` = {"principal", "fuentes"}."""
    principal, fuentes = entradas["principal"], entradas["fuentes"]
    log(f"Principal: {principal}")
    for f in fuentes:
        log(f"Combinar : {f}")
    return procesar(principal, fuentes, opts, log=log, progreso=progreso,
                    pausar=pausar, cancelar=cancelar, confirmar=confirmar)


def procesar(principal: Path, fuentes: list[Path], opts: Opciones, *,
             log: Callable[[str], None] = print,
             progreso: Callable[[int, int, float, str], None] | None = None,
             pausar: Callable[[], bool] | None = None,
             cancelar: Callable[[], bool] | None = None,
             confirmar: Callable[[str, bool], bool] | None = None) -> Resultado:
    """Funde `fuentes` (en orden) dentro de `principal`. Reanudable por índice.
    Paraleliza por archivo si el perfil lo aconseja (SSD), serializando por ruta
    de destino y la escritura del índice (D7)."""
    t0 = time.monotonic()
    pausar = pausar or (lambda: False)
    cancelar = cancelar or (lambda: False)
    principal = Path(principal)
    perf = recursos.preparar(principal, opts.politica,
                             ruta_origen=(fuentes[0] if fuentes else None), log=log)

    # --- Índice (D1/D9) ---
    indice = cargar_indice(principal) if opts.crear_indice else None
    if opts.crear_indice and indice is None:
        indice = _indice_nuevo(principal)
    if indice is not None and not indice.get("principal_registrado"):
        # D4: registrar los archivos que YA tenía el principal (origen=principal).
        for rel in _walk_rel(principal, opts):
            indice["archivos"].setdefault(
                rel, {"origen": "principal", "ruta_original": rel})
        indice["principal_registrado"] = True
        guardar_indice(principal, indice)
    procesados = _procesados(indice) if indice is not None else set()

    # --- Unidades de trabajo (una por archivo a combinar), saltando lo ya hecho ---
    codigos = _codigos(fuentes, opts)

    # El recorrido de las fuentes se cachea (solo si hay índice, es decir, si el
    # proceso es reanudable): al reanudar no se vuelven a recorrer las fuentes. El
    # índice sigue filtrando lo ya hecho. Sin índice no hay reanudación: se explora
    # directo, sin dejar caché.
    def _explorar():
        log("Explorando los directorios a combinar...")
        return {f"d{i}": list(_walk_rel(fuente, opts))
                for i, fuente in enumerate(fuentes, 1)}

    if indice is not None:
        cache = CacheArbol(principal / ARBOL_NOMBRE, _firma_arbol(fuentes, opts))
        por_fuente = cache.obtener(_explorar, log=log)
    else:
        cache = None
        por_fuente = _explorar()

    items: list[tuple[str, Path, str, str]] = []
    for i, fuente in enumerate(fuentes, 1):
        oid = f"d{i}"
        if indice is not None:
            indice["origenes"][oid] = {"ruta": str(fuente), "codigo": codigos[i - 1]}
        for rel in por_fuente[oid]:
            if indice is not None and (oid, rel) in procesados:
                continue
            items.append((oid, fuente, rel, codigos[i - 1]))
    total = len(items)
    n_hilos = recursos.calcular_hilos(perf, opts.politica, unidades=total)
    log(f"  {total} archivos a combinar; "
        + (f"en paralelo con {n_hilos} hilos." if n_hilos > 1 else "secuencial (1 hilo)."))

    # --- Estado COMPARTIDO entre hilos (serializado con cerrojos, D7) ---
    cont = {"hechos": 0, "copiados": 0, "renombrados": 0, "mantenidos": 0,
            "reemplazados": 0}
    errores: list[str] = []
    ilock = threading.Lock()                 # índice + contadores + errores
    locks_ruta: dict[str, threading.Lock] = {}
    guard = threading.Lock()
    pausa_ruta = principal.parent / PAUSE_NAME

    def _lock_ruta(rel: str) -> threading.Lock:
        with guard:                          # un cerrojo por ruta destino (rel)
            lk = locks_ruta.get(rel)
            if lk is None:
                lk = locks_ruta[rel] = threading.Lock()
            return lk

    def _combinar_uno(item) -> None:
        oid, fuente, rel, codigo = item
        src = fuente / rel
        try:
            with _lock_ruta(rel):            # solo se serializan items del MISMO destino
                dest = principal / rel
                if not dest.exists():
                    _copiar(src, dest)
                    with ilock:
                        if indice is not None:
                            indice["archivos"][rel] = {"origen": oid, "ruta_original": rel}
                        cont["copiados"] += 1
                elif opts.conflicto == "mantener":
                    with ilock:
                        if indice is not None:
                            indice["descartados"].append(
                                {"origen": oid, "ruta_original": rel, "motivo": "mantenido"})
                        cont["mantenidos"] += 1
                elif opts.conflicto == "reemplazar":
                    gana = _gana_entrante(src, dest, opts.criterio_reemplazo)
                    if gana:
                        _copiar(src, dest)    # sobrescribe (el del principal pierde)
                    with ilock:
                        if gana and indice is not None:
                            perdedor = indice["archivos"].pop(
                                rel, {"origen": "principal", "ruta_original": rel})
                            indice["descartados"].append({**perdedor, "motivo": "reemplazado"})
                            indice["archivos"][rel] = {"origen": oid, "ruta_original": rel}
                        elif not gana and indice is not None:
                            indice["descartados"].append(
                                {"origen": oid, "ruta_original": rel, "motivo": "reemplazado"})
                        cont["reemplazados"] += 1
                else:                          # renombrar (por defecto)
                    nrel = _rel_renombrado(rel, codigo, principal)
                    _copiar(src, principal / nrel)
                    with ilock:
                        if indice is not None:
                            indice["archivos"][nrel] = {"origen": oid, "ruta_original": rel}
                        cont["renombrados"] += 1
        except OSError as e:
            with ilock:
                errores.append(f"{src}: {e}")
            log(f"[!] No se pudo combinar {rel}: {e}")
        if opts.detallado:
            log(f"  [{oid}] {rel}")
        with ilock:
            cont["hechos"] += 1
            h = cont["hechos"]
            if progreso and (h % 25 == 0 or h == total):
                progreso(h, total, min(1.0, (h / total) if total else 0.0), rel)
            if indice is not None and h % PASO_REGISTRO == 0:
                guardar_indice(principal, indice)

    ctrl = Control(pausar=pausar, cancelar=cancelar, pausa_ruta=pausa_ruta)
    try:
        if n_hilos <= 1:
            for item in items:
                if ctrl.debe_parar():
                    break
                _combinar_uno(item)
        else:
            plan = paralelo.PlanLista(items)
            ejec = paralelo.Ejecutor(n_hilos)
            limite = (recursos.regulador_carga(perf.cpu, n_hilos)
                      if opts.politica.throttling else None)
            ctrl.desde_ejecutor(ejec.ejecutar(plan, _combinar_uno, ctrl.debe_pausar,
                                              limite_activos=limite, cancelar=cancelar))
    except KeyboardInterrupt:
        ctrl.motivo = "Proceso cortado."

    if indice is not None:
        guardar_indice(principal, indice)
    seg = time.monotonic() - t0
    hechos = cont["hechos"]

    if ctrl.motivo:
        log(ctrl.motivo)
        log("Vuelve a lanzarlo para seguir combinando lo que queda.")
        return Resultado(ctrl.estado, hechos, max(0, total - hechos), total, errores,
                         principal, ctrl.motivo, seg)

    if cache is not None:
        cache.borrar()                       # completado: la caché del árbol ya no hace falta
    log(f"Combinado: {cont['copiados']} nuevos, {cont['renombrados']} renombrados, "
        f"{cont['mantenidos']} mantenidos, {cont['reemplazados']} por reemplazo, "
        f"en {duracion(seg)}.")
    if not opts.crear_indice:
        log("[!] Sin índice: este resultado NO se podrá descombinar.")
    if errores:
        log(f"[!] {len(errores)} archivos dieron error.")
    return Resultado("completado", hechos, 0, total, errores, principal, "", seg)


# ==========================================================================
# Consola
# ==========================================================================
def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Funde varios directorios dentro de un directorio principal "
                    "manteniendo la estructura común.")
    p.add_argument("principal", type=Path, help="directorio principal (destino, in situ)")
    p.add_argument("fuentes", type=Path, nargs="+", help="directorios a combinar")
    p.add_argument("-y", "--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--conflicto", choices=CONFLICTOS, default="renombrar")
    p.add_argument("--criterio", choices=CRITERIOS, default="mas_reciente",
                   help="para --conflicto reemplazar")
    p.add_argument("--codigo", choices=MODOS_CODIGO, default="basename")
    p.add_argument("--codigo-texto", default="", help="código si --codigo personalizado")
    p.add_argument("--sin-indice", action="store_true",
                   help="no crear el índice (más rápido; NO descombinable)")
    p.add_argument("--omitir-ocultos", action="store_true")
    p.add_argument("--seguir-enlaces", action="store_true")
    p.add_argument("--detallado", action="store_true")
    args = p.parse_args(argv)

    try:
        principal, fuentes = rutas_validadas(args.principal, args.fuentes)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    opts = Opciones(conflicto=args.conflicto, criterio_reemplazo=args.criterio,
                    modo_codigo=args.codigo, codigo_personalizado=args.codigo_texto,
                    crear_indice=not args.sin_indice,
                    omitir_ocultos=args.omitir_ocultos,
                    seguir_enlaces=args.seguir_enlaces, detallado=args.detallado)

    avisos = []
    if args.conflicto == "reemplazar":
        avisos.append("AVISO: 'reemplazar' descarta archivos DE FORMA IRREVERSIBLE.")
    if args.sin_indice:
        avisos.append("AVISO: sin índice, el resultado NO se podrá descombinar.")
    return correr_cli(ejecutar, {"principal": principal, "fuentes": fuentes}, opts,
                      si=args.si, antes=("\n".join(avisos) or None))


if __name__ == "__main__":
    sys.exit(main())
