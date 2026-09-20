# -*- coding: utf-8 -*-
"""Caracterización del motor Eliminar: borrado real, simulación (no borra),
guardas de seguridad de `rutas_validadas` y confirmación."""
from __future__ import annotations

import pytest

from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.eliminar.motor as melim


def _opts(**kw):
    return melim.Opciones(politica=politica(), **kw)


def test_borra_de_verdad(tmp_path):
    objetivo = arboles.crear_arbol(tmp_path / "victima", semilla=1, dirs=2,
                                   archivos_por_dir=2, profundidad=1)
    r = melim.ejecutar({"origen": objetivo}, _opts(), log=nolog)
    assert r.estado == "completado"
    assert not objetivo.exists()


def test_simular_no_borra_nada(tmp_path):
    objetivo = arboles.crear_arbol(tmp_path / "intacta", semilla=2, dirs=2,
                                   archivos_por_dir=2, profundidad=1)
    firma_antes = arboles.firmar(objetivo)
    r = melim.ejecutar({"origen": objetivo}, _opts(simular=True), log=nolog)
    assert r.estado == "completado"
    assert objetivo.exists()
    assert arboles.firmar(objetivo) == firma_antes    # intacta


def test_confirmar_negativo_cancela(tmp_path):
    objetivo = arboles.crear_arbol(tmp_path / "salvada", semilla=3, dirs=1,
                                   archivos_por_dir=1, profundidad=0)
    r = melim.ejecutar({"origen": objetivo}, _opts(),
                       log=nolog, confirmar=lambda *_a: False)
    assert r.estado == "cancelado"
    assert objetivo.exists()                          # no se borró nada


def test_confirmar_positivo_borra(tmp_path):
    objetivo = arboles.crear_arbol(tmp_path / "condenada", semilla=4, dirs=1,
                                   archivos_por_dir=1, profundidad=0)
    r = melim.ejecutar({"origen": objetivo}, _opts(),
                       log=nolog, confirmar=lambda *_a: True)
    assert r.estado == "completado"
    assert not objetivo.exists()


# --- guardas de seguridad de rutas_validadas ---
def test_rechaza_inexistente(tmp_path):
    with pytest.raises(ValueError):
        melim.rutas_validadas(tmp_path / "fantasma")


def test_rechaza_archivo(tmp_path):
    f = tmp_path / "soy_un_archivo.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        melim.rutas_validadas(f)


def test_rechaza_carpeta_personal():
    from pathlib import Path
    with pytest.raises(ValueError):
        melim.rutas_validadas(Path.home())
