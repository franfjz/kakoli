# -*- coding: utf-8 -*-
"""Selector de 'Hilos' (control segmentado): selección única y visible, layout
en columnas ('Auto' aislado + números en 4 columnas) y bloqueo durante tarea.
El indicador circular nativo se veía igual marcado que sin marcar sobre el tema
oscuro; ahora el radio elegido se ilumina y el resto queda apagado."""
from __future__ import annotations

import pytest

from gui import tema

pytestmark = pytest.mark.gui


def _seleccionados(app):
    """Radios cuyo fondo es el verde de selección (los 'marcados' visualmente)."""
    return [rb.cget("value") for rb in app._radios_hilos
            if str(rb.cget("bg")) == tema.PRIMARY]


def test_solo_uno_seleccionado_visualmente(app):
    app.v_hilos.set("Auto")
    assert _seleccionados(app) == ["Auto"]


def test_cambiar_seleccion_mueve_el_resaltado(app):
    app.v_hilos.set("1")
    assert _seleccionados(app) == ["1"]          # solo uno, y es el elegido
    app.v_hilos.set("2")
    assert _seleccionados(app) == ["2"]          # se movió; no se acumulan


def test_auto_aislado_en_primera_columna(app):
    auto = app._radios_hilos[0]
    assert auto.cget("value") == "Auto"
    info = auto.grid_info()
    assert (int(info["row"]), int(info["column"])) == (0, 0)


def test_numeros_en_las_cuatro_columnas_siguientes(app):
    # Los números ocupan las columnas 1..4 (nunca la 0, reservada a 'Auto').
    cols = {int(rb.grid_info()["column"]) for rb in app._radios_hilos[1:]}
    assert cols <= {1, 2, 3, 4}
    assert 0 not in cols


def test_radios_son_tipo_boton(app):
    # indicatoron=0: es el propio botón el que se ilumina, no un círculo.
    assert all(int(rb.cget("indicatoron")) == 0 for rb in app._radios_hilos)


def test_bloqueo_durante_tarea_y_reactivacion(app):
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    normales = [rb for rb in app._radios_hilos if str(rb.cget("state")) == "normal"]
    assert normales                                  # al menos 'Auto' y algún número
    app.bloquear(pes)
    try:
        assert all(str(rb.cget("state")) == "disabled" for rb in app._radios_hilos)
    finally:
        app.desbloquear()
    for rb in normales:
        assert str(rb.cget("state")) == "normal"     # se reactivan los seleccionables
