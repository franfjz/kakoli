# -*- coding: utf-8 -*-
"""GUI: el botón Cancelar (Fase 4 mejoras). Verifica el cableado con la máquina de
ejecución y el renderizado del final 'cancelado' como reanudable ('Continuar')."""
from __future__ import annotations

import pytest


import core.resultado as resultado
Resultado = resultado.Resultado

pytestmark = pytest.mark.gui


def _pes(app):
    from tasks.renombrar.pestana import PestanaRenombrar
    return app.pestana(PestanaRenombrar)


def test_boton_cancelar_desactivado_al_inicio(app):
    pes = _pes(app)
    assert str(pes.b_cancelar.cget("state")) == "disabled"


def test_cancelar_pide_cancelacion_y_desactiva_boton(app):
    """_cancelar (con el modal confirmado) activa la señal de cancelación de la
    máquina de ejecución y deshabilita los botones Cancelar/Pausar."""
    pes = _pes(app)
    assert not pes._ejec.cancela.is_set()
    pes._cancelar()                       # askyesno está monkeypatcheado a True
    assert pes._ejec.cancela.is_set()
    assert str(pes.b_cancelar.cget("state")) == "disabled"
    assert str(pes.b_pausar.cget("state")) == "disabled"


def test_fin_cancelado_queda_reanudable(app):
    """Un Resultado('cancelado') deja la pestaña lista para reanudar: botón
    'Continuar', estado con lo que queda, y sin pedir el modal al reanudar."""
    pes = _pes(app)
    pes._fin(Resultado("cancelado", procesadas=1, restantes=3, total=4))
    assert pes._reanudando_en_sesion is True
    assert str(pes.b_iniciar.cget("text")) == "Continuar"
    assert pes.v_estado.get() == "Cancelado: quedan 3."
    assert str(pes.b_cancelar.cget("state")) == "disabled"
    assert str(pes.b_iniciar.cget("state")) == "normal"
