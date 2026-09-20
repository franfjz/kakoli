# -*- coding: utf-8 -*-
"""Caracterización del motor Descomprimir: validación de rutas, detección de
contenedor y la guarda anti zip-slip (`_destino_seguro`)."""
from __future__ import annotations

import os
import zipfile

import pytest


import tasks.descomprimir.motor as mdesc


def test_rutas_validadas_no_zip(tmp_path):
    f = tmp_path / "no.zip"
    f.write_text("no soy un zip")
    with pytest.raises(ValueError):
        mdesc.rutas_validadas(f, None)


def test_rutas_validadas_inexistente(tmp_path):
    with pytest.raises(ValueError):
        mdesc.rutas_validadas(tmp_path / "no_existe.zip", None)


def test_es_contenedor_sin_marca_sin_expandir(tmp_path):
    z = tmp_path / "datos.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    es, _n = mdesc.es_contenedor(z, mdesc.Opciones())
    assert es is False                       # zip de datos, no lleva la marca


def test_es_contenedor_expandir_todos(tmp_path):
    z = tmp_path / "datos.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    es, _n = mdesc.es_contenedor(z, mdesc.Opciones(expandir_todos=True))
    assert es is True                        # con expandir_todos, cualquier zip


def test_destino_seguro_rechaza_traversal(tmp_path):
    base = str(tmp_path.resolve())
    with pytest.raises(ValueError):
        mdesc._destino_seguro(base, "../fuera.txt")


def test_destino_seguro_rechaza_absoluta(tmp_path):
    base = str(tmp_path.resolve())
    with pytest.raises(ValueError):
        mdesc._destino_seguro(base, "/etc/passwd")


def test_destino_seguro_acepta_interna(tmp_path):
    base = str(tmp_path.resolve())
    ruta = mdesc._destino_seguro(base, "sub/a.txt")
    assert str(ruta).startswith(base)


@pytest.mark.skipif(os.name != "nt", reason="ADS/':' solo aplica en Windows")
def test_destino_seguro_rechaza_dos_puntos_en_windows(tmp_path):
    base = str(tmp_path.resolve())
    with pytest.raises(ValueError):
        mdesc._destino_seguro(base, "flujo:oculto.txt")
