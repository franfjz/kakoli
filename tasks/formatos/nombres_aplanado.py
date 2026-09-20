# -*- coding: utf-8 -*-
"""nombres_aplanado — códec de nombres del aplanado (compartido por Aplanar/Desaplanar).

Aplanar codifica la ruta en el nombre con un separador (`aplanar_nombre`); Desaplanar
la reconstruye partiendo el nombre por ese separador (`desaplanar_nombre`, con
anti path-traversal). Vive aquí, y no dentro de un motor, para que ninguno de los dos
gemelos "esconda" código que el otro necesita.

También los nombres de los registros de progreso reanudable de ambas tareas: Desaplanar
necesita saber el de Aplanar para excluirlo del recorrido (no reconstruirlo).
"""
from __future__ import annotations

from pathlib import PurePosixPath

# Ficheros de registro de progreso reanudable (roadmap_reanudar.md).
REGISTRO_APLANADO = ".kakoli_aplanado.json"
REGISTRO_DESAPLANADO = ".kakoli_desaplanado.json"

# Cachés del árbol explorado (core.cache_arbol): evitan volver a recorrer el disco al
# reanudar. Viven junto al registro de progreso, en la carpeta de salida.
ARBOL_APLANADO = ".kakoli_aplanado_arbol.json"
ARBOL_DESAPLANADO = ".kakoli_desaplanado_arbol.json"


def separador_ok(sep: str) -> str:
    """Valida el separador de niveles (texto libre, uno o varios caracteres).
    Devuelve un mensaje de error, o '' si es válido."""
    if not sep:
        return "El separador no puede estar vacío."
    if "/" in sep or "\\" in sep:
        return "El separador no puede contener '/' ni '\\'."
    return ""


def aplanar_nombre(rel: str, sep: str = "-") -> str:
    """`nivel1/nivel2/archivo.txt` -> `nivel1-nivel2-archivo.txt` (rel en posix).
    `sep` puede tener uno o varios caracteres."""
    return sep.join(p for p in rel.split("/") if p)


def _sanea_seg(seg: str) -> str:
    """Segmento de carpeta seguro (anti-traversal): sin '.', '..', ni separadores
    de ruta. Devuelve '' si no queda nada usable."""
    seg = seg.strip().strip("/\\")
    if seg in ("", ".", ".."):
        return ""
    # nunca dejar que un segmento reintroduzca separadores de ruta ni una unidad
    # o flujo alterno de datos (ADS) en Windows (`C:`, `nombre:flujo`).
    return seg.replace("/", "_").replace("\\", "_").replace(":", "_")


def desaplanar_nombre(nombre: str, sep: str = "-") -> str:
    """`nivel1-nivel2-archivo.txt` -> `nivel1/nivel2/archivo.txt` (posix).
    Sin separador -> el propio nombre (queda en la raíz). Anti path-traversal."""
    if not sep:
        return nombre
    partes = nombre.split(sep)
    archivo = partes[-1].strip()
    if archivo in (".", ".."):                # nombre de archivo degenerado
        archivo = "_"
    elif archivo == "":
        archivo = nombre or "_"
    carpetas = [s for s in (_sanea_seg(p) for p in partes[:-1]) if s]
    if carpetas:
        return (PurePosixPath(*carpetas) / archivo).as_posix()
    return archivo
