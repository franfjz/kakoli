# -*- coding: utf-8 -*-
"""Handoff entre gemelas por TIPO DE ARTEFACTO (Fase 5): cada tarea declara
`produce`/`consume` y el Registro los casa; `sugerir_entrada` rellena el origen de
la pestaña consumidora. Ya no hay `produce_hacia` ni destino explícito."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_produce_consume_declarados(app):
    from tasks.comprimir.pestana import PestanaComprimir
    from tasks.descomprimir.pestana import PestanaDescomprimir
    from tasks.combinar.pestana import PestanaCombinar
    from tasks.descombinar.pestana import PestanaDescombinar
    from tasks.aplanar.pestana import PestanaAplanar
    from tasks.desaplanar.pestana import PestanaDesaplanar

    assert PestanaComprimir.produce == "zip_anidado"
    assert PestanaDescomprimir.consume == "zip_anidado"
    assert PestanaCombinar.produce == "carpeta_combinada"
    assert PestanaDescombinar.consume == "carpeta_combinada"
    assert PestanaAplanar.produce == "carpeta_aplanada"
    assert PestanaDesaplanar.consume == "carpeta_aplanada"
    # Ya no existe el cableado por clase.
    assert not hasattr(PestanaComprimir, "produce_hacia")


def test_sugerir_entrada_casa_por_artefacto(app, tmp_path):
    from tasks.comprimir.pestana import PestanaComprimir
    from tasks.descomprimir.pestana import PestanaDescomprimir
    z = tmp_path / "resultado.zip"
    z.write_text("x")
    receptora = app.sugerir_entrada(str(z), "zip_anidado",
                                    excepto=app.pestana(PestanaComprimir))
    assert receptora is app.pestana(PestanaDescomprimir)
    assert receptora.v_origen.get() == str(z)


def test_sugerir_entrada_artefacto_sin_consumidor(app, tmp_path):
    # Un artefacto que nadie consume no se entrega a ninguna pestaña.
    assert app.sugerir_entrada(str(tmp_path), "artefacto_inexistente") is None


def test_sugerir_entrada_carpeta_aplanada(app, tmp_path):
    from tasks.desaplanar.pestana import PestanaDesaplanar
    carpeta = tmp_path / "aplanada"
    carpeta.mkdir()
    receptora = app.sugerir_entrada(str(carpeta), "carpeta_aplanada")
    assert receptora is app.pestana(PestanaDesaplanar)
    assert receptora.v_origen.get() == str(carpeta)
