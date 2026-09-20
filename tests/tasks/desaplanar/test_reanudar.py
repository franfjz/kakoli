# -*- coding: utf-8 -*-
"""Reanudación de Desaplanar con caché de árbol (core.cache_arbol): tras una pausa, la
reanudación carga el árbol del caché en vez de volver a recorrer la carpeta aplanada."""
from __future__ import annotations

from tests.soporte.util import nolog, politica

import tasks.aplanar.motor as maplanar
import tasks.desaplanar.motor as mdes


def _crear_aplanada(origen_arbol, plano):
    """Aplana un arbolito para tener una carpeta aplanada real que desaplanar."""
    from tests.soporte import arboles
    origen = arboles.crear_arbol(origen_arbol, semilla=7, dirs=2, archivos_por_dir=2,
                                 profundidad=1, vacios=False)
    r = maplanar.procesar(origen, plano, maplanar.Opciones(politica=politica(hilos=1)),
                          log=nolog)
    assert r.estado == "completado"
    return plano


def _seq():
    return mdes.Opciones(politica=politica(hilos=1))


def test_reanudado_no_vuelve_a_explorar(tmp_path, monkeypatch):
    plano = _crear_aplanada(tmp_path / "origen", tmp_path / "plano")
    destino = tmp_path / "reconstruido"

    veces = {"n": 0}

    def pausar():
        veces["n"] += 1
        return veces["n"] > 1                 # deja pasar 1 archivo, luego pausa

    r = mdes.procesar(plano, destino, _seq(), log=nolog, pausar=pausar)
    assert r.estado == "pausado"
    assert r.procesadas >= 1 and r.restantes >= 1
    assert (destino / mdes.ARBOL_NOMBRE).exists()          # árbol cacheado

    llamadas = {"n": 0}
    original = mdes._walk_archivos

    def contador(*a, **kw):
        llamadas["n"] += 1
        return original(*a, **kw)

    monkeypatch.setattr(mdes, "_walk_archivos", contador)

    r2 = mdes.procesar(plano, destino, _seq(), log=nolog)
    assert r2.estado == "completado"
    assert llamadas["n"] == 0                  # se cargó del caché, no se re-exploró
    assert not (destino / mdes.ARBOL_NOMBRE).exists()      # al completar se borra
