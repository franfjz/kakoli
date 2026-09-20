# -*- coding: utf-8 -*-
"""ayuda — sección de la vista de Ayuda de la tarea Descombinar."""
from __future__ import annotations

SECCIONES: "list[tuple[str, list[str]]]" = [
    ("Combinación · Descombinar", [
        "Deshace una combinación: lee el índice del directorio combinado y reconstruye "
        "los directorios originales (uno por origen) con sus nombres originales.",
        "Necesita que el directorio tenga índice de combinación. Los archivos "
        "descartados por «Reemplazar» no se pueden recuperar.",
        "  Consejo: un directorio combinado se puede copiar a otro sitio y seguirá "
        "siendo descombinable (el índice viaja dentro).",
    ]),
]
