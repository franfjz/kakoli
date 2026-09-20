# -*- coding: utf-8 -*-
"""tarea Descombinar — paquete vertical: motor, pestana, ayuda y DESCRIPTOR.

Gemela de Combinar: consume el artefacto "carpeta_combinada". Comparte con su
gemela el índice `tasks/formatos/indice_combinacion` (no importa a la gemela).
"""
from __future__ import annotations

from core.registro import DescriptorTarea
from tasks.descombinar.pestana import PestanaDescombinar
from tasks.descombinar.ayuda import SECCIONES

DESCRIPTOR = DescriptorTarea(
    id="descombinar",
    nombre="Descombinar",
    clase=PestanaDescombinar,
    consume="carpeta_combinada",
    ayuda=SECCIONES,
)
