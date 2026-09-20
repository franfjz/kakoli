# -*- coding: utf-8 -*-
"""Chrome propio de la ventana (sin barra de título nativa). Solo se prueba lo
verificable sin display: presencia de los controles y el maximizar/restaurar
manual. El overrideredirect real y la barra de tareas (ctypes) son de arranque y
solo se validan de forma interactiva."""
from __future__ import annotations

import pytest

from gui import marco_ventana

pytestmark = pytest.mark.gui


def test_es_windows_devuelve_bool():
    assert isinstance(marco_ventana.es_windows(), bool)


@pytest.mark.skipif(not marco_ventana.es_windows(), reason="chrome propio solo en Windows")
def test_controles_ventana_presentes(app):
    # La franja del panel derecho trae min / maximizar / cerrar.
    strip = app._b_maximizar.master
    botones = [w for w in strip.winfo_children() if w.winfo_class() == "TButton"]
    assert len(botones) == 3


@pytest.mark.skipif(not marco_ventana.es_windows(), reason="chrome propio solo en Windows")
def test_maximizar_alterna_y_restaura(app, monkeypatch):
    # Se registra qué geometría PIDE _alternar_maximizar (el readback en una ventana
    # oculta no es fiable), y se comprueba el flag y que restaurar usa _geo_normal.
    prev_max, prev_geo = app._maximizada, app._geo_normal
    pedidas: list[str] = []
    orig = type(app).geometry

    def _geo(self, arg=None):
        if arg is not None:
            pedidas.append(arg)
        return orig(self, arg) if arg is not None else orig(self)
    monkeypatch.setattr(type(app), "geometry", _geo)
    try:
        x, y, w, h = app._area_trabajo()
        # Restaurar desde maximizado usa _geo_normal.
        app._maximizada = True
        app._geo_normal = "800x600+40+40"
        app._alternar_maximizar()
        assert app._maximizada is False                         # restaurado
        assert pedidas[-1] == "800x600+40+40"                   # vuelve al tamaño normal
        # Maximizar ocupa el área de trabajo (no 'zoomed').
        app._alternar_maximizar()
        assert app._maximizada is True                          # maximizado
        assert pedidas[-1] == f"{w}x{h}+{x}+{y}"
    finally:
        app._maximizada, app._geo_normal = prev_max, prev_geo
