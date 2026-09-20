# -*- coding: utf-8 -*-
"""test_importa_todo — humo de arranque: cada módulo de la app se importa sin error,
y las utilidades de soporte funcionan. Importar un módulo de GUI NO crea una ventana
Tk (solo define clases), así que es seguro sin display."""
from __future__ import annotations

import importlib
import pkgutil

import pytest

import core
import gui
import tasks
from tests.soporte import arboles


def _modulos():
    nombres = ["kakoli"]
    for paquete in (core, gui, tasks):
        for info in pkgutil.walk_packages(paquete.__path__, paquete.__name__ + "."):
            nombres.append(info.name)
    return nombres


@pytest.mark.parametrize("nombre", _modulos())
def test_cada_modulo_importa(nombre):
    """Cada módulo de core/gui/tasks (y kakoli) se importa sin error."""
    assert importlib.import_module(nombre) is not None


def test_contrato_ejecutar_en_los_ocho_motores():
    """Los 8 motores exponen el contrato uniforme `ejecutar` y `rutas_validadas`."""
    for tarea in ("comprimir", "descomprimir", "combinar", "descombinar",
                  "aplanar", "desaplanar", "renombrar", "eliminar"):
        motor = importlib.import_module(f"tasks.{tarea}.motor")
        assert hasattr(motor, "ejecutar"), tarea
        assert hasattr(motor, "rutas_validadas"), tarea
        assert hasattr(motor, "Opciones"), tarea


def test_soporte_arboles_round_trip_de_firma(tmp_path):
    """La utilidad de árboles crea, firma y compara de forma consistente: un árbol
    copiado a sí mismo no tiene diferencias; alterar un archivo se detecta."""
    a = arboles.crear_arbol(tmp_path / "a", semilla=1)
    b = arboles.crear_arbol(tmp_path / "b", semilla=1)
    assert arboles.comparar(a, b) == []

    (b / "a0_0.txt").write_bytes(b"otro contenido")
    assert arboles.comparar(a, b) != []


def test_soporte_preserva_carpeta_vacia(tmp_path):
    """La firma incluye las carpetas vacías (invariante del round-trip)."""
    a = arboles.crear_arbol(tmp_path / "a", semilla=2, vacios=True)
    firma = arboles.firmar(a)
    assert "vacia/" in firma
