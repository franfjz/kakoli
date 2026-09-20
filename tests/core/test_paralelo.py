# -*- coding: utf-8 -*-
"""Caracterización de core.paralelo: PlanLista y Ejecutor (reparto, pausa,
propagación del primer error). Sin Tkinter; concurrencia real."""
from __future__ import annotations

import threading

import pytest


import core.paralelo as paralelo
import core.resultado as resultado


# ---------------- PlanLista ----------------
def test_planlista_restantes_y_entrega_unica():
    plan = paralelo.PlanLista([1, 2, 3])
    assert plan.restantes == 3
    vistos = [plan.siguiente() for _ in range(4)]
    assert vistos == [1, 2, 3, None]      # cada item una sola vez, luego None
    assert plan.restantes == 3            # aún no terminadas


def test_planlista_terminada_descuenta():
    plan = paralelo.PlanLista(["a", "b"])
    plan.terminada("a")
    assert plan.restantes == 1
    plan.terminada("b")
    assert plan.restantes == 0


def test_planlista_cumple_el_protocol():
    assert isinstance(paralelo.PlanLista([1]), paralelo.Plan)


# ---------------- Ejecutor ----------------
@pytest.mark.parametrize("hilos", [1, 4, 8])
def test_ejecutor_procesa_cada_unidad_una_vez(hilos):
    items = list(range(50))
    vistos: list[int] = []
    lock = threading.Lock()

    def trabajo(x):
        with lock:
            vistos.append(x)

    estado = paralelo.Ejecutor(hilos).ejecutar(paralelo.PlanLista(items), trabajo)
    assert estado == "ok"
    assert sorted(vistos) == items        # todas, exactamente una vez


def test_ejecutor_pausa_desde_el_inicio_no_procesa_nada():
    items = list(range(20))
    vistos: list[int] = []
    lock = threading.Lock()

    def trabajo(x):
        with lock:
            vistos.append(x)

    plan = paralelo.PlanLista(items)
    estado = paralelo.Ejecutor(4).ejecutar(plan, trabajo, pausar=lambda: True)
    assert estado == "pausado"
    assert vistos == []
    assert plan.restantes == len(items)   # nada consumido


def test_ejecutor_propaga_el_primer_error():
    def trabajo(x):
        if x == 7:
            raise ValueError("boom en 7")

    with pytest.raises(ValueError, match="boom en 7"):
        paralelo.Ejecutor(4).ejecutar(paralelo.PlanLista(range(50)), trabajo)


def test_ejecutor_pedir_parada_corta():
    """pedir_parada() externo hace que el reparto termine como pausado."""
    ejec = paralelo.Ejecutor(2)
    ejec.pedir_parada()
    estado = ejec.ejecutar(paralelo.PlanLista(range(10)), lambda _x: None)
    assert estado == "pausado"


def test_ajustar_limite_acota_y_respeta_hilos():
    """ajustar_limite fija cuántos workers pueden estar activos, acotado a [1, hilos]."""
    ejec = paralelo.Ejecutor(4)
    ejec.ajustar_limite(2)
    assert ejec._activos_max == 2
    ejec.ajustar_limite(99)               # se acota al nº de hilos
    assert ejec._activos_max == 4
    ejec.ajustar_limite(0)                # nunca por debajo de 1
    assert ejec._activos_max == 1


def test_ejecutor_cancelar_desde_el_inicio():
    """cancelar()=True desde el arranque: no se toma ninguna unidad -> 'cancelado'."""
    plan = paralelo.PlanLista(range(20))
    estado = paralelo.Ejecutor(4).ejecutar(plan, lambda _x: None,
                                           cancelar=lambda: True)
    assert estado == "cancelado"
    assert plan.restantes == 20


def test_ejecutor_cancelado_del_trabajo_es_parada_limpia():
    """Si un trabajo lanza Cancelado (aborto intra-unidad), el reparto termina como
    'cancelado' (no como error) y para a TODOS los workers."""
    hechas: list[int] = []
    lock = threading.Lock()

    def trabajo(x):
        if x == 5:
            raise resultado.Cancelado()
        with lock:
            hechas.append(x)

    estado = paralelo.Ejecutor(4).ejecutar(paralelo.PlanLista(range(50)), trabajo)
    assert estado == "cancelado"
    assert 5 not in hechas                 # la unidad abortada no cuenta como hecha
