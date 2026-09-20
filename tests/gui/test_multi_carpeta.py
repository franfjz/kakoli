# -*- coding: utf-8 -*-
"""Renombrar y Eliminar aceptan VARIAS carpetas (campo lista) y las procesan EN EL
ORDEN de la lista. Se ejecuta el motor real sobre carpetas temporales."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _carpeta(tmp_path, nombre, *ficheros):
    d = tmp_path / nombre
    d.mkdir()
    for f in ficheros:
        (d / f).write_text("x", encoding="utf-8")
    return d


def _poner_lista(pes, *rutas):
    txt = pes._widgets_lista["origenes"]
    txt.delete("1.0", "end")
    txt.insert("1.0", "\n".join(str(r) for r in rutas) + "\n")


def _correr(pes, datos, sondas=None):
    """Ejecuta la secuencia con callbacks inertes; devuelve el Resultado agregado."""
    lineas = sondas if sondas is not None else []
    return pes._ejecutar_en_orden(
        datos["entradas"]["origenes"], datos["opts"],
        log=lineas.append, progreso=None,
        pausar=lambda: False, cancelar=lambda: False)


def test_renombrar_varias_carpetas(app, tmp_path):
    from tasks.renombrar.pestana import PestanaRenombrar
    a = _carpeta(tmp_path, "a", "f1.txt")
    b = _carpeta(tmp_path, "b", "f2.txt")
    pes = app.pestana(PestanaRenombrar)
    _poner_lista(pes, a, b)
    pes.v_prefijo.set("p_")
    res = _correr(pes, pes._validar())
    assert res.estado == "completado"
    assert (a / "p_f1.txt").exists() and (b / "p_f2.txt").exists()   # ambas renombradas


def test_renombrar_respeta_el_orden_de_la_lista(app, tmp_path):
    from tasks.renombrar.pestana import PestanaRenombrar
    a = _carpeta(tmp_path, "a", "f.txt")
    b = _carpeta(tmp_path, "b", "f.txt")
    c = _carpeta(tmp_path, "c", "f.txt")
    pes = app.pestana(PestanaRenombrar)
    _poner_lista(pes, c, a, b)                       # orden deliberado: c, a, b
    pes.v_prefijo.set("p_")
    lineas = []
    _correr(pes, pes._validar(), lineas)
    cabeceras = [ln for ln in lineas if "=== Carpeta" in ln]
    assert "c" in cabeceras[0] and "a" in cabeceras[1] and "b" in cabeceras[2]


def test_eliminar_varias_carpetas(app, tmp_path):
    from tasks.eliminar.pestana import PestanaEliminar
    a = _carpeta(tmp_path, "a", "f1.txt")
    b = _carpeta(tmp_path, "b", "f2.txt")
    pes = app.pestana(PestanaEliminar)
    _poner_lista(pes, a, b)
    pes.v_confirmo.set(True)
    res = _correr(pes, pes._validar())
    assert res.estado == "completado"
    assert not a.exists() and not b.exists()         # ambas borradas


def test_eliminar_simular_no_borra(app, tmp_path):
    from tasks.eliminar.pestana import PestanaEliminar
    a = _carpeta(tmp_path, "a", "f1.txt")
    b = _carpeta(tmp_path, "b", "f2.txt")
    pes = app.pestana(PestanaEliminar)
    _poner_lista(pes, a, b)
    pes.v_simular.set(True)
    res = _correr(pes, pes._validar())
    assert res.estado == "completado"
    assert a.exists() and b.exists()                 # simulación: siguen ahí


def test_pausa_antes_de_empezar_detiene_la_secuencia(app, tmp_path):
    from tasks.eliminar.pestana import PestanaEliminar
    a = _carpeta(tmp_path, "a", "f.txt")
    b = _carpeta(tmp_path, "b", "f.txt")
    pes = app.pestana(PestanaEliminar)
    _poner_lista(pes, a, b)
    pes.v_simular.set(True)
    datos = pes._validar()
    res = pes._ejecutar_en_orden(
        datos["entradas"]["origenes"], datos["opts"],
        log=lambda *_: None, progreso=None,
        pausar=lambda: True, cancelar=lambda: False)     # ya en pausa
    assert res.estado == "pausado"
    assert a.exists() and b.exists()                 # no tocó ninguna
