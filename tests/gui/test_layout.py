# -*- coding: utf-8 -*-
"""Divisor ajustable navegador/monitor (Fase 7): PanedWindow de dos paneles y la
restauración/guardado de la posición del sash. La ventana de test está oculta (sin
tamaño real), así que se parchean `winfo_width`/`sashpos`."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_paned_tiene_dos_paneles(app):
    assert len(app._paned.panes()) == 2


def test_restaurar_sash_usa_el_ancho_guardado(app, monkeypatch):
    registrado = []
    monkeypatch.setattr(app._paned, "winfo_width", lambda: 1000)
    monkeypatch.setattr(app._paned, "sashpos",
                        lambda i, x=None: registrado.append(x))
    monkeypatch.setattr(app, "_monitor_min_px", lambda: 280)
    app._prefs["monitor_ancho"] = 300          # >= mínimo y cabe: se respeta
    app._sash_restaurado = False
    app._restaurar_sash()
    assert registrado == [700]                 # 1000 - 300
    assert app._sash_restaurado is True


def test_restaurar_sash_respeta_el_minimo_del_panel(app, monkeypatch):
    registrado = []
    monkeypatch.setattr(app._paned, "winfo_width", lambda: 1000)
    monkeypatch.setattr(app._paned, "sashpos",
                        lambda i, x=None: registrado.append(x))
    monkeypatch.setattr(app, "_monitor_min_px", lambda: 320)
    app._prefs["monitor_ancho"] = 200          # por debajo del mínimo -> se sube a 320
    app._sash_restaurado = False
    app._restaurar_sash()
    assert registrado == [680]                 # 1000 - 320


def test_restaurar_sash_espera_a_tener_tamano(app, monkeypatch):
    monkeypatch.setattr(app._paned, "winfo_width", lambda: 1)
    app._sash_restaurado = False
    app._restaurar_sash()
    assert app._sash_restaurado is False       # aún sin tamaño real: no fija nada


def test_restaurar_sash_limita_monitor_enorme(app, monkeypatch):
    registrado = []
    monkeypatch.setattr(app._paned, "winfo_width", lambda: 1000)
    monkeypatch.setattr(app._paned, "sashpos",
                        lambda i, x=None: registrado.append(x))
    monkeypatch.setattr(app, "_monitor_min_px", lambda: 280)
    app._prefs["monitor_ancho"] = 5000         # no debe ahogar la tarea
    app._sash_restaurado = False
    app._restaurar_sash()
    # El navegador conserva al menos _IZQ_MIN (300): el sash no pasa de ahí.
    assert registrado == [app._IZQ_MIN]


def test_clamp_sash_respeta_ambos_minimos(app, monkeypatch):
    registrado = []
    pos = {"v": 0}
    monkeypatch.setattr(app._paned, "winfo_width", lambda: 1000)

    def _sashpos(i, x=None):
        if x is None:
            return pos["v"]
        pos["v"] = x
        registrado.append(x)
    monkeypatch.setattr(app._paned, "sashpos", _sashpos)
    monkeypatch.setattr(app, "_monitor_min_px", lambda: 300)
    # Arrastre extremo a la derecha: el monitor no baja de su mínimo (sash <= 700).
    pos["v"] = 980
    app._clamp_sash()
    assert pos["v"] == 700
    # Arrastre extremo a la izquierda: el navegador no baja de _IZQ_MIN.
    pos["v"] = 10
    app._clamp_sash()
    assert pos["v"] == app._IZQ_MIN


def test_guardar_prefs_persiste_ancho_monitor(app, monkeypatch):
    monkeypatch.setattr(app._paned, "winfo_width", lambda: 1000)
    monkeypatch.setattr(app._paned, "sashpos", lambda i: 700)
    app._guardar_prefs()
    assert app._prefs["monitor_ancho"] == 300  # 1000 - 700
