# -*- coding: utf-8 -*-
"""Caracterización del motor Comprimir: validación de rutas, exploración del árbol
y marca del ZIP final."""
from __future__ import annotations


import pytest

from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.comprimir.motor as mcomp
import tasks.comprimir.explorar as mexplorar
import tasks.formatos.formato_zip as fzip


def _opts(**kw):
    return mcomp.Opciones(politica=politica(), **kw)


def test_rutas_validadas_salida_dentro_de_origen(tmp_path):
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=1, dirs=1,
                               archivos_por_dir=1, profundidad=0)
    with pytest.raises(ValueError):
        mcomp.rutas_validadas(raiz, raiz / "dentro")


def test_rutas_validadas_origen_no_carpeta(tmp_path):
    f = tmp_path / "archivo.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        mcomp.rutas_validadas(f, None)


def test_comprime_y_marca_el_zip_final(tmp_path):
    raiz = arboles.crear_arbol(tmp_path / "datos", semilla=2, dirs=2,
                               archivos_por_dir=2, profundidad=1)
    salida = tmp_path / "zips"
    r = mcomp.ejecutar({"origen": raiz, "destino": salida}, _opts(), log=nolog)
    assert r.estado == "completado"
    zip_final = salida / f"{raiz.name}.zip"
    assert zip_final.exists() and r.ruta_final == zip_final
    marca = fzip.leer_marca(zip_final)
    assert marca is not None and marca["carpeta"] == raiz.name


def test_explorar_cuenta_carpetas(tmp_path):
    raiz = arboles.crear_arbol(tmp_path / "arbol", semilla=3, dirs=2,
                               archivos_por_dir=1, profundidad=1, vacios=False)
    infos, orden = mcomp.explorar(raiz, False, False, nolog)
    # raíz + 2 subcarpetas de primer nivel = 3 carpetas.
    assert len(orden) == 3


def test_serializar_y_deserializar_arbol_es_fiel(tmp_path):
    """serializar_arbol/deserializar_arbol son inversas exactas (el JSON que va a la
    caché reconstruye el árbol de InfoDir sin pérdida)."""
    raiz = arboles.crear_arbol(tmp_path / "arbol", semilla=6, dirs=2,
                               archivos_por_dir=2, profundidad=1, vacios=False)
    infos, orden = mcomp.explorar(raiz, False, False, nolog)

    payload = mexplorar.serializar_arbol((infos, orden))
    infos2, orden2 = mexplorar.deserializar_arbol(payload)
    assert orden2 == orden
    assert set(infos2) == set(infos)
    for rel, info in infos.items():
        info2 = infos2[rel]
        assert info2.archivos == info.archivos
        assert info2.subdirs == info.subdirs
        assert info2.bytes == info.bytes
        assert info2.bytes_arbol == info.bytes_arbol
        assert info2.archivos_arbol == info.archivos_arbol
        assert info2.carpetas_arbol == info.carpetas_arbol
        assert info2.profundidad == info.profundidad
