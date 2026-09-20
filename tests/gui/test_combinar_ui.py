# -*- coding: utf-8 -*-
"""Rediseño de la pestaña Combinar: política de conflicto en radios (una fila) con
selección única y VISIBLE, opciones dependientes que aparecen/ocultan según la
política elegida (conservando su estado) y el campo de rutas redimensionable con
barra vertical."""
from __future__ import annotations

import pytest

from gui import tema

pytestmark = pytest.mark.gui


@pytest.fixture
def pes(app):
    from tasks.combinar.pestana import PestanaCombinar
    p = app.pestana(PestanaCombinar)
    p.v_conflicto.set("renombrar")          # estado conocido de partida
    p.v_codigo.set("Nombre de la carpeta de origen")
    p.v_codigo_texto.set("")
    return p


def _seleccionados(pes):
    return [rb.cget("value") for rb in pes._radios_conflicto
            if str(rb.cget("bg")) == tema.PRIMARY]


def _visible(w):
    return bool(w.winfo_manager())          # '' si está oculto (grid_remove)


def test_politica_en_radios_seleccion_unica_visible(pes):
    assert len(pes._radios_conflicto) == 3
    pes.v_conflicto.set("reemplazar")
    assert _seleccionados(pes) == ["reemplazar"]     # solo uno resaltado
    pes.v_conflicto.set("mantener")
    assert _seleccionados(pes) == ["mantener"]       # se mueve, no se acumula


def test_criterio_solo_visible_con_reemplazar(pes):
    pes.v_conflicto.set("renombrar")
    assert not _visible(pes.blq_criterio)
    pes.v_conflicto.set("reemplazar")
    assert _visible(pes.blq_criterio)
    assert str(pes.cb_criterio.cget("state")) == "readonly"
    pes.v_conflicto.set("mantener")
    assert not _visible(pes.blq_criterio)


def test_codigo_solo_visible_con_renombrar(pes):
    pes.v_conflicto.set("renombrar")
    assert _visible(pes.blq_codigo)
    pes.v_conflicto.set("reemplazar")
    assert not _visible(pes.blq_codigo)


def test_personalizado_solo_con_renombrar_y_codigo_personalizado(pes):
    pes.v_conflicto.set("renombrar")
    pes.v_codigo.set("Nombre de la carpeta de origen")
    pes._actualizar_codigo()
    assert not _visible(pes.blq_personalizado)
    pes.v_codigo.set("Personalizado")
    pes._actualizar_codigo()
    assert _visible(pes.blq_personalizado)
    assert str(pes.e_codigo.cget("state")) == "normal"


def test_cambiar_politica_conserva_el_estado(pes):
    # 'Renombrar' + código Personalizado con texto propio.
    pes.v_conflicto.set("renombrar")
    pes.v_codigo.set("Personalizado")
    pes._actualizar_codigo()
    pes.v_codigo_texto.set("MI_SUFIJO")
    # Cambiar a otra política (se ocultan los dependientes) y volver.
    pes.v_conflicto.set("reemplazar")
    pes.v_conflicto.set("renombrar")
    # El texto y el código elegido siguen ahí (no hay que reescribir nada).
    assert pes.v_codigo.get() == "Personalizado"
    assert pes.v_codigo_texto.get() == "MI_SUFIJO"
    assert _visible(pes.blq_personalizado)


def test_conflictos_en_recuadro_con_ayuda_sobre_los_botones(pes):
    # El bloque de conflictos es un recuadro (LabelFrame) titulado, con la ayuda
    # en la fila 0 (bajo el título) y los radios en la fila 1 (debajo).
    blq = pes._radios_conflicto[0].master.master
    assert blq.winfo_class() == "TLabelframe"
    assert str(blq.cget("text")) == "Conflictos entre archivos"
    fila_radios = pes._radios_conflicto[0].master
    ayudas = [w for w in blq.grid_slaves() if w.winfo_class() == "Label"]
    assert ayudas, "falta el texto de ayuda"
    assert int(ayudas[0].grid_info()["row"]) < int(fila_radios.grid_info()["row"])


def test_examinar_anade_una_e_ignora_duplicados(pes, monkeypatch):
    from tkinter import filedialog
    txt = pes._widgets_lista["mas"]
    txt.delete("1.0", "end")
    txt.insert("1.0", "D:/ya/estaba\n")
    campo = next(c for c in pes.campos if c.clave == "mas")
    # Examinar añade UNA carpeta y cierra (comportamiento por defecto).
    monkeypatch.setattr(filedialog, "askdirectory", lambda *a, **k: "D:/n1")
    pes._anexar_carpeta(txt, campo)
    assert pes.valores_lista("mas") == ["D:/ya/estaba", "D:/n1"]
    # Elegir una que ya está: no cambia nada.
    monkeypatch.setattr(filedialog, "askdirectory", lambda *a, **k: "D:/ya/estaba")
    pes._anexar_carpeta(txt, campo)
    assert pes.valores_lista("mas") == ["D:/ya/estaba", "D:/n1"]
    # Cancelar (cadena vacía): no cambia nada.
    monkeypatch.setattr(filedialog, "askdirectory", lambda *a, **k: "")
    pes._anexar_carpeta(txt, campo)
    assert pes.valores_lista("mas") == ["D:/ya/estaba", "D:/n1"]


def test_campo_lista_redimensionable_con_barra(pes):
    # El Text de rutas existe, tiene alto ajustable (líneas) y una barra hermana.
    txt = pes._widgets_lista["mas"]
    assert int(txt.cget("height")) >= 2
    caja = txt.master
    clases = {h.winfo_class() for h in caja.winfo_children()}
    assert "TScrollbar" in clases                    # barra vertical disponible
    assert "Frame" in clases                          # tirador de redimensionado
