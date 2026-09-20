# -*- coding: utf-8 -*-
"""Arranque de la ventana: categorías, tareas y su orden; coloreado del registro
(`_tag_log`). Marcados `gui` (requieren Tkinter)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui

CATEGORIAS = ["Combinación", "Compresión", "Aplanado", "Renombrado", "Eliminar"]
TAREAS = ["Combinar", "Descombinar", "Comprimir", "Descomprimir", "Aplanar",
          "Desaplanar", "Renombrar", "Eliminar"]


def test_ocho_tareas_cinco_categorias(app):
    assert [c.nombre for c in app.registro.categorias] == CATEGORIAS
    assert [p.nombre for p in app.pestanas] == TAREAS


def test_por_clase_registra_cada_pestana(app):
    from tasks.comprimir.pestana import PestanaComprimir
    assert app.pestana(PestanaComprimir).nombre == "Comprimir"


def test_arranca_en_el_menu(app):
    # Nivel 1 (portada): sin categoría activa; la barra de tareas está oculta.
    assert app._categoria_actual is None
    assert app.estado_barra() == []


@pytest.mark.parametrize("linea, tag", [
    ("[!] cuidado", "aviso"),
    ("=== 2026 ===", "sistema"),
    ("Máquina: 8 núcleos", "sistema"),
    ("[Simulación] nada", "sistema"),
    ("Completado en 3s.", "exito"),
    ("Eliminado: carpeta", "exito"),
    ("Nada que hacer", "exito"),
    ("copiando archivo x", "normal"),
])
def test_tag_log(app, linea, tag):
    assert app._tag_log(linea) == tag
