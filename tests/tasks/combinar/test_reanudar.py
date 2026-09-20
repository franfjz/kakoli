# -*- coding: utf-8 -*-
"""Reanudación de Combinar con caché de árbol (core.cache_arbol): tras una pausa, la
reanudación carga el recorrido de las fuentes del caché en vez de re-explorarlas."""
from __future__ import annotations

from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.combinar.motor as mcomb
from tasks.formatos.indice_combinacion import ARBOL_NOMBRE


def _seq():
    return mcomb.Opciones(politica=politica(hilos=1))


def test_reanudado_no_vuelve_a_explorar(tmp_path, monkeypatch):
    principal = tmp_path / "principal"
    principal.mkdir()
    fuente = arboles.crear_arbol(tmp_path / "fuente", semilla=3, dirs=2,
                                 archivos_por_dir=2, profundidad=1, vacios=False)

    veces = {"n": 0}

    def pausar():
        veces["n"] += 1
        return veces["n"] > 1                 # deja pasar 1 archivo, luego pausa

    r = mcomb.procesar(principal, [fuente], _seq(), log=nolog, pausar=pausar)
    assert r.estado == "pausado"
    assert r.procesadas >= 1 and r.restantes >= 1
    assert (principal / ARBOL_NOMBRE).exists()             # árbol de fuentes cacheado

    llamadas = {"n": 0}
    original = mcomb._walk_rel

    def contador(*a, **kw):
        llamadas["n"] += 1
        return original(*a, **kw)

    monkeypatch.setattr(mcomb, "_walk_rel", contador)

    r2 = mcomb.procesar(principal, [fuente], _seq(), log=nolog)
    assert r2.estado == "completado"
    assert llamadas["n"] == 0                  # ni fuentes ni principal se re-exploran
    assert not (principal / ARBOL_NOMBRE).exists()         # al completar se borra


def test_sin_indice_no_deja_cache(tmp_path):
    """Con --sin-indice no hay reanudación: se explora directo, sin dejar caché."""
    principal = tmp_path / "principal"
    principal.mkdir()
    fuente = arboles.crear_arbol(tmp_path / "fuente", semilla=4, dirs=1,
                                 archivos_por_dir=2, profundidad=0, vacios=False)
    opts = mcomb.Opciones(politica=politica(hilos=1), crear_indice=False)
    r = mcomb.procesar(principal, [fuente], opts, log=nolog)
    assert r.estado == "completado"
    assert not (principal / ARBOL_NOMBRE).exists()
