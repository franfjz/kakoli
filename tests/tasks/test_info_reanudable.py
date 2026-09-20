# -*- coding: utf-8 -*-
"""Caracterización de `info_reanudable` (gancho de detección de tarea a medias que
usa el modal de la GUI). Lo exponen Comprimir, Aplanar y Desaplanar: devuelve
None cuando no hay progreso, y {fecha, hechas} cuando quedó algo pendiente."""
from __future__ import annotations

from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.comprimir.motor as mcomp
import tasks.aplanar.motor as maplan
import tasks.desaplanar.motor as mdesaplan


def _pausa_tras(n):
    """pausar() que devuelve False las primeras `n` veces y True después."""
    cont = {"i": 0}

    def pausar():
        cont["i"] += 1
        return cont["i"] > n
    return pausar


def test_comprimir_info_reanudable_none_sin_progreso(tmp_path):
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=1, dirs=1,
                               archivos_por_dir=1, profundidad=0)
    salida = tmp_path / "zips"
    assert mcomp.info_reanudable({"origen": raiz, "destino": salida}) is None


def test_comprimir_info_reanudable_detecta_pendiente(tmp_path):
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=2, dirs=2,
                               archivos_por_dir=2, profundidad=1)
    salida = tmp_path / "zips"
    r = mcomp.ejecutar({"origen": raiz, "destino": salida},
                       mcomp.Opciones(politica=politica(), max_dirs=1), log=nolog)
    assert r.estado == "pausado"
    info = mcomp.info_reanudable({"origen": raiz, "destino": salida})
    assert info is not None and info["hechas"] >= 1


def test_aplanar_info_reanudable_none_sin_progreso(tmp_path):
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=3, dirs=1,
                               archivos_por_dir=1, profundidad=0)
    destino = tmp_path / "aplanada"
    opts = maplan.Opciones(politica=politica())
    assert maplan.info_reanudable({"origen": raiz, "destino": destino}, opts) is None


def test_aplanar_info_reanudable_detecta_pendiente(tmp_path):
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=4, dirs=3,
                               archivos_por_dir=3, profundidad=1, vacios=False)
    destino = tmp_path / "aplanada"
    opts = maplan.Opciones(politica=politica(hilos=1))
    r = maplan.ejecutar({"origen": raiz, "destino": destino}, opts,
                        log=nolog, pausar=_pausa_tras(1))
    assert r.estado == "pausado"
    info = maplan.info_reanudable({"origen": raiz, "destino": destino}, opts)
    assert info is not None and info["hechas"] >= 1


def test_desaplanar_info_reanudable_none_sin_progreso(tmp_path):
    origen = tmp_path / "aplanada"
    origen.mkdir()
    (origen / "a.txt").write_text("x")
    destino = tmp_path / "recon"
    opts = mdesaplan.Opciones(politica=politica())
    assert mdesaplan.info_reanudable({"origen": origen, "destino": destino}, opts) is None
