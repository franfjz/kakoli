# -*- coding: utf-8 -*-
"""Navegación de dos niveles y bloqueo 'una tarea a la vez'."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _textos(app):
    return [t for t, _en, _act in app.estado_barra()]


def test_entrar_en_categoria_muestra_sus_tareas(app):
    app._entrar(app.registro.categorias[1])              # "Compresión" -> Comprimir/Descomprimir
    textos = _textos(app)
    assert any("←" in t for t in textos)
    assert any("Comprimir" in t for t in textos)
    assert any("Descomprimir" in t for t in textos)


def test_mostrar_selecciona_la_tarea(app):
    from tasks.descomprimir.pestana import PestanaDescomprimir
    pes = app.mostrar(PestanaDescomprimir)
    assert pes is app.pestana(PestanaDescomprimir)
    assert app._tarea_actual is pes
    activos = [t for t, _en, act in app.estado_barra() if act]
    assert activos and "Descomprimir" in activos[0]


def test_ir_menu_vuelve_al_nivel_1(app):
    app._entrar(app.registro.categorias[1])
    app._ir_menu()
    assert app._categoria_actual is None
    assert app.estado_barra() == []


def test_bloqueo_deshabilita_hermanas_y_volver(app):
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.mostrar(PestanaComprimir)
    app.bloquear(pes)
    try:
        assert app._bloqueado is True
        barra = app.estado_barra()
        # El botón de volver '←' queda deshabilitado.
        volver = [en for t, en, _act in barra if "←" in t]
        assert volver and volver[0] is False
        # La activa sigue habilitada; alguna hermana queda deshabilitada.
        activos = [(t, en) for t, en, act in barra if act]
        assert activos and activos[0][1] is True
    finally:
        app.desbloquear()
    assert app._bloqueado is False
