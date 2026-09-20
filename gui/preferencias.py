# -*- coding: utf-8 -*-
"""preferencias — persistencia de los ajustes de la GUI entre sesiones.

Guarda en `%APPDATA%/kakoli/config.json` (o `~/.config/kakoli/config.json` en otros
SO) lo que hoy se perdería al cerrar: rendimiento (Hilos / Modo ligero / Registro
detallado), la última tarea abierta, la última carpeta usada en los diálogos y la
geometría de la ventana. La App decide qué claves usa; aquí solo se lee/escribe un
`dict`.

Robusto por diseño: si el fichero falta, está corrupto o no se puede escribir
(permisos, disco lleno), se degrada a valores por defecto y **nunca** lanza —los
ajustes son una comodidad, no deben impedir arrancar ni cerrar la app.

No depende de Tkinter. El escritor atómico (temporal + `os.replace`) se implementa
aquí en local a propósito, para que `gui` no dependa de piezas del núcleo que
pudieran no estar presentes; es idéntico en espíritu a `core.json_util`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def ruta_config() -> Path:
    """Ruta del fichero de configuración según el SO (roaming en Windows)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "kakoli" / "config.json"


def cargar(ruta: "Path | None" = None) -> dict:
    """Lee la configuración. Devuelve `{}` si no existe o es ilegible (fichero a
    medias, JSON corrupto, tipo inesperado): quien llama usa sus valores por defecto."""
    ruta = ruta or ruta_config()
    try:
        with open(ruta, encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def guardar(datos: dict, ruta: "Path | None" = None) -> bool:
    """Escribe la configuración de forma ATÓMICA (temporal + reemplazo). Silencioso:
    devuelve True si se guardó, False si no se pudo (permisos, disco lleno…) sin
    lanzar nunca."""
    ruta = ruta or ruta_config()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = ruta.with_name(ruta.name + ".part")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, ruta)
        return True
    except OSError:
        return False
