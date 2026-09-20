# -*- coding: utf-8 -*-
"""Componentes reutilizables de GUI: MarcoDesplazable y fila_texto."""
from __future__ import annotations

import tkinter as tk

import pytest

pytestmark = pytest.mark.gui


def test_marco_desplazable_expone_interior_y_lienzo(app):
    from gui import componentes
    marco = componentes.MarcoDesplazable(app, padding=8, margen=4)
    assert isinstance(marco.lienzo, tk.Canvas)
    assert marco.interior is not None
    # Se puede poblar el interior sin error.
    from tkinter import ttk
    ttk.Label(marco.interior, text="hola").pack()
    app.update_idletasks()


def test_fila_texto_devuelve_frame_y_entry(app):
    from gui import componentes
    var = tk.StringVar(value="x")
    fila, entry = componentes.fila_texto(app, "Etiqueta:", var, width=10)
    assert entry.get() == "x"
    assert str(entry.cget("width")) == "10"
    app.update_idletasks()


def test_pestana_usa_marco_para_opciones(app):
    """Cada pestaña tiene su área de opciones desplazable (contenedor_ops dentro de
    un Canvas)."""
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    assert isinstance(pes._lienzo, tk.Canvas)
    assert pes.contenedor_ops is not None
