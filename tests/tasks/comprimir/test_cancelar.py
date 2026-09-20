# -*- coding: utf-8 -*-
"""Cancelación de Comprimir (Fase 3 mejoras): abortar la carpeta en curso descartando
su fragmento (.part) y dejar el progreso en la última carpeta completada; reanudable."""
from __future__ import annotations

import pytest

from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.comprimir.motor as mcomp


def _seq():
    """Opciones deterministas y en un solo hilo (camino secuencial)."""
    return mcomp.Opciones(politica=politica(hilos=1))


def test_crear_cancelado_borra_el_fragmento(tmp_path):
    """Comprimidor.crear con cancelar()=True aborta la carpeta EN CURSO: lanza
    Cancelado y no deja ni el ZIP final ni el .part a medias."""
    raiz = arboles.crear_arbol(tmp_path / "datos", semilla=3, dirs=2,
                               archivos_por_dir=3, profundidad=1)
    salida = tmp_path / "zips"
    salida.mkdir()
    infos, orden = mcomp.explorar(raiz, False, False, log=nolog)
    rel = next(r for r in orden if infos[r].archivos)   # una carpeta con archivos
    comp = mcomp.Comprimidor(raiz, salida, _seq(), log=nolog)
    destino = comp.destino(rel)
    parcial = destino.with_name(destino.name + ".part")

    with pytest.raises(mcomp.Cancelado):
        comp.crear(rel, infos[rel], cancelar=lambda: True)

    assert not destino.exists()          # el ZIP no llegó a crearse
    assert not parcial.exists()          # el fragmento a medias se descartó


def test_procesar_cancelado_es_reanudable(tmp_path):
    """Cancelar tras completar una carpeta: la ya hecha se conserva, el resultado es
    'cancelado' y relanzar sin cancelar completa el ZIP final."""
    raiz = arboles.crear_arbol(tmp_path / "datos", semilla=4, dirs=3,
                               archivos_por_dir=2, profundidad=1)
    salida = tmp_path / "zips"

    prog = {"done": 0}

    def progreso(h, t, f, e):
        prog["done"] = h

    def cancelar():
        return prog["done"] >= 1         # cancela en cuanto una carpeta está hecha

    r = mcomp.procesar(raiz, salida, _seq(), log=nolog, progreso=progreso,
                       cancelar=cancelar)
    assert r.estado == "cancelado"
    assert r.procesadas >= 1 and r.restantes >= 1
    assert (salida / mcomp.ESTADO_NOMBRE).exists()      # progreso persistido
    assert not (salida / f"{raiz.name}.zip").exists()   # aún no está el ZIP final

    # Relanzar SIN cancelar continúa desde el punto guardado y completa.
    r2 = mcomp.procesar(raiz, salida, _seq(), log=nolog)
    assert r2.estado == "completado"
    assert (salida / f"{raiz.name}.zip").exists()


def test_procesar_reanudado_no_vuelve_a_explorar(tmp_path, monkeypatch):
    """Tras cancelar, la reanudación carga el árbol desde el caché que dejó el primer
    explorar() (mejora: evita recorrer el disco entero otra vez)."""
    raiz = arboles.crear_arbol(tmp_path / "datos", semilla=5, dirs=3,
                               archivos_por_dir=2, profundidad=1)
    salida = tmp_path / "zips"

    prog = {"done": 0}

    def progreso(h, t, f, e):
        prog["done"] = h

    def cancelar():
        return prog["done"] >= 1

    r = mcomp.procesar(raiz, salida, _seq(), log=nolog, progreso=progreso,
                       cancelar=cancelar)
    assert r.estado == "cancelado"
    assert (salida / mcomp.ARBOL_NOMBRE).exists()      # árbol cacheado

    llamadas = {"n": 0}
    original = mcomp.explorar

    def contador(*a, **kw):
        llamadas["n"] += 1
        return original(*a, **kw)

    monkeypatch.setattr(mcomp, "explorar", contador)

    r2 = mcomp.procesar(raiz, salida, _seq(), log=nolog)
    assert r2.estado == "completado"
    assert llamadas["n"] == 0          # se cargó del caché, no se volvió a explorar


def test_procesar_reiniciar_descarta_el_arbol_cacheado(tmp_path):
    """--reiniciar borra también el caché del árbol, no solo el progreso."""
    raiz = arboles.crear_arbol(tmp_path / "datos", semilla=6, dirs=2,
                               archivos_por_dir=2, profundidad=1)
    salida = tmp_path / "zips"

    mcomp.procesar(raiz, salida, _seq(), log=nolog, cancelar=lambda: True)
    assert (salida / mcomp.ARBOL_NOMBRE).exists()

    r2 = mcomp.procesar(raiz, salida, mcomp.Opciones(politica=politica(hilos=1),
                                                     reiniciar=True), log=nolog)
    assert r2.estado == "completado"
