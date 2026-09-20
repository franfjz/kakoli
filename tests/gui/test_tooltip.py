# -*- coding: utf-8 -*-
"""Componente Tooltip y su uso en campos de ruta (Fase 8)."""
from __future__ import annotations

import tkinter as tk

import pytest

pytestmark = pytest.mark.gui


def test_actualizar_cambia_el_texto(app):
    from gui import componentes
    lbl = tk.Label(app)
    t = componentes.Tooltip(lbl, "uno")
    assert t.texto == "uno"
    t.actualizar("dos")
    assert t.texto == "dos"
    lbl.destroy()


def test_mostrar_y_ocultar(app):
    from gui import componentes
    lbl = tk.Label(app)
    lbl.pack()
    app.update_idletasks()
    t = componentes.Tooltip(lbl, "información")
    t._mostrar()
    assert t._tip is not None and t._tip.winfo_exists()
    t._ocultar()
    assert t._tip is None
    lbl.destroy()


def test_sin_texto_no_muestra(app):
    from gui import componentes
    lbl = tk.Label(app)
    lbl.pack()
    t = componentes.Tooltip(lbl, "")          # vacío: no aparece nada
    t._mostrar()
    assert t._tip is None
    lbl.destroy()


def test_actualizar_oculta_si_estaba_visible(app):
    from gui import componentes
    lbl = tk.Label(app)
    lbl.pack()
    app.update_idletasks()
    t = componentes.Tooltip(lbl, "antes")
    t._mostrar()
    assert t._tip is not None
    t.actualizar("después")                   # refresca: se oculta hasta el próximo hover
    assert t._tip is None
    assert t.texto == "después"
    lbl.destroy()


def test_tooltip_opcion_ignora_none_y_vacio(app):
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    pes._tooltip_opcion("", tk.Label(app))     # detalle vacío: no hace nada
    pes._tooltip_opcion("algo", None)          # widget None: se ignora (no lanza)


def test_opciones_adjuntan_tooltip_de_detalle(app, monkeypatch):
    from gui import componentes
    from tasks.comprimir.pestana import PestanaComprimir
    textos = []

    class TipFalso:
        def __init__(self, _w, texto="", **_k):
            textos.append(texto)

        def actualizar(self, texto):
            pass

    monkeypatch.setattr(componentes, "Tooltip", TipFalso)
    pes = PestanaComprimir(app.area_tarea, app)
    try:
        # Alguna opción aportó un 'detalle' no vacío (tooltip de ayuda ampliada).
        assert any(t for t in textos)
    finally:
        pes.destroy()


def test_fijar_ruta_no_rompe_el_campo(app):
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    pes.v_origen.set("C:/una/ruta/bastante/larga/para/probar/el/desplazamiento")
    app.update_idletasks()
    # El enganche de ruta larga (xview + tooltip) no debe alterar el valor.
    assert pes.v_origen.get().endswith("desplazamiento")
    first, last = pes.e_origen.xview()
    assert 0.0 <= first <= last <= 1.0
