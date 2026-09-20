# -*- coding: utf-8 -*-
"""Módulo de preferencias (Fase 2): cargar/guardar un dict en JSON, robusto ante
fichero ausente, corrupto o de tipo inesperado. No necesita Tkinter (no lleva el
marcador `gui`): opera sobre rutas explícitas en `tmp_path`."""
from __future__ import annotations

from gui import preferencias


def test_roundtrip(tmp_path):
    ruta = tmp_path / "config.json"
    datos = {"hilos": "2", "ligero": False, "abierto": "comprimir",
             "ultimas": {"Compresión": "comprimir"}}
    assert preferencias.guardar(datos, ruta) is True
    assert preferencias.cargar(ruta) == datos


def test_crea_directorio_padre(tmp_path):
    ruta = tmp_path / "sub" / "carpeta" / "config.json"
    assert preferencias.guardar({"x": 1}, ruta) is True
    assert ruta.exists()


def test_fichero_ausente_devuelve_vacio(tmp_path):
    assert preferencias.cargar(tmp_path / "no_existe.json") == {}


def test_json_corrupto_devuelve_vacio(tmp_path):
    ruta = tmp_path / "config.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    assert preferencias.cargar(ruta) == {}


def test_json_no_dict_devuelve_vacio(tmp_path):
    ruta = tmp_path / "config.json"
    ruta.write_text("[1, 2, 3]", encoding="utf-8")     # JSON válido, pero no un dict
    assert preferencias.cargar(ruta) == {}
