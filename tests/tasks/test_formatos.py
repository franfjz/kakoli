# -*- coding: utf-8 -*-
"""Caracterización de los formatos compartidos entre gemelas:
nombres_aplanado (códec + anti path-traversal), formato_zip (marca) e
indice_combinacion (E/S del índice)."""
from __future__ import annotations

import zipfile



import tasks.formatos.nombres_aplanado as nombres
import tasks.formatos.formato_zip as fzip
import tasks.formatos.indice_combinacion as findice


# ---------------- nombres_aplanado ----------------
def test_separador_ok():
    assert nombres.separador_ok("-") == ""
    assert nombres.separador_ok("") != ""
    assert nombres.separador_ok("a/b") != ""
    assert nombres.separador_ok("a\\b") != ""


def test_aplanar_nombre():
    assert nombres.aplanar_nombre("n1/n2/a.txt", "-") == "n1-n2-a.txt"
    assert nombres.aplanar_nombre("a.txt", "-") == "a.txt"


def test_desaplanar_nombre_reconstruye_ruta():
    assert nombres.desaplanar_nombre("n1-n2-a.txt", "-") == "n1/n2/a.txt"


def test_desaplanar_nombre_sin_separador_queda_en_raiz():
    assert nombres.desaplanar_nombre("a.txt", "-") == "a.txt"


def test_desaplanar_nombre_ambiguedad_del_separador():
    # Un nombre real con el separador se interpreta como carpeta (documentado).
    assert nombres.desaplanar_nombre("mi-informe.txt", "-") == "mi/informe.txt"


def test_desaplanar_nombre_anti_traversal():
    # Segmentos de carpeta con '..' se sanean; nunca escapan del destino.
    salida = nombres.desaplanar_nombre("..-..-secreto.txt", "-")
    assert ".." not in salida.split("/")


def test_aplanar_desaplanar_son_inversos_sin_separador_en_nombres():
    for rel in ["a.txt", "n1/a.txt", "n1/n2/n3/a.txt"]:
        plano = nombres.aplanar_nombre(rel, "-")
        assert nombres.desaplanar_nombre(plano, "-") == rel


# ---------------- formato_zip ----------------
def test_leer_marca_de_no_zip_es_none(tmp_path):
    f = tmp_path / "no_es_zip.txt"
    f.write_text("hola")
    assert fzip.leer_marca(f) is None


def test_leer_marca_zip_sin_marca_es_none(tmp_path):
    z = tmp_path / "normal.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("dentro.txt", "x")
    assert fzip.leer_marca(z) is None


def test_leer_marca_zip_con_marca(tmp_path):
    import json
    z = tmp_path / "carpeta.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("dentro.txt", "x")
        zf.comment = json.dumps(
            {"formato": fzip.MARCA_FORMATO, "carpeta": "mi_carpeta"}).encode("utf-8")
    marca = fzip.leer_marca(z)
    assert marca is not None and marca["carpeta"] == "mi_carpeta"


# ---------------- indice_combinacion ----------------
def test_indice_round_trip(tmp_path):
    indice = {"formato": findice.INDICE_FORMATO, "archivos": {"a.txt": {"x": 1}}}
    findice.guardar_indice(tmp_path, indice)
    assert (tmp_path / findice.INDICE_NOMBRE).exists()
    leido = findice.cargar_indice(tmp_path)
    assert leido == indice


def test_indice_ausente_es_none(tmp_path):
    assert findice.cargar_indice(tmp_path) is None


def test_indice_formato_invalido_es_none(tmp_path):
    (tmp_path / findice.INDICE_NOMBRE).write_text('{"formato": "otro/9"}',
                                                  encoding="utf-8")
    assert findice.cargar_indice(tmp_path) is None
