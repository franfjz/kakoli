# -*- coding: utf-8 -*-
"""util — ayudas comunes a los tests de motores: política de hilos determinista y
un log que descarta. Los tests NUNCA deben bajar la prioridad del proceso de
pytest (P22) ni arrancar el regulador de throttling, así que se fuerza
`prioridad_baja=False` y `throttling=False`.
"""
from __future__ import annotations


import core.recursos as _recursos


def politica(hilos: int = 0, **kw):
    """PoliticaHilos determinista para tests. `hilos=0` = auto; >0 lo fuerza."""
    return _recursos.PoliticaHilos(hilos=hilos, prioridad_baja=False,
                                   throttling=False, **kw)


def nolog(*_a, **_k) -> None:
    """log() que descarta (los tests comprueban Resultado y disco, no textos)."""
