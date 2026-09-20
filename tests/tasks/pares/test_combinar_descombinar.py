# -*- coding: utf-8 -*-
"""Par Combinar <-> Descombinar: Descombinar(Combinar(fuentes)) == fuentes.

Con conflicto 'renombrar' + índice, la combinación es reversible: cada directorio
de origen se reconstruye con sus nombres originales. Incluye el caso NO reversible
(sin índice) como comportamiento documentado."""
from __future__ import annotations

import pytest

from tests.soporte.util import nolog, politica
from tests.soporte import arboles

import tasks.combinar.motor as mcombi
import tasks.descombinar.motor as mdescombi


def test_round_trip_renombrar_con_indice(tmp_path):
    uno = arboles.crear_arbol(tmp_path / "uno", semilla=1, dirs=2,
                              archivos_por_dir=2, profundidad=1, vacios=False)
    dos = arboles.crear_arbol(tmp_path / "dos", semilla=2, dirs=2,
                              archivos_por_dir=2, profundidad=1, vacios=False)
    # Colisión deliberada en la raíz para ejercitar 'renombrar'.
    (uno / "colision.txt").write_bytes(b"soy de uno")
    (dos / "colision.txt").write_bytes(b"soy de dos")

    principal = tmp_path / "principal"
    p, fs = mcombi.rutas_validadas(principal, [uno, dos])
    rc = mcombi.ejecutar({"principal": p, "fuentes": fs},
                         mcombi.Opciones(politica=politica(), conflicto="renombrar"),
                         log=nolog)
    assert rc.estado == "completado"

    destino = tmp_path / "reconstruido"
    rd = mdescombi.ejecutar({"origen": p, "destino": destino},
                            mdescombi.Opciones(politica=politica()), log=nolog)
    assert rd.estado == "completado"

    # El principal estaba vacío; se reconstruyen 'uno' y 'dos' con sus nombres.
    assert arboles.comparar(uno, destino / "uno") == []
    assert arboles.comparar(dos, destino / "dos") == []


def test_sin_indice_no_es_descombinable(tmp_path):
    a = arboles.crear_arbol(tmp_path / "a", semilla=3, dirs=1,
                            archivos_por_dir=2, profundidad=0)
    principal = tmp_path / "principal"
    p, fs = mcombi.rutas_validadas(principal, [a])
    rc = mcombi.ejecutar({"principal": p, "fuentes": fs},
                         mcombi.Opciones(politica=politica(), crear_indice=False),
                         log=nolog)
    assert rc.estado == "completado"
    # Sin índice, Descombinar rechaza el directorio (comportamiento documentado).
    with pytest.raises(ValueError):
        mdescombi.rutas_validadas(p, None)
