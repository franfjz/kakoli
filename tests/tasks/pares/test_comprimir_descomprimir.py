# -*- coding: utf-8 -*-
"""Par Comprimir <-> Descomprimir: Descomprimir(Comprimir(árbol)) == árbol.

Verifica la identidad (nombres + bytes + carpetas vacías) por la firma completa,
en varias configuraciones (normal, compacto, paralelo forzado y reanudación).
Usa SOLO la API pública de cada motor (sin imports cruzados entre tareas)."""
from __future__ import annotations

import pytest

from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.comprimir.motor as mcomp
import tasks.descomprimir.motor as mdesc


def _round_trip(tmp_path, opts_comp, *, semilla=1):
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=semilla, dirs=3,
                               archivos_por_dir=3, profundidad=2, vacios=True)
    salida = tmp_path / "zips"
    rc = mcomp.ejecutar({"origen": raiz, "destino": salida}, opts_comp, log=nolog)
    assert rc.estado == "completado", rc.mensaje
    zip_final = rc.ruta_final

    destino = tmp_path / "out"
    rd = mdesc.ejecutar({"origen": zip_final, "destino": destino},
                        mdesc.Opciones(politica=politica()), log=nolog)
    assert rd.estado == "completado", rd.mensaje
    reconstruido = rd.ruta_final
    return raiz, reconstruido


def test_round_trip_normal(tmp_path):
    raiz, recon = _round_trip(tmp_path, mcomp.Opciones(politica=politica()))
    assert arboles.comparar(raiz, recon) == []


def test_round_trip_compacto(tmp_path):
    opts = mcomp.Opciones(politica=politica())
    mcomp.aplicar_modo_compacto(opts)
    raiz, recon = _round_trip(tmp_path, opts, semilla=7)
    assert arboles.comparar(raiz, recon) == []


@pytest.mark.lento
def test_round_trip_paralelo_forzado(tmp_path):
    # Fuerza 4 hilos: el resultado debe ser idéntico al secuencial.
    opts = mcomp.Opciones(politica=politica(hilos=4))
    raiz, recon = _round_trip(tmp_path, opts, semilla=9)
    assert arboles.comparar(raiz, recon) == []


def test_reanudacion_por_max_dirs(tmp_path):
    """Comprimir con max_dirs=1 pausa; relanzar completa; el round-trip sigue OK."""
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=3, dirs=2,
                               archivos_por_dir=2, profundidad=1, vacios=True)
    salida = tmp_path / "zips"

    r1 = mcomp.ejecutar({"origen": raiz, "destino": salida},
                        mcomp.Opciones(politica=politica(), max_dirs=1), log=nolog)
    assert r1.estado == "pausado" and r1.restantes > 0

    r2 = mcomp.ejecutar({"origen": raiz, "destino": salida},
                        mcomp.Opciones(politica=politica()), log=nolog)
    assert r2.estado == "completado"

    destino = tmp_path / "out"
    rd = mdesc.ejecutar({"origen": r2.ruta_final, "destino": destino},
                        mdesc.Opciones(politica=politica()), log=nolog)
    assert arboles.comparar(raiz, rd.ruta_final) == []
