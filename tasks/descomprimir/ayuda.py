# -*- coding: utf-8 -*-
"""ayuda — sección de la vista de Ayuda de la tarea Descomprimir."""
from __future__ import annotations

SECCIONES: "list[tuple[str, list[str]]]" = [
    ("Compresión · Descomprimir", [
        "Extrae un ZIP anidado reconstruyendo el árbol original (proceso inverso a "
        "Comprimir).",
        "• Sobrescribir: rehace la carpeta de destino si ya existe. Sin marcar, salta "
        "las carpetas que ya estén completas (así reanuda por el propio destino).",
    ]),
]
