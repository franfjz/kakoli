# -*- coding: utf-8 -*-
"""Caracterización de core.reanudable: el registro de progreso reanudable común a
todas las tareas (JSONL append-only, validación de cabecera, compactación)."""
from __future__ import annotations


import core.reanudable as reanudable
RegistroReanudable = reanudable.RegistroReanudable


def _firma():
    return {"modo": "ruta", "sep": "-"}


# ---------------- anota / procesados ----------------
def test_anota_y_procesados(tmp_path):
    ruta = tmp_path / "reg.jsonl"
    reg = RegistroReanudable.cargar(ruta, "tarea", tmp_path / "orig", _firma())
    reg.anota("a", "A")
    reg.anota("b", "B")
    assert reg.procesados() == {"a", "b"}
    assert reg.salida_de("a") == "A"
    reg.guardar()
    assert ruta.exists()


def test_marca_guarda_campos_arbitrarios(tmp_path):
    ruta = tmp_path / "reg.jsonl"
    reg = RegistroReanudable.cargar(ruta, "comprimir", tmp_path / "orig", {})
    reg.marca("carpeta", zip="carpeta.zip", bytes=123, entradas=4)
    reg.cerrar()
    reg2 = RegistroReanudable.cargar(ruta, "comprimir", tmp_path / "orig", {})
    ent = reg2.entrada("carpeta")
    assert ent["zip"] == "carpeta.zip" and ent["bytes"] == 123 and ent["entradas"] == 4


# ---------------- persistencia / recarga ----------------
def test_recarga_conserva_lo_hecho(tmp_path):
    ruta = tmp_path / "reg.jsonl"
    origen = tmp_path / "orig"
    reg = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    reg.anota("a", "A")
    reg.anota("b", "B")
    reg.guardar()
    reg2 = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    assert reg2.procesados() == {"a", "b"}


# ---------------- inspeccionar (modal) ----------------
def test_inspeccionar_detecta_pendiente(tmp_path):
    ruta = tmp_path / "reg.jsonl"
    origen = tmp_path / "orig"
    reg = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    reg.anota("a", "A")
    reg.guardar()

    info = RegistroReanudable.inspeccionar(ruta, "tarea", origen, _firma())
    assert info is not None and info["hechas"] == 1 and info["fecha"]

    # Firma distinta -> el progreso no vale -> None.
    assert RegistroReanudable.inspeccionar(ruta, "tarea", origen,
                                           {"modo": "final"}) is None
    # Otra tarea/origen -> None.
    assert RegistroReanudable.inspeccionar(ruta, "otra", origen, _firma()) is None


def test_inspeccionar_sin_fichero_es_none(tmp_path):
    assert RegistroReanudable.inspeccionar(
        tmp_path / "no.jsonl", "tarea", tmp_path / "o", _firma()) is None


# ---------------- completar / reiniciar ----------------
def test_completar_borra(tmp_path):
    ruta = tmp_path / "reg.jsonl"
    origen = tmp_path / "orig"
    reg = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    reg.anota("a", "A")
    reg.guardar()
    reg.completar(borrar=True)
    assert not ruta.exists()
    assert RegistroReanudable.inspeccionar(ruta, "tarea", origen, _firma()) is None


def test_reiniciar_empieza_de_cero(tmp_path):
    ruta = tmp_path / "reg.jsonl"
    origen = tmp_path / "orig"
    reg = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    reg.anota("a", "A")
    reg.guardar()
    reg2 = RegistroReanudable.cargar(ruta, "tarea", origen, _firma(), reiniciar=True)
    assert reg2.procesados() == set()
    assert not ruta.exists()


# ---------------- cabecera incongruente ----------------
def test_cabecera_incongruente_empieza_de_cero(tmp_path):
    ruta = tmp_path / "reg.jsonl"
    origen = tmp_path / "orig"
    reg = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    reg.anota("a", "A")
    reg.guardar()
    # Misma ruta, otra firma: el fichero previo no vale y se descarta.
    reg2 = RegistroReanudable.cargar(ruta, "tarea", origen, {"modo": "final"})
    assert reg2.procesados() == set()
    reg2.anota("z", "Z")
    reg2.guardar()
    reg3 = RegistroReanudable.cargar(ruta, "tarea", origen, {"modo": "final"})
    assert reg3.procesados() == {"z"}          # el fichero se rehízo limpio


# ---------------- errores / descartados ----------------
def test_errores_y_descartados_persisten(tmp_path):
    ruta = tmp_path / "reg.jsonl"
    origen = tmp_path / "orig"
    reg = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    reg.anota("a", "A")
    reg.descarta("b", "mantenido")
    reg.error("x: falló")
    reg.error("x: falló")                       # duplicado: no se repite
    reg.guardar()
    reg2 = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    assert reg2.procesados() == {"a"}
    assert reg2.errores == ["x: falló"]
    assert reg2.descartados and reg2.descartados[0]["descarta"] == "b"


# ---------------- compactación ----------------
def test_compacta_lineas_repetidas(tmp_path):
    ruta = tmp_path / "reg.jsonl"
    origen = tmp_path / "orig"
    reg = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    # Muchas re-anotaciones de pocas unidades -> muchas líneas de cuerpo.
    for _ in range(300):
        reg.anota("a", "A")
        reg.anota("b", "B")
    reg.guardar()
    lineas_antes = ruta.read_text(encoding="utf-8").count("\n")
    assert lineas_antes > 200
    # Al recargar se compacta: cabecera + 2 unidades = 3 líneas.
    reg2 = RegistroReanudable.cargar(ruta, "tarea", origen, _firma())
    assert reg2.procesados() == {"a", "b"}
    lineas_despues = ruta.read_text(encoding="utf-8").count("\n")
    assert lineas_despues < lineas_antes and lineas_despues <= 3
