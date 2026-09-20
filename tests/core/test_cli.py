# -*- coding: utf-8 -*-
"""Caracterización de core.cli: el arnés de consola correr_cli (traducción del estado
del Resultado a código de salida)."""
from __future__ import annotations

import signal

import pytest


import core.cli as cli
import core.resultado as resultado


def _motor_fake(estado):
    def ejecutar(entradas, opts, *, log=print, pausar=None, confirmar=None):
        return resultado.Resultado(estado, mensaje="msg" if estado == "error" else "")
    return ejecutar


@pytest.fixture
def _senales_intactas():
    """correr_cli instala manejadores de SIGINT/SIGTERM y no los restaura; se
    preservan para no contaminar el resto de la suite."""
    previos = {signal.SIGINT: signal.getsignal(signal.SIGINT)}
    if hasattr(signal, "SIGTERM"):
        previos[signal.SIGTERM] = signal.getsignal(signal.SIGTERM)
    try:
        yield
    finally:
        for s, h in previos.items():
            signal.signal(s, h)


@pytest.mark.parametrize("estado, codigo", [
    ("completado", 0),
    ("nada", 0),
    ("error", 1),
    ("cancelado", 1),
    ("pausado", 2),
])
def test_correr_cli_codigos(estado, codigo, capsys, _senales_intactas):
    rc = cli.correr_cli(_motor_fake(estado), {"origen": "x"}, object(), si=True)
    assert rc == codigo
