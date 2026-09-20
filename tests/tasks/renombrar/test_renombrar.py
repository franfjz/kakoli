# -*- coding: utf-8 -*-
"""Caracterización del motor Renombrar: transformación de nombre (pura) y el
motor por su contrato `ejecutar` (simular no toca el disco; conflictos)."""
from __future__ import annotations

import pytest

from tests.soporte.util import nolog, politica

import tasks.renombrar.motor as mrenom


# ---------------- transformación de nombre (pura) ----------------
def _opts(**kw):
    return mrenom.Opciones(politica=politica(), **kw)


def test_dividir_ext_simple():
    assert mrenom.dividir_ext("foto.jpg") == ("foto", ".jpg")


def test_dividir_ext_compuesta():
    assert mrenom.dividir_ext("backup.tar.gz") == ("backup", ".tar.gz")


def test_nuevo_nombre_prefijo_sufijo_conserva_extension():
    o = _opts(prefijo="a_", sufijo="_v2")
    assert mrenom.nuevo_nombre("foto.jpg", o) == "a_foto_v2.jpg"


def test_nuevo_nombre_reemplazo_interno():
    o = _opts(buscar="IMG", reemplazar="foto")
    assert mrenom.nuevo_nombre("IMG_001.jpg", o) == "foto_001.jpg"


def test_nuevo_nombre_reemplazo_insensible_mayusculas():
    o = _opts(buscar="img", reemplazar="X", sensible_mayusculas=False)
    assert mrenom.nuevo_nombre("IMG_img.png", o) == "X_X.png"


def test_nuevo_nombre_compuesta_sufijo_antes_de_extension():
    o = _opts(sufijo="_bak")
    assert mrenom.nuevo_nombre("data.tar.gz", o) == "data_bak.tar.gz"


# ---------------- motor ----------------
def test_simular_no_toca_el_disco(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    r = mrenom.ejecutar({"origen": tmp_path},
                        _opts(prefijo="p_", simular=True), log=nolog)
    assert r.estado == "completado"
    assert (tmp_path / "a.txt").exists()          # no se renombró
    assert not (tmp_path / "p_a.txt").exists()


def test_renombra_de_verdad(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    r = mrenom.ejecutar({"origen": tmp_path}, _opts(prefijo="p_"), log=nolog)
    assert r.estado == "completado"
    assert not (tmp_path / "a.txt").exists()
    assert (tmp_path / "p_a.txt").exists()


def test_conflicto_numerar(tmp_path):
    # "a.txt" y "b.txt" con sufijo "" y buscar a->x colisionarían; forzamos colisión
    # real: dos archivos que al aplicar el cambio dan el mismo nombre.
    (tmp_path / "uno.log").write_text("1")
    (tmp_path / "dos.log").write_text("2")
    # buscar 'uno'/'dos' -> 'x' hace que ambos quieran llamarse x.log
    r1 = mrenom.ejecutar({"origen": tmp_path},
                         _opts(buscar="uno", reemplazar="x"), log=nolog)
    r2 = mrenom.ejecutar({"origen": tmp_path},
                         _opts(buscar="dos", reemplazar="x", conflicto="numerar"),
                         log=nolog)
    assert r1.estado == "completado" and r2.estado == "completado"
    nombres = sorted(p.name for p in tmp_path.iterdir())
    assert "x.log" in nombres
    assert "x_2.log" in nombres                    # el segundo se numeró


def test_conflicto_omitir(tmp_path):
    (tmp_path / "x.log").write_text("1")
    (tmp_path / "dos.log").write_text("2")
    r = mrenom.ejecutar({"origen": tmp_path},
                        _opts(buscar="dos", reemplazar="x", conflicto="omitir"),
                        log=nolog)
    # El único candidato se omite por conflicto: 0 renombrados y no simular -> "nada".
    assert r.estado == "nada"
    assert (tmp_path / "dos.log").exists()         # se omitió (no se renombró)


def test_sin_operacion_devuelve_nada(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    r = mrenom.ejecutar({"origen": tmp_path}, _opts(), log=nolog)
    assert r.estado == "nada"


def test_rutas_validadas_carpeta_inexistente(tmp_path):
    with pytest.raises(ValueError):
        mrenom.rutas_validadas(tmp_path / "no_existe")
