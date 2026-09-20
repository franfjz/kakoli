# -*- coding: utf-8 -*-
"""constantes — versión/marca, enlaces, ajustes de la GUI, mapeos de los
desplegables (etiqueta visible → valor del motor) y pequeños helpers de UI."""
from __future__ import annotations

from core import recursos

# --- Identidad de la app ---
VERSION = "1.8.0-alpha"
SUBTITULO = "Herramientas de gestión de directorios y archivos"

# Enlaces de la información de la aplicación (columna derecha).
AUTOR = "@franfjz"
URL_AUTOR = "https://github.com/franfjz/kakoli"     # repositorio del proyecto
URL_CAFE = "https://buymeacoffee.com/franfjz"       # donaciones
ICONO_CAFE = "☕"

# El registro se recorta para que la ventana no se vuelva lenta en equipos
# antiguos: un Text de tkinter con decenas de miles de líneas cuesta memoria y
# repintado. Los mensajes se insertan por lotes, no uno a uno.
MAX_LINEAS_REGISTRO = 2000
LINEAS_A_CONSERVAR = 1500
INTERVALO_BOMBA_MS = 150


def politica_desde(hilos_str: str, ligero: bool) -> recursos.PoliticaHilos:
    """Traduce los controles avanzados de la GUI a la PoliticaHilos común.
    'Auto' -> hilos=0 (lo decide recursos.calcular_hilos según CPU/RAM)."""
    hilos = 0 if hilos_str == "Auto" else int(hilos_str)
    return recursos.PoliticaHilos(hilos=hilos, prioridad_baja=ligero)


# (Las tareas con desplegables ya migraron a tasks/: sus mapeos viven en sus pestañas.
#  Comprimir/Descomprimir no usan mapeos etiqueta->valor. `_valor_ui` sigue siendo el
#  helper genérico que usan las pestañas migradas.)


def _valor_ui(pares, etiqueta, defecto):
    """Devuelve el valor asociado a `etiqueta` en una lista (etiqueta, valor)."""
    for et, val in pares:
        if et == etiqueta:
            return val
    return defecto
