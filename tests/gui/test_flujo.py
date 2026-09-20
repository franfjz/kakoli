# -*- coding: utf-8 -*-
"""Flujo completo GUI con un motor real pequeño (Renombrar en modo vista previa):
_iniciar -> hilo de trabajo -> cola -> _fin, bombeando `procesar_cola` a mano."""
from __future__ import annotations

import pytest

from tests.gui.conftest import bombear

pytestmark = pytest.mark.gui


def test_flujo_renombrar_vista_previa(app, tmp_path):
    (tmp_path / "a.txt").write_text("x")
    from tasks.renombrar.pestana import PestanaRenombrar
    pes = app.pestana(PestanaRenombrar)
    txt = pes._widgets_lista["origenes"]
    txt.delete("1.0", "end")
    txt.insert("1.0", str(tmp_path) + "\n")
    pes.v_prefijo.set("p_")

    pes._previsualizar()                 # simular=True -> _iniciar en un hilo
    bombear(app, pes)

    assert not pes.ocupada()
    # Vista previa (simular): NO renombra el archivo.
    assert (tmp_path / "a.txt").exists()
    assert not (tmp_path / "p_a.txt").exists()
    # El estado final refleja que completó.
    assert pes.v_estado.get().startswith("Completado")
    # Y se ha reactivado la navegación (desbloqueo).
    assert app._bloqueado is False


def test_flujo_error_de_validacion_no_arranca(app, tmp_path):
    from tasks.renombrar.pestana import PestanaRenombrar
    pes = app.pestana(PestanaRenombrar)
    txt = pes._widgets_lista["origenes"]
    txt.delete("1.0", "end")
    txt.insert("1.0", str(tmp_path) + "\n")   # sin prefijo/sufijo/buscar -> _validar falla
    pes._iniciar()                       # muestra error (neutralizado) y no arranca hilo
    assert not pes.ocupada()
