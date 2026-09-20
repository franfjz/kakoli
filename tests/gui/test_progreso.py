# -*- coding: utf-8 -*-
"""Progreso legible (Fase 3): barra indeterminada mientras no se conoce el total,
y estado con porcentaje + ETA cuando sí. Se prueban los helpers de PestanaBase
sobre una pestaña real, más un flujo completo que confirma que la barra vuelve a
modo determinado al terminar."""
from __future__ import annotations

import time

import pytest

from tests.gui.conftest import bombear

pytestmark = pytest.mark.gui


def _pes(app):
    from tasks.comprimir.pestana import PestanaComprimir
    return app.pestana(PestanaComprimir)


def test_texto_sin_total(app):
    pes = _pes(app)
    assert pes._texto_progreso(7, 0, 0.0, "explorando") == "7 — explorando"


def test_texto_con_total_muestra_porcentaje(app):
    pes = _pes(app)
    pes._reset_progreso()
    txt = pes._texto_progreso(50, 200, 0.25, "copiando")
    assert txt.startswith("25 % · 50/200")
    assert "copiando" in txt


def test_barra_modo_alterna(app):
    pes = _pes(app)
    pes._barra_modo(True)
    assert pes._barra_indeterminada is True
    assert str(pes.barra.cget("mode")) == "indeterminate"
    pes._barra_modo(False)
    assert pes._barra_indeterminada is False
    assert str(pes.barra.cget("mode")) == "determinate"


def test_eta_vacio_al_arrancar_y_estima_tras_calentar(app):
    pes = _pes(app)
    pes._reset_progreso()
    # Recién empezado (sin calentamiento): aún no hay ETA.
    assert pes._eta(10, 100) == ""
    # Simula una tarea con recorrido y una muestra previa fiable.
    ahora = time.monotonic()
    pes._prog_t0 = ahora - 5.0
    pes._prog_t_prev = ahora - 1.0
    pes._prog_hechas_prev = 10
    pes._prog_rate = 0.0
    eta = pes._eta(20, 100)              # ~10 u/s, 80 restantes -> ~8 s
    assert eta.startswith(" · ~")


def test_flujo_deja_la_barra_determinada(app, tmp_path):
    (tmp_path / "a.txt").write_text("x")
    from tasks.renombrar.pestana import PestanaRenombrar
    pes = app.pestana(PestanaRenombrar)
    txt = pes._widgets_lista["origenes"]
    txt.delete("1.0", "end")
    txt.insert("1.0", str(tmp_path) + "\n")
    pes.v_prefijo.set("p_")

    pes._previsualizar()
    bombear(app, pes)

    assert not pes.ocupada()
    assert pes._barra_indeterminada is False
    assert str(pes.barra.cget("mode")) == "determinate"
