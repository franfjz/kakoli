# -*- coding: utf-8 -*-
"""tarea Descomprimir — paquete vertical: motor, pestana, ayuda y DESCRIPTOR.

Gemela de Comprimir: consume el artefacto "zip_anidado". Comparte con su gemela
la marca `tasks/formatos/formato_zip` (no importa a la gemela).
"""
from __future__ import annotations

from core.registro import DescriptorTarea
from tasks.descomprimir.pestana import PestanaDescomprimir
from tasks.descomprimir.ayuda import SECCIONES

DESCRIPTOR = DescriptorTarea(
    id="descomprimir",
    nombre="Descomprimir",
    clase=PestanaDescomprimir,
    consume="zip_anidado",
    ayuda=SECCIONES,
)
