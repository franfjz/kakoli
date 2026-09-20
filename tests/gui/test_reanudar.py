# -*- coding: utf-8 -*-
"""Diálogo de reanudación con botones etiquetados (Fase 10). El constructor no
bloquea (el modal solo lo hace `mostrar()`), así que se puede probar el mapeo de
cada botón invocándolo directamente."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_botones_mapean_al_contrato(app):
    from gui.componentes import DialogoReanudar
    # Continuar=False, Empezar de cero=True, Cancelar=None.
    for atributo, esperado in (("_b_continuar", False),
                               ("_b_cero", True),
                               ("_b_cancelar", None)):
        d = DialogoReanudar(app, "Se encontró una tarea a medias.")
        getattr(d, atributo).invoke()
        assert d.resultado is esperado


def test_etiquetas_claras(app):
    from gui.componentes import DialogoReanudar
    d = DialogoReanudar(app, "mensaje")
    assert str(d._b_continuar.cget("text")) == "Continuar"
    assert str(d._b_cero.cget("text")) == "Empezar de cero"
    assert str(d._b_cancelar.cget("text")) == "Cancelar"
    d.win.destroy()


def test_sin_elegir_es_cancelar(app):
    from gui.componentes import DialogoReanudar
    d = DialogoReanudar(app, "mensaje")
    assert d.resultado is None            # cerrar/Esc = cancelar
    d.win.destroy()


def test_preguntar_reanudar_enruta_al_dialogo(app, monkeypatch):
    from gui import componentes
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    # El motor detecta una tarea a medias...
    monkeypatch.setattr(pes.MOTOR, "info_reanudable",
                        lambda entradas, opts: {"hechas": 3, "total": 10, "fecha": ""})
    # ...y el usuario pulsa "Empezar de cero" (True).
    monkeypatch.setattr(componentes, "dialogo_reanudar", lambda *a, **k: True)
    datos = {"entradas": {"origen": None, "destino": None}, "opts": None}
    assert pes._preguntar_reanudar(datos) is True


def test_preguntar_reanudar_sin_info_no_pregunta(app, monkeypatch):
    from gui import componentes
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    monkeypatch.setattr(pes.MOTOR, "info_reanudable", lambda entradas, opts: None)
    # Si se llamara al diálogo, fallaría; no debe llamarse.
    monkeypatch.setattr(componentes, "dialogo_reanudar",
                        lambda *a, **k: pytest.fail("no debe preguntar sin progreso"))
    datos = {"entradas": {"origen": None}, "opts": None}
    assert pes._preguntar_reanudar(datos) is False
