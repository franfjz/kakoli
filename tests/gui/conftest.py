# -*- coding: utf-8 -*-
"""Fixtures de los tests de GUI. Requieren Tkinter (marcador `gui`): si el sistema
no tiene Tk utilizable, los tests se saltan en vez de fallar.

Se crea UNA sola ventana `App` por sesión y se REINICIA su estado antes de cada
test (navegación al menú + todas las variables Tk a sus valores por defecto). Se
hace así a propósito: crear y destruir muchos roots `Tk()` seguidos en el mismo
proceso provoca una carrera intermitente en la carga de la librería Tcl en Windows
('tcl_findLibrary' / 'winTheme.tcl'). Con un único root la construcción es estable.

Sin `mainloop`: los tests bombean `procesar_cola`/`update` a mano. `messagebox` se
sustituye para que ningún diálogo modal bloquee la suite.
"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox

import pytest


def _variables(app) -> list[tk.Variable]:
    """Todas las variables Tk de la App y de sus pestañas (atributos + campos de
    entrada), para poder capturar y restaurar sus valores por defecto."""
    vistos: dict[int, tk.Variable] = {}

    def recoger(obj):
        for v in list(vars(obj).values()):
            if isinstance(v, tk.Variable):
                vistos[id(v)] = v
        entradas = getattr(obj, "vars_entrada", None)
        if isinstance(entradas, dict):
            for v in entradas.values():
                if isinstance(v, tk.Variable):
                    vistos[id(v)] = v

    recoger(app)
    for pes in app.pestanas:
        recoger(pes)
    return list(vistos.values())


@pytest.fixture(scope="session", autouse=True)
def _config_temporal(tmp_path_factory):
    """Redirige el config.json de la GUI a un temporal durante TODA la sesión de
    tests: ninguna App (ni la de sesión ni las que crean tests como
    test_extensibilidad) lee ni escribe el config real del usuario, pero
    `preferencias.cargar/guardar` se siguen ejercitando de verdad."""
    from unittest import mock
    ruta = tmp_path_factory.mktemp("kakoli_cfg") / "config.json"
    with mock.patch("gui.preferencias.ruta_config", return_value=ruta):
        yield ruta


@pytest.fixture(scope="session")
def _app_sesion():
    from gui.app import App
    from tasks import REGISTRO
    try:
        a = App(REGISTRO)
    except tk.TclError as e:
        pytest.skip(f"Tkinter no disponible: {e}")
    a.withdraw()
    # Las pestañas se crean perezosamente (Fase 9). Para la App de sesión COMPARTIDA
    # se fuerzan todas al arrancar: así los tests que las enumeran o resetean sus
    # variables las ven todas y el estado queda limpio entre tests. La laziness real
    # se prueba con una App separada (test_lazy.py).
    for _clase in a._clases:
        a._instancia(_clase)
    a.update_idletasks()
    defaults = [(v, v.get()) for v in _variables(a)]
    try:
        yield a, defaults
    finally:
        try:
            a.destroy()
        except tk.TclError:
            pass


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    """Neutraliza los diálogos modales (defensa: ningún test debe abrir uno)."""
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(messagebox, "askyesnocancel", lambda *a, **k: False)
    # Diálogo propio de reanudación: por defecto «continuar» (False), sin bloquear.
    from gui import componentes
    monkeypatch.setattr(componentes, "dialogo_reanudar", lambda *a, **k: False)


@pytest.fixture
def app(_app_sesion):
    a, defaults = _app_sesion
    # Estado limpio ANTES de cada test.
    a._bloqueado = False
    # Bomba en reposo (Fase 1): sin timer colgado de un test anterior.
    if getattr(a, "_id_bomba", None) is not None:
        try:
            a.after_cancel(a._id_bomba)
        except Exception:
            pass
        a._id_bomba = None
    for var, valor in defaults:
        var.set(valor)
    a._ultima_tarea.clear()          # navegación limpia entre tests
    a._prefs.clear()                 # preferencias limpias entre tests
    a.limpiar_consola()              # consola compartida limpia entre tests
    for pes in a.pestanas:
        pes.auto_destino = True
        pes._reanudando_en_sesion = False
        if hasattr(pes, "_simular_flag"):
            pes._simular_flag = False
        for txt in getattr(pes, "_widgets_lista", {}).values():
            txt.delete("1.0", "end")
    a._ir_menu()
    a.update_idletasks()
    return a


def bombear(app, pes, *, intentos: int = 300, pausa: float = 0.01) -> None:
    """Hace avanzar el bucle a mano hasta que la pestaña deja de estar ocupada
    (sin mainloop): actualiza la ventana y vacía la cola del hilo de trabajo."""
    if pes.hilo is not None:
        pes.hilo.join(timeout=intentos * pausa)
    for _ in range(intentos):
        app.update()
        pes.procesar_cola()
        if not pes.ocupada():
            break
        time.sleep(pausa)
    pes.procesar_cola()
