# -*- coding: utf-8 -*-
"""Caracterización de core.resultado: Resultado (defaults + validación de estado) y
EstadoResultado (intercambiable con su cadena)."""
from __future__ import annotations

import pytest


import core.resultado as resultado
Resultado = resultado.Resultado
EstadoResultado = resultado.EstadoResultado


def test_defaults():
    r = Resultado("completado")
    assert r.estado == "completado"
    assert r.procesadas == 0 and r.restantes == 0 and r.total == 0
    assert r.errores == [] and r.ruta_final is None
    assert r.mensaje == "" and r.segundos == 0.0


def test_errores_no_comparten_lista():
    a = Resultado("nada")
    b = Resultado("nada")
    a.errores.append("x")
    assert b.errores == []           # default_factory, no lista compartida


def test_estado_invalido_lanza():
    with pytest.raises(ValueError):
        Resultado("cancelodo")       # typo -> se rechaza al construir


def test_estado_enum_intercambiable_con_cadena():
    assert EstadoResultado.ERROR == "error"
    r = Resultado("error", mensaje="x")
    assert r.estado == EstadoResultado.ERROR


def test_cancelado_es_excepcion():
    assert issubclass(resultado.Cancelado, Exception)
