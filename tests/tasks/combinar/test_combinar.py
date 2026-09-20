# -*- coding: utf-8 -*-
"""Caracterización del motor Combinar (validación) y del motor Aplanar (validación
+ modos). El round-trip completo vive en tests/tasks/pares/."""
from __future__ import annotations

import pytest

from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.combinar.motor as mcombi


def test_rutas_validadas_fuente_inexistente(tmp_path):
    principal = tmp_path / "principal"
    with pytest.raises(ValueError):
        mcombi.rutas_validadas(principal, [tmp_path / "no_existe"])


def test_rutas_validadas_sin_fuentes(tmp_path):
    with pytest.raises(ValueError):
        mcombi.rutas_validadas(tmp_path / "principal", [])


def test_rutas_validadas_contencion_mutua(tmp_path):
    principal = arboles.crear_arbol(tmp_path / "p", semilla=1, dirs=1,
                                    archivos_por_dir=1, profundidad=0)
    dentro = principal / "sub"
    dentro.mkdir()
    with pytest.raises(ValueError):
        mcombi.rutas_validadas(principal, [dentro])


def test_combina_crea_indice(tmp_path):
    a = arboles.crear_arbol(tmp_path / "a", semilla=2, dirs=1,
                            archivos_por_dir=2, profundidad=0)
    principal = tmp_path / "principal"
    p, fs = mcombi.rutas_validadas(principal, [a])
    r = mcombi.ejecutar({"principal": p, "fuentes": fs},
                        mcombi.Opciones(politica=politica()), log=nolog)
    assert r.estado == "completado"
    from tasks.formatos import indice_combinacion as findice
    assert (p / findice.INDICE_NOMBRE).exists()
