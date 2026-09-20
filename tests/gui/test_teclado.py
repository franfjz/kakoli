# -*- coding: utf-8 -*-
"""Atajos de teclado y navegación con Esc (Fase 6). Se prueban los manejadores de
App directamente; el foco y el `invoke` de los botones se parchean porque la ventana
de test está oculta (el foco real no es fiable sin mainloop)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _comprimir(app):
    from tasks.comprimir.pestana import PestanaComprimir
    return app.mostrar(PestanaComprimir)


def test_atajo_pulsa_el_boton_de_la_tarea_visible(app, monkeypatch):
    pes = _comprimir(app)
    llamado = []
    monkeypatch.setattr(pes.b_pausar, "invoke", lambda: llamado.append(True))
    assert app._atajo_boton("b_pausar") == "break"
    assert llamado == [True]


def test_atajo_no_hace_nada_en_portada(app):
    app._ir_menu()
    assert app._tarea_actual is None
    assert app._atajo_boton("b_iniciar") == "break"     # no lanza


def test_atajo_no_actua_en_ayuda(app, monkeypatch):
    pes = _comprimir(app)
    monkeypatch.setattr(pes.b_iniciar, "invoke",
                        lambda: pytest.fail("no debería invocar en Ayuda"))
    app._entrar_ayuda()
    app._atajo_boton("b_iniciar")                        # _en_ayuda: no hace nada


def test_escape_vuelve_al_menu(app, monkeypatch):
    _comprimir(app)
    monkeypatch.setattr(app, "focus_get", lambda: None)
    assert app._atajo_escape() == "break"
    assert app._categoria_actual is None
    assert app._tarea_actual is None


def test_escape_no_navega_si_bloqueado(app):
    pes = _comprimir(app)
    app.bloquear(pes)
    try:
        app._atajo_escape()
        assert app._tarea_actual is pes                 # sigue en la tarea
    finally:
        app.desbloquear()


def test_escape_ignora_foco_en_entrada(app, monkeypatch):
    pes = _comprimir(app)
    monkeypatch.setattr(app, "focus_get", lambda: pes.e_origen)   # Entry con el foco
    app._atajo_escape()
    assert app._tarea_actual is pes                     # no navega: Esc es del widget


def test_escape_cierra_la_ayuda(app, monkeypatch):
    app._entrar_ayuda()
    assert app._en_ayuda is True
    monkeypatch.setattr(app, "focus_get", lambda: None)
    app._atajo_escape()
    assert app._en_ayuda is False


def test_boton_volver_texto_descriptivo(app):
    _comprimir(app)
    textos = [t for t, _en, _act in app.estado_barra()]
    assert any("Menú" in t for t in textos)
