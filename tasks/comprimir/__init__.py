# -*- coding: utf-8 -*-
"""tarea Comprimir — paquete vertical: motor, pestana, ayuda y DESCRIPTOR.

Gemela de Descomprimir: produce el artefacto "zip_anidado". Comparte con su
gemela la marca `tasks/formatos/formato_zip` (no importa a la gemela).
"""
from __future__ import annotations

from core.registro import DescriptorTarea
from tasks.comprimir.pestana import PestanaComprimir
from tasks.comprimir.ayuda import SECCIONES

DESCRIPTOR = DescriptorTarea(
    id="comprimir",
    nombre="Comprimir",
    clase=PestanaComprimir,
    produce="zip_anidado",
    ayuda=SECCIONES,
)
