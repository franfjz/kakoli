# -*- coding: utf-8 -*-
"""Caracterización de core.json_util: lectura/escritura atómica de un JSON, común a
cualquier tarea que necesite persistir una instantánea de datos entre ejecuciones."""
from __future__ import annotations


from core.json_util import cargar_json, guardar_json


def test_guardar_y_cargar_json(tmp_path):
    ruta = tmp_path / "datos.json"
    datos = {"orden": ["a", "b"], "infos": {"a": {"bytes": 1}}}
    guardar_json(ruta, datos)
    assert ruta.exists()
    assert cargar_json(ruta) == datos


def test_cargar_json_inexistente_devuelve_none(tmp_path):
    assert cargar_json(tmp_path / "no_existe.json") is None


def test_cargar_json_corrupto_devuelve_none(tmp_path):
    ruta = tmp_path / "roto.json"
    ruta.write_text("{no es json", encoding="utf-8")
    assert cargar_json(ruta) is None


def test_guardar_json_es_atomico_no_deja_fichero_temporal(tmp_path):
    ruta = tmp_path / "sub" / "datos.json"
    guardar_json(ruta, {"x": 1})
    assert ruta.exists()
    assert not ruta.with_name(ruta.name + ".part").exists()
