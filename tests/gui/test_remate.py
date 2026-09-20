# -*- coding: utf-8 -*-
"""Remate final no modal (Fase 4): al completar, "Abrir carpeta" (salvo tareas cuyo
resultado se borra, como Eliminar) y un enlace a la tarea gemela cuando el handoff
casa una consumidora. Ningún `showinfo` de fin interrumpe. Más el helper
`abrir_en_explorador`."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _res(estado, ruta=""):
    from core.resultado import Resultado
    return Resultado(estado, ruta_final=ruta, segundos=1.0)


def test_abrir_carpeta_aparece_al_completar(app, tmp_path):
    from core.resultado import EstadoResultado
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    pes._acciones_finales(_res(EstadoResultado.COMPLETADO, str(tmp_path)), None)
    assert pes.b_abrir.winfo_manager() == "pack"     # visible
    assert pes._ruta_resultado == str(tmp_path)


def test_abrir_carpeta_oculto_sin_ruta(app):
    from core.resultado import EstadoResultado
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    pes._acciones_finales(_res(EstadoResultado.COMPLETADO), None)
    assert pes.b_abrir.winfo_manager() == ""         # oculto


def test_eliminar_no_ofrece_abrir(app, tmp_path):
    from core.resultado import EstadoResultado
    from tasks.eliminar.pestana import PestanaEliminar
    pes = app.pestana(PestanaEliminar)
    assert pes.ofrece_abrir is False
    pes._acciones_finales(_res(EstadoResultado.COMPLETADO, str(tmp_path)), None)
    assert pes.b_abrir.winfo_manager() == ""


def test_handoff_muestra_y_navega_a_la_gemela(app):
    from core.resultado import EstadoResultado
    from tasks.comprimir.pestana import PestanaComprimir
    from tasks.descomprimir.pestana import PestanaDescomprimir
    pes = app.pestana(PestanaComprimir)
    receptora = app.pestana(PestanaDescomprimir)
    pes._acciones_finales(_res(EstadoResultado.COMPLETADO, "x"), receptora)
    assert pes.b_ir_gemela.winfo_manager() == "pack"
    assert "Descomprimir" in str(pes.b_ir_gemela.cget("text"))
    # El enlace navega a la gemela.
    pes.b_ir_gemela.invoke()
    assert app._tarea_actual is receptora


def test_sin_handoff_no_hay_enlace(app, tmp_path):
    from core.resultado import EstadoResultado
    from tasks.descomprimir.pestana import PestanaDescomprimir
    pes = app.pestana(PestanaDescomprimir)               # no produce artefacto
    pes._acciones_finales(_res(EstadoResultado.COMPLETADO, str(tmp_path)), None)
    assert pes.b_ir_gemela.winfo_manager() == ""


def test_abrir_en_explorador_vacio_es_false():
    from gui import componentes
    assert componentes.abrir_en_explorador("") is False


def test_abrir_en_explorador_carpeta(monkeypatch, tmp_path):
    from gui import componentes
    llamadas = []
    monkeypatch.setattr(componentes.sys, "platform", "win32")
    monkeypatch.setattr(componentes.os, "startfile",
                        lambda p: llamadas.append(p), raising=False)
    assert componentes.abrir_en_explorador(str(tmp_path)) is True
    assert llamadas == [str(tmp_path)]


def test_abrir_en_explorador_archivo_abre_su_carpeta(monkeypatch, tmp_path):
    from gui import componentes
    f = tmp_path / "a.zip"
    f.write_text("x")
    llamadas = []
    monkeypatch.setattr(componentes.sys, "platform", "win32")
    monkeypatch.setattr(componentes.os, "startfile",
                        lambda p: llamadas.append(p), raising=False)
    componentes.abrir_en_explorador(str(f))
    assert llamadas == [str(tmp_path)]                   # abre la carpeta contenedora
