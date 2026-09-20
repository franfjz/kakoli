# -*- coding: utf-8 -*-
"""Aplanar usa el mismo sistema de 'Conflictos entre archivos' que Combinar:
política en radios (una fila) con selección única y visible, dentro de un recuadro,
y el criterio de 'Reemplazar' que solo aparece si esa política está elegida."""
from __future__ import annotations

import pytest

from gui import tema

pytestmark = pytest.mark.gui


@pytest.fixture
def pes(app):
    from tasks.aplanar.pestana import PestanaAplanar
    p = app.pestana(PestanaAplanar)
    p.v_conflicto.set("renombrar")
    return p


def _seleccionados(pes):
    return [rb.cget("value") for rb in pes._radios_conflicto
            if str(rb.cget("bg")) == tema.PRIMARY]


def _visible(w):
    return bool(w.winfo_manager())


def test_politica_en_radios_seleccion_unica(pes):
    assert len(pes._radios_conflicto) == 3
    pes.v_conflicto.set("reemplazar")
    assert _seleccionados(pes) == ["reemplazar"]
    pes.v_conflicto.set("mantener")
    assert _seleccionados(pes) == ["mantener"]


def test_conflictos_en_recuadro(pes):
    blq = pes._radios_conflicto[0].master.master
    assert blq.winfo_class() == "TLabelframe"
    assert str(blq.cget("text")) == "Conflictos entre archivos"


def test_criterio_solo_visible_con_reemplazar(pes):
    pes.v_conflicto.set("renombrar")
    assert not _visible(pes.blq_criterio)
    pes.v_conflicto.set("reemplazar")
    assert _visible(pes.blq_criterio)
    assert str(pes.cb_criterio.cget("state")) == "readonly"
    pes.v_conflicto.set("mantener")
    assert not _visible(pes.blq_criterio)


def test_validar_mapea_la_politica_cruda(pes, tmp_path):
    pes.v_conflicto.set("reemplazar")
    pes.v_origen.set(str(tmp_path))
    assert pes._validar()["opts"].conflicto == "reemplazar"
