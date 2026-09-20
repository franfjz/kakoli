# -*- coding: utf-8 -*-
"""Par Aplanar <-> Desaplanar: Desaplanar(Aplanar(árbol, modo=ruta)) == árbol.

Solo el modo 'ruta' (codifica la ruta en el nombre) es reversible. Se incluyen los
casos NO reversibles como comportamiento documentado: modo 'final' y un nombre que
contiene el separador. Aplanar copia SOLO archivos (las carpetas vacías no
sobreviven), así que el árbol de prueba se crea sin carpetas vacías."""
from __future__ import annotations


from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.aplanar.motor as maplan
import tasks.desaplanar.motor as mdesaplan


def test_round_trip_modo_ruta(tmp_path):
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=1, dirs=3,
                               archivos_por_dir=3, profundidad=2, vacios=False)
    aplanada = tmp_path / "aplanada"
    ra = maplan.ejecutar({"origen": raiz, "destino": aplanada},
                         maplan.Opciones(politica=politica(), modo_nombre="ruta",
                                         separador="-"), log=nolog)
    assert ra.estado == "completado"

    recon = tmp_path / "recon"
    rd = mdesaplan.ejecutar({"origen": aplanada, "destino": recon},
                            mdesaplan.Opciones(politica=politica(), separador="-"),
                            log=nolog)
    assert rd.estado == "completado"
    assert arboles.comparar(raiz, rd.ruta_final) == []


def test_aplanada_es_un_solo_nivel(tmp_path):
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=2, dirs=2,
                               archivos_por_dir=2, profundidad=2, vacios=False)
    aplanada = tmp_path / "aplanada"
    maplan.ejecutar({"origen": raiz, "destino": aplanada},
                    maplan.Opciones(politica=politica(), modo_nombre="ruta"),
                    log=nolog)
    # Todo en la carpeta aplanada es archivo (un único nivel).
    assert all(p.is_file() for p in aplanada.iterdir())


def test_modo_final_no_es_desaplanable(tmp_path):
    # 'final' pierde la ruta: el árbol reconstruido NO coincide con el original.
    raiz = arboles.crear_arbol(tmp_path / "raiz", semilla=3, dirs=2,
                               archivos_por_dir=2, profundidad=2, vacios=False)
    aplanada = tmp_path / "aplanada"
    maplan.ejecutar({"origen": raiz, "destino": aplanada},
                    maplan.Opciones(politica=politica(), modo_nombre="final"),
                    log=nolog)
    recon = tmp_path / "recon"
    mdesaplan.ejecutar({"origen": aplanada, "destino": recon},
                       mdesaplan.Opciones(politica=politica(), separador="-"),
                       log=nolog)
    assert arboles.comparar(raiz, recon) != []


def test_separador_en_el_nombre_crea_carpeta(tmp_path):
    """Un nombre real con el separador se interpreta como carpeta al desaplanar
    (ambigüedad inherente y documentada)."""
    aplanada = tmp_path / "aplanada"
    aplanada.mkdir()
    (aplanada / "mi-informe.txt").write_text("x")
    recon = tmp_path / "recon"
    mdesaplan.ejecutar({"origen": aplanada, "destino": recon},
                       mdesaplan.Opciones(politica=politica(), separador="-"),
                       log=nolog)
    assert (recon / "mi" / "informe.txt").exists()
