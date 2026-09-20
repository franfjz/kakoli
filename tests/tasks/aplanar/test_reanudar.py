# -*- coding: utf-8 -*-
"""Reanudación de Aplanar con caché de árbol (core.cache_arbol): tras una pausa, la
reanudación carga el árbol del caché en vez de volver a recorrer el origen."""
from __future__ import annotations

from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.aplanar.motor as maplanar


def _seq():
    return maplanar.Opciones(politica=politica(hilos=1))


def test_reanudado_no_vuelve_a_explorar(tmp_path, monkeypatch):
    origen = arboles.crear_arbol(tmp_path / "origen", semilla=1, dirs=2,
                                 archivos_por_dir=2, profundidad=1, vacios=False)
    destino = tmp_path / "plano"

    veces = {"n": 0}

    def pausar():
        veces["n"] += 1
        return veces["n"] > 1                 # deja pasar 1 archivo, luego pausa

    r = maplanar.procesar(origen, destino, _seq(), log=nolog, pausar=pausar)
    assert r.estado == "pausado"
    assert r.procesadas >= 1 and r.restantes >= 1
    assert (destino / maplanar.ARBOL_NOMBRE).exists()      # árbol cacheado

    llamadas = {"n": 0}
    original = maplanar._walk_rel

    def contador(*a, **kw):
        llamadas["n"] += 1
        return original(*a, **kw)

    monkeypatch.setattr(maplanar, "_walk_rel", contador)

    r2 = maplanar.procesar(origen, destino, _seq(), log=nolog)
    assert r2.estado == "completado"
    assert llamadas["n"] == 0                  # se cargó del caché, no se re-exploró
    assert not (destino / maplanar.ARBOL_NOMBRE).exists()  # al completar se borra


def test_reiniciar_descarta_la_cache(tmp_path):
    origen = arboles.crear_arbol(tmp_path / "origen", semilla=2, dirs=2,
                                 archivos_por_dir=2, profundidad=1, vacios=False)
    destino = tmp_path / "plano"

    maplanar.procesar(origen, destino, _seq(), log=nolog, pausar=lambda: True)
    # (pausa antes del primer archivo, pero el árbol ya se cacheó)
    assert (destino / maplanar.ARBOL_NOMBRE).exists()

    opts = maplanar.Opciones(politica=politica(hilos=1), reiniciar=True)
    r2 = maplanar.procesar(origen, destino, opts, log=nolog)
    assert r2.estado == "completado"
