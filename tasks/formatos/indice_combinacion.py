# -*- coding: utf-8 -*-
"""indice_combinacion — índice de la combinación (compartido por Combinar/Descombinar).

Combinar escribe un índice JSON (`.kakoli_combinacion.json`) en el directorio principal
con el origen de cada archivo del resultado; Descombinar lo lee para reconstruir los
directorios originales. Este módulo concentra el FORMATO y la E/S del índice para que
ninguno de los dos gemelos "esconda" código que el otro necesita.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

INDICE_NOMBRE = ".kakoli_combinacion.json"
INDICE_FORMATO = "kakoli-combinacion/1"
# Caché del árbol explorado (core.cache_arbol): evita volver a recorrer las fuentes al
# reanudar. Vive en el principal, junto al índice; se descarta al completar.
ARBOL_NOMBRE = ".kakoli_combinacion_arbol.json"


def cargar_indice(principal: Path) -> dict | None:
    """Lee el índice del directorio combinado, o None si no hay/está roto."""
    ruta = Path(principal) / INDICE_NOMBRE
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, dict) and datos.get("formato") == INDICE_FORMATO:
            return datos
    except (OSError, ValueError):
        pass
    return None


def guardar_indice(principal: Path, indice: dict) -> None:
    """Escribe el índice de forma atómica (.part + os.replace)."""
    destino = Path(principal) / INDICE_NOMBRE
    tmp = destino.with_name(destino.name + ".part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=1)
    os.replace(tmp, destino)
