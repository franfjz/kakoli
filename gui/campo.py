# -*- coding: utf-8 -*-
"""campo — un campo de entrada declarativo de una pestaña."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Campo:
    """Un campo de entrada de una pestaña (E del plan de escalabilidad).
    `tipo`: 'carpeta' | 'archivo' | 'carpeta_salida' | 'texto' | 'lista'.
    `filtros`: para 'archivo', lista de (etiqueta, patrón) del diálogo (None = todos).
    `titulo_dialogo`: título del diálogo de este campo (None = uno genérico)."""
    clave: str
    etiqueta: str
    tipo: str = "carpeta"
    opcional: bool = False
    filtros: "list[tuple[str, str]] | None" = None
    titulo_dialogo: "str | None" = None
