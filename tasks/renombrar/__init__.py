# -*- coding: utf-8 -*-
"""tarea Renombrar — paquete vertical y autónomo: motor (lógica), pestana (GUI),
ayuda (texto) y este DESCRIPTOR para el registro.

Añadir esta tarea a la app es solo referenciar `DESCRIPTOR` desde el manifiesto
`tasks/__init__.py`. Renombrar no tiene gemela ni handoff (produce/consume None).
"""
from __future__ import annotations

from core.registro import DescriptorTarea
from tasks.renombrar.pestana import PestanaRenombrar
from tasks.renombrar.ayuda import SECCIONES

DESCRIPTOR = DescriptorTarea(
    id="renombrar",
    nombre="Renombrar",
    clase=PestanaRenombrar,
    ayuda=SECCIONES,
)
