# -*- coding: utf-8 -*-
"""Regresión de P2 (corregido en la Fase 3): PestanaDescomprimir._preguntar ya
importa `threading`, así que construir `threading.Event()` en la confirmación
DURANTE la tarea no lanza NameError.

Antes de tocar Tk entre hilos (fuera del alcance de P2), se ejecuta `_preguntar`
en el hilo principal parcheando `after` para que el callback corra en el acto: así
se ejercita la línea que fallaba (`threading.Event()`) y el `evento.wait()`."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_preguntar_no_lanza_nameerror(app, monkeypatch):
    from tasks.descomprimir.pestana import PestanaDescomprimir
    pes = app.pestana(PestanaDescomprimir)

    # after(0, fn) ejecuta fn de inmediato en este hilo (evita Tk entre hilos).
    monkeypatch.setattr(pes, "after", lambda _delay, fn: fn())

    # askyesno está neutralizado a True por la fixture _sin_dialogos.
    assert pes._preguntar("¿sobrescribir?", False) is True


def test_modulo_descomprimir_tiene_threading():
    """El símbolo `threading` está en el espacio de nombres del módulo (P2)."""
    import tasks.descomprimir.pestana as pd
    assert hasattr(pd, "threading")
