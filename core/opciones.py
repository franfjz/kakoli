# -*- coding: utf-8 -*-
"""opciones — campos de opciones COMUNES a todos los motores (núcleo, sin Tkinter).

Cada motor define su propia `Opciones(OpcionesBase)` añadiendo SOLO sus campos
específicos. Antes vivía en `core.comun`; se separó aquí (Fase 6 de mejoras) y se
subieron a la base las opciones de RECORRIDO del sistema de archivos que varios
motores repetían (`seguir_enlaces`, `omitir_ocultos`)."""
from __future__ import annotations

from dataclasses import dataclass, field

from core import recursos


@dataclass
class OpcionesBase:
    """Campos de opciones que comparte cualquier motor.

    - `detallado`: una línea de registro por unidad procesada.
    - `politica`: política de rendimiento común (hilos/RAM/modo ligero); el
      auto-cálculo de hilos vive en `recursos.calcular_hilos`.
    - `seguir_enlaces` / `omitir_ocultos`: recorrido del sistema de archivos, comunes
      a los motores que exploran un árbol (los que no exploran los ignoran).
    """
    detallado: bool = False
    politica: recursos.PoliticaHilos = field(
        default_factory=recursos.PoliticaHilos)
    seguir_enlaces: bool = False
    omitir_ocultos: bool = False
