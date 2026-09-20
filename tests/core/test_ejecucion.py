# -*- coding: utf-8 -*-
"""Caracterización de core.ejecucion: la máquina hilo+cola SIN Tkinter (arranque,
excepción->Resultado('error'), pausa cooperativa, orden de eventos, ocupada)."""
from __future__ import annotations

import time


import core.ejecucion as ejecucion
import core.resultado as resultado
Ejecucion = ejecucion.Ejecucion
Resultado = resultado.Resultado


def _esperar(ej, timeout=2.0):
    if ej.hilo is not None:
        ej.hilo.join(timeout=timeout)


def test_iniciar_encola_fin_con_resultado():
    ej = Ejecucion()
    ej.iniciar(lambda log, prog, pausar, cancelar: Resultado("completado", procesadas=3))
    _esperar(ej)
    lineas, ultimo, finales = ej.recoger()
    assert lineas == [] and ultimo is None
    assert len(finales) == 1 and finales[0].estado == "completado"
    assert finales[0].procesadas == 3


def test_excepcion_se_convierte_en_error():
    def trabajo(log, prog, pausar, cancelar):
        raise RuntimeError("boom")
    ej = Ejecucion()
    ej.iniciar(trabajo)
    _esperar(ej)
    _lineas, _ultimo, finales = ej.recoger()
    assert len(finales) == 1 and finales[0].estado == "error"
    assert "boom" in finales[0].mensaje


def test_log_y_progreso_se_recogen():
    def trabajo(log, prog, pausar, cancelar):
        log("hola")
        log("adiós")
        prog(1, 2, 0.5, "mitad")
        return Resultado("completado")
    ej = Ejecucion()
    ej.iniciar(trabajo)
    _esperar(ej)
    lineas, ultimo, finales = ej.recoger()
    assert lineas == ["hola", "adiós"]
    assert ultimo == (1, 2, 0.5, "mitad")
    assert finales[0].estado == "completado"


def test_solo_cuenta_el_ultimo_progreso():
    def trabajo(log, prog, pausar, cancelar):
        for i in range(5):
            prog(i, 5, i / 5, f"paso {i}")
        return Resultado("completado")
    ej = Ejecucion()
    ej.iniciar(trabajo)
    _esperar(ej)
    _lineas, ultimo, _finales = ej.recoger()
    assert ultimo == (4, 5, 4 / 5, "paso 4")


def test_pausa_cooperativa():
    def trabajo(log, prog, pausar, cancelar):
        while not pausar():
            time.sleep(0.005)
        return Resultado("pausado", restantes=2)
    ej = Ejecucion()
    ej.iniciar(trabajo)
    assert ej.ocupada() is True
    ej.pedir_pausa()
    _esperar(ej)
    assert ej.ocupada() is False
    _lineas, _ultimo, finales = ej.recoger()
    assert finales[0].estado == "pausado" and finales[0].restantes == 2


def test_cancelacion_cooperativa():
    def trabajo(log, prog, pausar, cancelar):
        while not cancelar():
            time.sleep(0.005)
        return Resultado("cancelado", restantes=2)
    ej = Ejecucion()
    ej.iniciar(trabajo)
    assert ej.ocupada() is True
    ej.pedir_cancelar()
    _esperar(ej)
    assert ej.ocupada() is False
    _lineas, _ultimo, finales = ej.recoger()
    assert finales[0].estado == "cancelado" and finales[0].restantes == 2


def test_ocupada_pasa_a_falso_al_terminar():
    ej = Ejecucion()
    assert ej.ocupada() is False
    ej.iniciar(lambda log, prog, pausar, cancelar: Resultado("nada"))
    _esperar(ej)
    assert ej.ocupada() is False
