#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""explorar — recorrido del árbol de carpetas para Comprimir (parte del paquete).

Enumera el árbol (`explorar`) en post-orden (hijos antes que padres) con la info por
carpeta (`InfoDir`) que necesitan el planificador y el compresor, decide qué
subárboles se empaquetan juntos en el modo compacto (`seleccionar_agrupados`), y
lo convierte a/desde JSON (`serializar_arbol`/`deserializar_arbol`) para que la caché
común (`core.cache_arbol.CacheArbol`) evite volver a recorrer el disco al reanudar
tras una pausa o cancelación."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tasks.comprimir.motor import Opciones

# Raíz relativa del árbol (la propia carpeta de origen).
RAIZ = Path(".")


@dataclass(slots=True)
class InfoDir:
    rel: Path
    archivos: list[str] = field(default_factory=list)
    subdirs: list[str] = field(default_factory=list)
    bytes: int = 0
    # Acumulados del subárbol (los usa seleccionar_agrupados, mejora 5).
    bytes_arbol: int = 0
    archivos_arbol: int = 0
    carpetas_arbol: int = 0
    profundidad: int = 0


def ruta_abs(raiz: Path, rel: Path) -> Path:
    return raiz if rel == RAIZ else raiz / rel


def explorar(raiz: Path, seguir_enlaces: bool, omitir_ocultos: bool,
             log: Callable[[str], None] = print
             ) -> tuple[dict[Path, InfoDir], list[Path]]:
    """Devuelve (info por directorio, lista en post-orden: hijos antes que padres)."""
    infos: dict[Path, InfoDir] = {}
    orden: list[Path] = []
    visitados: set[tuple[int, int]] = set()
    pila: list[tuple[Path, bool]] = [(RAIZ, False)]

    while pila:
        rel, expandido = pila.pop()
        if expandido:
            info = infos[rel]
            info.profundidad = 0 if rel == RAIZ else len(rel.parts)
            info.bytes_arbol = info.bytes
            info.archivos_arbol = len(info.archivos)
            info.carpetas_arbol = 1
            for nombre in info.subdirs:
                hijo = infos.get(rel / nombre)
                if hijo is not None:
                    info.bytes_arbol += hijo.bytes_arbol
                    info.archivos_arbol += hijo.archivos_arbol
                    info.carpetas_arbol += hijo.carpetas_arbol
            orden.append(rel)
            continue

        carpeta = ruta_abs(raiz, rel)
        info = InfoDir(rel)
        try:
            entradas = sorted(os.scandir(carpeta), key=lambda e: e.name)
        except OSError as e:
            log(f"[!] No se puede leer {rel}: {e}")
            entradas = []

        for e in entradas:
            if omitir_ocultos and e.name.startswith("."):
                continue
            try:
                if e.is_symlink() and not seguir_enlaces:
                    continue
                if e.is_dir(follow_symlinks=seguir_enlaces):
                    if seguir_enlaces:
                        # Dedup por inodo REAL para evitar bucles de enlaces. Se
                        # usa os.stat(), NO DirEntry.stat(): en Windows la caché
                        # de scandir devuelve st_ino=0 y confundiría TODAS las
                        # carpetas con el mismo "bucle". Si el inodo no es fiable
                        # (0), no se deduplica (mejor no perder carpetas).
                        try:
                            st = os.stat(e.path)
                        except OSError:
                            st = None
                        if st is not None and st.st_ino:
                            clave = (st.st_dev, st.st_ino)
                            if clave in visitados:
                                log(f"[!] Bucle de enlaces evitado en {rel / e.name}")
                                continue
                            visitados.add(clave)
                    info.subdirs.append(e.name)
                elif e.is_file(follow_symlinks=seguir_enlaces):
                    info.archivos.append(e.name)
                    info.bytes += e.stat(follow_symlinks=seguir_enlaces).st_size
            except OSError as err:
                log(f"[!] Se omite {rel / e.name}: {err}")

        infos[rel] = info
        pila.append((rel, True))
        for nombre in reversed(info.subdirs):
            pila.append((rel / nombre, False))

    return infos, orden


_CAMPOS_INFO = ("archivos", "subdirs", "bytes", "bytes_arbol", "archivos_arbol",
                "carpetas_arbol", "profundidad")


def serializar_arbol(arbol: "tuple[dict[Path, InfoDir], list[Path]]") -> dict:
    """Convierte `(infos, orden)` a un dict JSON-serializable (el `payload` que guarda
    `core.cache_arbol.CacheArbol`). Inversa de `deserializar_arbol`."""
    infos, orden = arbol
    return {
        "orden": [r.as_posix() for r in orden],
        "infos": {rel.as_posix(): {c: getattr(info, c) for c in _CAMPOS_INFO}
                  for rel, info in infos.items()},
    }


def deserializar_arbol(payload: dict) -> "tuple[dict[Path, InfoDir], list[Path]]":
    """Reconstruye `(infos, orden)` desde el `payload` de la caché. Lanza KeyError/
    TypeError si el payload no tiene la forma esperada (la caché lo trata como fallo
    y vuelve a explorar el disco)."""
    orden = [Path(r) for r in payload["orden"]]
    infos = {Path(rel): InfoDir(rel=Path(rel), **campos)
             for rel, campos in payload["infos"].items()}
    return infos, orden


def seleccionar_agrupados(infos: dict[Path, InfoDir], orden: list[Path],
                          opts: Opciones) -> set[Path]:
    """
    MEJORA 5. Devuelve las carpetas cuyo subárbol completo debería empaquetarse
    en un solo ZIP, sin desglosar sus subcarpetas.

    El empaquetado lo hace Comprimidor.crear_agrupado. Con las tres opciones a 0
    devuelve un conjunto vacío y el programa se comporta como siempre.
    """
    if not (opts.agrupar_mb or opts.agrupar_archivos or opts.profundidad_max):
        return set()

    limite_bytes = int(opts.agrupar_mb * 1024 * 1024) if opts.agrupar_mb else 0
    elegidas: set[Path] = set()
    # De la raíz hacia abajo: así se elige siempre la carpeta más alta posible.
    for rel in reversed(orden):
        if rel in elegidas or any(p in elegidas for p in rel.parents):
            continue
        info = infos[rel]
        if not info.subdirs:
            continue                      # sin subcarpetas no hay nada que agrupar
        cabe = limite_bytes and info.bytes_arbol <= limite_bytes
        pocos = opts.agrupar_archivos and info.archivos_arbol <= opts.agrupar_archivos
        hondo = opts.profundidad_max and info.profundidad >= opts.profundidad_max
        if cabe or pocos or hondo:
            elegidas.add(rel)
    return elegidas
