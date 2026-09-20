# -*- coding: utf-8 -*-
"""tarea Aplanar — paquete vertical: motor, pestana, ayuda y DESCRIPTOR.

Gemela de Desaplanar: produce el artefacto "carpeta_aplanada" (el handoff lo casa
el Registro). Comparte con su gemela el códec `tasks/formatos/nombres_aplanado`.
"""
from __future__ import annotations

from core.registro import DescriptorTarea
from tasks.aplanar.pestana import PestanaAplanar
from tasks.aplanar.ayuda import SECCIONES

DESCRIPTOR = DescriptorTarea(
    id="aplanar",
    nombre="Aplanar",
    clase=PestanaAplanar,
    produce="carpeta_aplanada",
    ayuda=SECCIONES,
)
