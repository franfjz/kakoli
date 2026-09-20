# -*- coding: utf-8 -*-
"""Caracterización de core.control.Control: las señales de parada comunes del bucle
de proceso (pausa del usuario, archivo PAUSA, límite, cancelación) y su traducción a
estado 'pausado'/'cancelado'."""
from __future__ import annotations


import core.control as control
Control = control.Control


def test_sin_causas_no_para():
    c = Control()
    assert c.debe_parar() is False
    assert c.motivo == "" and c.estado == "pausado"


def test_pausa_del_usuario():
    c = Control(pausar=lambda: True)
    assert c.debe_parar() is True
    assert c.cancelado is False and c.estado == "pausado"
    assert "Pausado" in c.motivo


def test_cancelacion_tiene_prioridad_sobre_pausa():
    c = Control(pausar=lambda: True, cancelar=lambda: True)
    assert c.debe_parar() is True
    assert c.cancelado is True and c.estado == "cancelado"
    assert "Cancelado" in c.motivo


def test_archivo_pausa(tmp_path):
    ruta = tmp_path / "PAUSA"
    c = Control(pausa_ruta=ruta)
    assert c.debe_parar() is False        # aún no existe
    ruta.write_text("")
    assert c.debe_parar() is True
    assert "PAUSA" in c.motivo and c.estado == "pausado"


def test_limite_de_unidades():
    hechas = {"n": 0}
    c = Control(limite=3, contador=lambda: hechas["n"], nombre_unidad="carpetas")
    assert c.debe_parar() is False
    hechas["n"] = 3
    assert c.debe_parar() is True
    assert "límite de 3 carpetas" in c.motivo


def test_debe_pausar_no_mira_cancelacion():
    """debe_pausar (callback del Ejecutor) NO considera la cancelación: esa va por el
    parámetro `cancelar` del propio Ejecutor."""
    c = Control(cancelar=lambda: True)
    assert c.debe_pausar() is False
    assert c.cancelado is False


def test_desde_ejecutor_cancelado():
    c = Control()
    c.desde_ejecutor("cancelado")
    assert c.cancelado is True and c.estado == "cancelado" and "Cancelado" in c.motivo


def test_desde_ejecutor_pausado():
    c = Control()
    c.desde_ejecutor("pausado")
    assert c.cancelado is False and c.estado == "pausado" and "Pausado" in c.motivo


def test_desde_ejecutor_ok_no_marca_nada():
    c = Control()
    c.desde_ejecutor("ok")
    assert c.motivo == "" and c.cancelado is False


def test_desde_ejecutor_conserva_motivo_previo():
    """Si el bucle ya fijó un motivo (p. ej. el archivo PAUSA), no se sobrescribe."""
    c = Control()
    c.motivo = "Pausado: existe el archivo PAUSA (bórralo para continuar)."
    c.desde_ejecutor("pausado")
    assert "PAUSA" in c.motivo
