# -*- coding: utf-8 -*-
"""Legibilidad: fuente de ayuda a 9 pt y escala/DPI (Fase 11). Pruebas ligeras: el
efecto real es visual y depende del monitor; aquí solo se comprueba lo verificable
sin pantalla HiDPI."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_fuente_ayuda_a_9pt(app):
    from gui import tema
    assert tema.fuente("peque").cget("size") == 9
    assert tema.fuente("peque_bold").cget("size") == 9


def test_activar_dpi_es_silencioso():
    from gui import tema
    tema.activar_dpi()          # ya se llamó al crear la App; repetir no debe lanzar


def test_escala_tk_positiva(app):
    escala = float(app.tk.call("tk", "scaling"))
    assert escala > 0           # configurar() dejó una escala válida
