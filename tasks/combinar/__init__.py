# -*- coding: utf-8 -*-
"""tarea Combinar — paquete vertical: motor, pestana, ayuda y DESCRIPTOR.

Gemela de Descombinar: produce el artefacto "carpeta_combinada". Comparte con su
gemela el índice `tasks/formatos/indice_combinacion` (no importa a la gemela).
"""
from __future__ import annotations

from core.registro import DescriptorTarea
from tasks.combinar.pestana import PestanaCombinar
from tasks.combinar.ayuda import SECCIONES

DESCRIPTOR = DescriptorTarea(
    id="combinar",
    nombre="Combinar",
    clase=PestanaCombinar,
    produce="carpeta_combinada",
    ayuda=SECCIONES,
)
