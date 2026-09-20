#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""json_util — lectura y escritura de un fichero JSON, común a cualquier tarea que
necesite persistir una instantánea de datos entre ejecuciones (p. ej. un caché
reanudable). Vive en el núcleo: sin Tkinter, sin depender de ninguna tarea."""
from __future__ import annotations

import json
import os
from pathlib import Path


def guardar_json(ruta: Path, datos) -> None:
    """Escribe `datos` como JSON de forma ATÓMICA (fichero temporal + reemplazo):
    un corte a medio escribir (kill, apagón) nunca deja el destino a medias."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".part")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False)
    os.replace(tmp, ruta)


def cargar_json(ruta: Path):
    """Lee el JSON de `ruta`, o None si no existe o es ilegible (fichero a medias,
    JSON corrupto...). Quien llama decide qué hacer ante None (p. ej. regenerar)."""
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
