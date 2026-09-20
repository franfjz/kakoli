# -*- coding: utf-8 -*-
"""Caracterización de core.recursos: la tabla de decisión de hilos (`calcular_hilos`),
`techo_hilos` y el objetivo de workers del throttling (`objetivo_activos`).

Se construyen PerfilSistema sintéticos (no se mide la máquina real), así que la
tabla es reproducible en cualquier equipo. Los valores esperados son los
documentados en docs/ARQUITECTURA.md §5.3.
"""
from __future__ import annotations

import pytest


import core.recursos as recursos
MB = 1024 * 1024
GB = 1024 * MB


def perfil(*, cpu, ram_total, ram_disp, cpu_fisicos=None, disco_lento=False,
           mismo_volumen=None, tipo_unidad="local", swap_usado=0,
           carga_externa=None, energia="enchufado", proceso_64bit=True):
    """PerfilSistema sintético con los campos por defecto de un equipo holgado."""
    return recursos.PerfilSistema(
        cpu=cpu, cpu_logicos=cpu, cpu_fisicos=cpu_fisicos,
        ram_total=ram_total, ram_disponible=ram_disp, origen_ram="test",
        swap_total=0, swap_usado=swap_usado, disco_lento=disco_lento,
        disco_libre=100 * GB, mismo_volumen=mismo_volumen, tipo_unidad=tipo_unidad,
        carga=None, energia=energia, proceso_64bit=proceso_64bit,
        carga_externa=carga_externa)


POL = recursos.PoliticaHilos()   # defaults documentados


# --- tabla de calcular_hilos (docs/ARQUITECTURA.md §5.3) ---
def test_hilos_2nucleos_poca_ram():
    p = perfil(cpu=2, ram_total=2 * GB, ram_disp=900 * MB)
    assert recursos.calcular_hilos(p, POL) == 1


def test_hilos_4nucleos_3gb_ssd():
    p = perfil(cpu=4, ram_total=4 * GB, ram_disp=3200 * MB)
    assert recursos.calcular_hilos(p, POL) == 3


def test_hilos_8nucleos_12gb_ssd():
    p = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB)
    assert recursos.calcular_hilos(p, POL) == 7


def test_hilos_8nucleos_hdd_disco_distinto():
    p = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB, disco_lento=True,
               mismo_volumen=False)
    assert recursos.calcular_hilos(p, POL) == 3


def test_hilos_8nucleos_hdd_mismo_disco():
    p = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB, disco_lento=True,
               mismo_volumen=True)
    assert recursos.calcular_hilos(p, POL) == 1


def test_hilos_swap_en_uso_fuerza_secuencial():
    p = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB, swap_usado=1 * GB)
    assert recursos.calcular_hilos(p, POL) == 1


def test_hilos_bateria_topa_en_2():
    p = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB, energia="bateria")
    assert recursos.calcular_hilos(p, POL) == 2


def test_hilos_carga_externa_alta_reduce():
    base = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB)
    ocupado = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB, carga_externa=0.5)
    assert recursos.calcular_hilos(ocupado, POL) < recursos.calcular_hilos(base, POL)


def test_hilos_usuario_fuerza_respeta_pero_topa_por_unidades():
    p = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB)
    forzada = recursos.PoliticaHilos(hilos=6)
    assert recursos.calcular_hilos(p, forzada) == 6
    assert recursos.calcular_hilos(p, forzada, unidades=2) == 2


def test_hilos_nunca_mas_que_unidades():
    p = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB)
    assert recursos.calcular_hilos(p, POL, unidades=1) == 1


# --- techo_hilos (característica estable, ignora RAM/carga del momento) ---
def test_techo_ssd_8nucleos():
    p = perfil(cpu=8, ram_total=16 * GB, ram_disp=1 * MB)   # RAM baja: no influye
    assert recursos.techo_hilos(p) == 7


def test_techo_2nucleos():
    p = perfil(cpu=2, ram_total=2 * GB, ram_disp=1 * GB)
    assert recursos.techo_hilos(p) == 1


def test_techo_hdd_mismo_disco():
    p = perfil(cpu=8, ram_total=16 * GB, ram_disp=12 * GB, disco_lento=True,
               mismo_volumen=True)
    assert recursos.techo_hilos(p) == 1


# --- objetivo_activos (throttling por carga externa) ---
@pytest.mark.parametrize("externo, esperado", [
    (None, 8),
    (0.1, 8),
    (0.25, 8),
    (0.5, 4),
    (0.75, 1),
    (0.9, 1),
])
def test_objetivo_activos(externo, esperado):
    assert recursos.objetivo_activos(externo, 8) == esperado
