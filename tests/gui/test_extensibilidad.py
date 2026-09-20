# -*- coding: utf-8 -*-
"""Extensibilidad (Fase 5): App arranca con un Registro de tareas FICTICIAS —
definidas solo en el test— y las muestra, navega y encadena por artefacto, SIN
tocar core/ ni gui/. Es la prueba de que añadir una tarea es un dato del registro.

Construye su propia App (con skip si no hay Tk); no usa la fixture `app` porque
necesita un registro distinto del real."""
from __future__ import annotations

import tkinter as tk

import pytest

pytestmark = pytest.mark.gui


def _registro_demo():
    from gui.pestana_base import PestanaBase
    from core.registro import Categoria, DescriptorTarea, Registro

    class PestanaProductora(PestanaBase):
        nombre = "Productora"
        produce = "demo_art"

    class PestanaConsumidora(PestanaBase):
        nombre = "Consumidora"
        consume = "demo_art"

    reg = Registro([
        Categoria("Demo", "Tareas de prueba.",
                  (DescriptorTarea("prod", "Productora", PestanaProductora,
                                   produce="demo_art"),
                   DescriptorTarea("cons", "Consumidora", PestanaConsumidora,
                                   consume="demo_art"))),
    ])
    return reg, PestanaProductora, PestanaConsumidora


def test_app_es_registro_driven(app):
    """SIEMPRE corre (sobre el app de sesión): las pestañas de App son EXACTAMENTE
    las clases del registro, en orden. App no tiene ninguna tarea cableada; añadir
    una tarea al registro basta para que aparezca."""
    esperado = [d.clase for d in app.registro.descriptores()]
    real = [type(p) for p in app.pestanas]
    assert real == esperado


def test_app_con_registro_ficticio(tmp_path):
    # Arranca una App SEPARADA con tareas ficticias. En este entorno Tkinter no
    # admite dos roots vivos a la vez (choca con el root de la sesión), así que se
    # SALTA si Tcl falla; en aislamiento corre y valida el arranque + handoff.
    from gui.app import App
    reg, Prod, Cons = _registro_demo()
    try:
        a = App(reg)
    except tk.TclError as e:
        pytest.skip(f"Tkinter no disponible: {e}")
    a.withdraw()
    a.update_idletasks()
    try:
        # Las tareas ficticias quedan registradas (se instancian perezosamente al
        # mostrarlas, no al arrancar; ver Fase 9).
        assert [c.nombre for c in a._clases] == ["Productora", "Consumidora"]
        assert [c.nombre for c in a.registro.categorias] == ["Demo"]

        # Navegación por clase.
        a.mostrar(Cons)
        assert a._tarea_actual is a.pestana(Cons)

        # Handoff por artefacto, sin ninguna referencia cruzada de clase.
        f = tmp_path / "x.dat"
        f.write_text("x")
        receptora = a.sugerir_entrada(str(f), "demo_art")
        assert receptora is a.pestana(Cons)
        assert receptora.v_origen.get() == str(f)
    finally:
        try:
            a.destroy()
        except tk.TclError:
            pass
