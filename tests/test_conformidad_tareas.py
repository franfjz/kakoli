# -*- coding: utf-8 -*-
"""test_conformidad_tareas — el CONTRATO de tarea, verificado sobre el REGISTRO.

Recorre `tasks.REGISTRO` (la fuente de verdad del manifiesto) y comprueba, por cada
tarea registrada, que cumple el contrato que la GUI y el arné de consola dan por
sentado. Así, si alguien añade una tarea nueva que rompe el contrato (motor sin
`ejecutar` con la firma correcta, `Opciones` que no hereda de `OpcionesBase`, sin
`main`, o una pestaña sin los métodos que App usa), FALLA aquí y no en la GUI en
tiempo de ejecución.

Es Tk-free: solo importa módulos e inspecciona firmas/atributos de CLASE, sin
instanciar ninguna pestaña (no necesita un root de Tcl), así que corre siempre.

Contratos verificados:
  - motor.ejecutar(entradas, opts, *, log, progreso, pausar, cancelar, confirmar)  [B]
  - motor.Opciones subclase de core.opciones.OpcionesBase, instanciable con defaults
  - motor.main : CLI (por convención via core.cli.correr_cli)
  - motor.info_reanudable(entradas, opts=...) si existe          [reanudación]
  - la clase de pestaña cumple core.registro.FabricaPestana       [C9]
  - handoff coherente: cada `consume` tiene un `produce` que lo casa
"""
from __future__ import annotations

import inspect
from importlib import import_module

import pytest

from core.opciones import OpcionesBase
from tasks import REGISTRO

DESCRIPTORES = REGISTRO.descriptores()

# Métodos/atributos que App usa de la clase de pestaña (ver FabricaPestana).
_MIEMBROS_FABRICA = ("procesar_cola", "ocupada", "pedir_cierre", "establecer_origen")


def _motor_de(desc):
    """Módulo motor de una tarea, derivado del módulo de su clase de pestaña
    (`tasks.<x>.pestana` → `tasks.<x>.motor`): el mismo enlace que usa la GUI."""
    paquete = desc.clase.__module__.rsplit(".", 1)[0]
    return import_module(paquete + ".motor")


@pytest.mark.parametrize("desc", DESCRIPTORES, ids=lambda d: d.id)
def test_motor_cumple_contrato_ejecutar(desc):
    motor = _motor_de(desc)
    assert hasattr(motor, "ejecutar"), f"{desc.id}: el motor no expone ejecutar()"
    params = inspect.signature(motor.ejecutar).parameters
    nombres = list(params)
    assert nombres[:2] == ["entradas", "opts"], (
        f"{desc.id}: ejecutar debe empezar por (entradas, opts), no {nombres[:2]}")
    for cb in ("log", "progreso", "pausar", "cancelar", "confirmar"):
        assert cb in params, f"{desc.id}: ejecutar sin el callback '{cb}'"
        assert params[cb].kind == inspect.Parameter.KEYWORD_ONLY, (
            f"{desc.id}: el callback '{cb}' debe ser keyword-only (tras '*')")


@pytest.mark.parametrize("desc", DESCRIPTORES, ids=lambda d: d.id)
def test_motor_opciones_y_cli(desc):
    motor = _motor_de(desc)
    assert hasattr(motor, "Opciones"), f"{desc.id}: el motor no define Opciones"
    assert issubclass(motor.Opciones, OpcionesBase), (
        f"{desc.id}: Opciones debe heredar de OpcionesBase")
    motor.Opciones()  # instanciable con valores por defecto
    assert callable(getattr(motor, "main", None)), (
        f"{desc.id}: el motor no expone main() (CLI)")


@pytest.mark.parametrize("desc", DESCRIPTORES, ids=lambda d: d.id)
def test_motor_info_reanudable_si_existe(desc):
    """Si el motor declara info_reanudable, su primer parámetro es `entradas`."""
    motor = _motor_de(desc)
    fn = getattr(motor, "info_reanudable", None)
    if fn is None:
        return
    nombres = list(inspect.signature(fn).parameters)
    assert nombres and nombres[0] == "entradas", (
        f"{desc.id}: info_reanudable debe recibir (entradas, ...), no {nombres}")


@pytest.mark.parametrize("desc", DESCRIPTORES, ids=lambda d: d.id)
def test_pestana_cumple_fabrica(desc):
    """La clase de pestaña ofrece lo que App usa (core.registro.FabricaPestana)."""
    cls = desc.clase
    assert isinstance(getattr(cls, "nombre", None), str), (
        f"{desc.id}: la pestaña no tiene un atributo de clase `nombre` (str)")
    for miembro in _MIEMBROS_FABRICA:
        assert callable(getattr(cls, miembro, None)), (
            f"{desc.id}: la pestaña no ofrece {miembro}() (FabricaPestana)")


def test_ids_unicos():
    ids = [d.id for d in DESCRIPTORES]
    assert len(ids) == len(set(ids)), f"ids de tarea duplicados: {ids}"


def test_handoff_coherente():
    """Todo artefacto CONSUMIDO por una tarea es PRODUCIDO por alguna (gemelas)."""
    producidos = {d.produce for d in DESCRIPTORES if d.produce}
    for d in DESCRIPTORES:
        if d.consume:
            assert d.consume in producidos, (
                f"{d.id} consume '{d.consume}' pero ninguna tarea lo produce")
