# -*- coding: utf-8 -*-
"""formato_zip — marca del formato "ZIP anidado" (compartida por Comprimir/Descomprimir).

Comprimir ESCRIBE una marca en el comentario del ZIP (un JSON con `formato`=MARCA_FORMATO)
y Descomprimir la LEE (`leer_marca`) para distinguir un ZIP de carpeta de un ZIP de datos
del usuario. Vive aquí, y no dentro de un motor, para que ninguno de los dos gemelos
"esconda" código que el otro necesita.
"""
from __future__ import annotations

import functools
import json
import zipfile
from pathlib import Path

MARCA_FORMATO = "zip-anidado/1"


def _leer_marca_disco(zip_str: str) -> dict | None:
    """Lee la marca abriendo el ZIP (parte cara). El resultado se cachea por
    (ruta, tamaño, mtime) en leer_marca; NO mutar el dict devuelto."""
    try:
        with zipfile.ZipFile(zip_str) as zf:
            comentario = zf.comment
    except (OSError, zipfile.BadZipFile):
        return None
    if not comentario:
        return None
    try:
        datos = json.loads(comentario.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(datos, dict) and datos.get("formato") == MARCA_FORMATO:
        return datos
    return None


@functools.lru_cache(maxsize=4096)
def _marca_cacheada(zip_str: str, tam: int, mtime_ns: int) -> dict | None:
    return _leer_marca_disco(zip_str)


def leer_marca(zip_path: Path) -> dict | None:
    """Devuelve la marca de 'carpeta comprimida' de un ZIP, o None si no la tiene.

    #6 (optimización): la descompresión pregunta por la marca del mismo ZIP
    varias veces (filtro, expansión, reanudación). Se cachea por (ruta, tamaño,
    mtime) para no reabrir el ZIP cada vez; un stat basta para validar la caché.
    No mutar el dict devuelto (se comparte entre llamadas)."""
    try:
        st = zip_path.stat()
    except OSError:
        return None
    return _marca_cacheada(str(zip_path), st.st_size, st.st_mtime_ns)
