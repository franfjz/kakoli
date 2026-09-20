# -*- coding: utf-8 -*-
"""Instanciación perezosa de pestañas (Fase 9): en el arranque no se crea ninguna;
se crean al mostrarlas, y el handoff crea la consumidora aunque no se haya abierto.

Usa una App SEPARADA (no la de sesión, que se fuerza a instanciar todas): en este
entorno Tk no admite dos roots a la vez de forma fiable, así que se SALTA si Tcl
falla. Se construye una sola App para no multiplicar roots."""
from __future__ import annotations

import tkinter as tk

import pytest

pytestmark = pytest.mark.gui


def test_instanciacion_perezosa(monkeypatch):
    from gui import preferencias
    from gui.app import App
    from tasks import REGISTRO
    from tasks.comprimir.pestana import PestanaComprimir
    from tasks.descomprimir.pestana import PestanaDescomprimir

    monkeypatch.setattr(preferencias, "cargar", lambda *a, **k: {})   # arranca en portada
    try:
        a = App(REGISTRO)
    except tk.TclError as e:
        pytest.skip(f"Tkinter no disponible: {e}")
    a.withdraw()
    a.update_idletasks()
    try:
        # 1) Arranque en portada: ninguna pestaña instanciada.
        assert a._por_clase == {}
        assert a.pestanas == ()

        # 2) Mostrar una crea SOLO esa (Comprimir es la primera de su categoría).
        a.mostrar(PestanaComprimir)
        assert set(a._por_clase) == {PestanaComprimir}

        # 3) El handoff instancia a la consumidora aunque no se haya abierto.
        receptora = a.sugerir_entrada("C:/x.zip", "zip_anidado")
        assert isinstance(receptora, PestanaDescomprimir)
        assert receptora.v_origen.get() == "C:/x.zip"
        assert PestanaDescomprimir in a._por_clase
    finally:
        try:
            a.destroy()
        except tk.TclError:
            pass
