# -*- coding: utf-8 -*-
"""tarea Eliminar — paquete vertical: motor (lógica), pestana (GUI, con botón de
peligro y confirmación reforzada), ayuda y este DESCRIPTOR para el registro.

Sin gemela ni handoff (produce/consume None)."""
from __future__ import annotations

from core.registro import DescriptorTarea
from tasks.eliminar.pestana import PestanaEliminar
from tasks.eliminar.ayuda import SECCIONES

DESCRIPTOR = DescriptorTarea(
    id="eliminar",
    nombre="Eliminar",
    clase=PestanaEliminar,
    ayuda=SECCIONES,
)
