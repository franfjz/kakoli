# -*- coding: utf-8 -*-
"""Acciones de la consola (Fase 5): empty state, limpiar, copiar y guardar el
registro compartido."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_empty_state_al_arrancar(app):
    # Consola vacía: muestra el texto de guía y no cuenta como contenido real.
    assert app._log_vacio is True
    assert "Aquí aparecerá" in app.texto_log.get("1.0", "end-1c")
    assert app._texto_consola() == ""


def test_primer_mensaje_retira_el_placeholder(app):
    app.escribir("hola mundo")
    assert app._log_vacio is False
    contenido = app.texto_log.get("1.0", "end-1c")
    assert "Aquí aparecerá" not in contenido
    assert "hola mundo" in contenido
    assert app._texto_consola().strip() == "hola mundo"


def test_limpiar_restaura_el_empty_state(app):
    app.escribir("una línea")
    app.limpiar_consola()
    assert app._log_vacio is True
    assert app._texto_consola() == ""
    assert "Aquí aparecerá" in app.texto_log.get("1.0", "end-1c")


def test_copiar_pone_el_registro_en_el_portapapeles(app):
    app.escribir("línea copiable")
    app.copiar_consola()
    assert "línea copiable" in app.clipboard_get()


def test_copiar_vacio_no_falla(app):
    # Sin contenido real (solo placeholder): copiar no hace nada y no lanza.
    app.limpiar_consola()
    app.copiar_consola()          # no debe lanzar


def test_guardar_escribe_el_registro(app, tmp_path, monkeypatch):
    from tkinter import filedialog
    destino = tmp_path / "registro.txt"
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda *a, **k: str(destino))
    app.escribir("línea uno")
    app.escribir("línea dos")
    app.guardar_consola()
    guardado = destino.read_text(encoding="utf-8")
    assert "línea uno" in guardado
    assert "línea dos" in guardado


def test_guardar_cancelado_no_crea_archivo(app, tmp_path, monkeypatch):
    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda *a, **k: "")
    app.escribir("algo")
    app.guardar_consola()         # usuario cancela el diálogo
    assert list(tmp_path.iterdir()) == []
