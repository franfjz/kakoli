# -*- coding: utf-8 -*-
"""Soporte opcional de arrastrar y soltar (gui/dnd.py). El parser de rutas y el
filtro a directorios NO dependen de tkinterdnd2 (solo del intérprete Tk), así que
se prueban siempre; la presencia de la zona en la pestaña se prueba solo si el
soporte está disponible."""
from __future__ import annotations

import pytest

from gui import dnd

pytestmark = pytest.mark.gui


def test_soporta_dnd_devuelve_bool(app):
    assert isinstance(dnd.soporta_dnd(), bool)


def test_parsear_rutas_vacio(app):
    assert dnd.parsear_rutas(app, "") == []


def test_parsear_rutas_con_espacios_entre_llaves(app):
    # Como envía tkdnd un <<Drop>> real: cada ruta entre llaves (los backslashes
    # dentro de {} son literales; las rutas con espacios no se parten).
    data = "{C:\\Users\\yo\\Mis Fotos} {D:\\a} {D:\\dos palabras\\x}"
    assert dnd.parsear_rutas(app, data) == [
        "C:\\Users\\yo\\Mis Fotos", "D:\\a", "D:\\dos palabras\\x"]


def test_solo_directorios_filtra_lo_inexistente(app, tmp_path):
    d1 = tmp_path / "uno"
    d1.mkdir()
    archivo = tmp_path / "f.txt"
    archivo.write_text("x", encoding="utf-8")
    rutas = [str(d1), str(archivo), str(tmp_path / "no_existe")]
    assert dnd.solo_directorios(rutas) == [str(d1)]


@pytest.mark.skipif(not dnd.soporta_dnd(), reason="tkinterdnd2 no instalado")
def test_zona_presente_en_campo_lista(app):
    from tasks.combinar.pestana import PestanaCombinar
    pes = app.pestana(PestanaCombinar)
    txt = pes._widgets_lista["mas"]
    cont = txt.master.master            # cont > (izq | caja); la zona vive en izq
    zonas = [w for w in _descendientes(cont)
             if w.winfo_class() == "Label" and "Arrastra" in str(w.cget("text"))]
    assert zonas, "falta la zona de soltar en la columna izquierda"


def _descendientes(w):
    for h in w.winfo_children():
        yield h
        yield from _descendientes(h)


def test_soltar_reutiliza_dedup(app, tmp_path):
    # El 'soltar' comparte el mismo _anexar_rutas que 'Examinar': ignora duplicados.
    from tasks.combinar.pestana import PestanaCombinar
    pes = app.pestana(PestanaCombinar)
    txt = pes._widgets_lista["mas"]
    txt.delete("1.0", "end")
    d = str(tmp_path)
    assert pes._anexar_rutas(txt, [d, d]) == 1     # intra-lote
    assert pes._anexar_rutas(txt, [d]) == 0        # ya estaba
    assert pes.valores_lista("mas") == [d]
