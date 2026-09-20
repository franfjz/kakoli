# -*- coding: utf-8 -*-
"""tarea Desaplanar — paquete vertical: motor, pestana, ayuda y DESCRIPTOR.

Gemela de Aplanar: consume el artefacto "carpeta_aplanada". Comparte con su gemela
el códec `tasks/formatos/nombres_aplanado` (no importa a la gemela).
"""
from __future__ import annotations

from core.registro import DescriptorTarea
from tasks.desaplanar.pestana import PestanaDesaplanar
from tasks.desaplanar.ayuda import SECCIONES

DESCRIPTOR = DescriptorTarea(
    id="desaplanar",
    nombre="Desaplanar",
    clase=PestanaDesaplanar,
    consume="carpeta_aplanada",
    ayuda=SECCIONES,
)
