# -*- coding: utf-8 -*-
"""Bomba de colas bajo demanda (Fase 1): en reposo no hay timer; al iniciar una
tarea se arma y, al terminar, se detiene sola. Así el proceso puede quedarse
inactivo (CPU/batería) cuando no hay trabajo.

Estos tests dejan que la propia `App._bomba` (vía `after`) drene la cola —en vez
de llamar a `procesar_cola` a mano como el helper `bombear`— para ejercitar de
verdad el arranque/parada del temporizador."""
from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.gui


def _dejar_correr_la_bomba(app, pes, *, segundos: float = 3.0,
                           pausa: float = 0.02) -> None:
    """Espera al hilo y luego bombea la ventana con `update()` (que dispara los
    `after` vencidos, incluida `_bomba`) hasta que la tarea termina y la bomba se
    apaga sola."""
    if pes.hilo is not None:
        pes.hilo.join(timeout=segundos)
    t0 = time.time()
    while time.time() - t0 < segundos:
        app.update()                       # dispara los after() vencidos (_bomba)
        if not pes.ocupada() and app._id_bomba is None:
            break
        time.sleep(pausa)


def test_reposo_sin_timer(app):
    # Nada más arrancar / volver al menú: la bomba NO está armada.
    assert app._id_bomba is None


def test_arranca_al_iniciar_y_se_detiene_al_terminar(app, tmp_path):
    (tmp_path / "a.txt").write_text("x")
    from tasks.renombrar.pestana import PestanaRenombrar
    pes = app.pestana(PestanaRenombrar)
    txt = pes._widgets_lista["origenes"]
    txt.delete("1.0", "end")
    txt.insert("1.0", str(tmp_path) + "\n")
    pes.v_prefijo.set("p_")

    assert app._id_bomba is None           # reposo
    pes._previsualizar()                   # _iniciar -> bloquear -> arma la bomba
    assert app._id_bomba is not None       # armada mientras trabaja
    assert app._bloqueado is True

    _dejar_correr_la_bomba(app, pes)

    assert not pes.ocupada()
    assert app._bloqueado is False
    assert app._id_bomba is None           # se apagó sola en reposo
    # La bomba (no el helper) drenó el evento `fin`: el estado refleja el final.
    assert pes.v_estado.get().startswith("Completado")


def test_arrancar_bomba_es_idempotente(app):
    # Armar dos veces no crea dos timers (mismo id, un solo after vivo).
    app._bloqueado = True
    app._arrancar_bomba()
    primero = app._id_bomba
    app._arrancar_bomba()
    assert app._id_bomba is primero
    # Limpieza: parar la bomba para no dejar el timer colgado.
    app._bloqueado = False
    app._bomba()
    assert app._id_bomba is None
