# -*- coding: utf-8 -*-
"""ayuda — sección de la vista de Ayuda de la tarea Comprimir."""
from __future__ import annotations

SECCIONES: "list[tuple[str, list[str]]]" = [
    ("Compresión · Comprimir", [
        "Comprime una carpeta en ZIPs anidados (un .zip por subcarpeta), al lado de la "
        "original. Los archivos ya comprimidos (fotos, vídeos, .zip) se guardan sin "
        "recomprimir.",
        "• Compresión: «Rápido» es lo normal; «Máximo» reduce más pero tarda mucho más.",
        "• Modo compacto: junta las carpetas pequeñas en un solo ZIP (más rápido en "
        "discos lentos), pero cambia la estructura (no podrás sacar una subcarpeta suelta).",
        "• Verificar ZIP ya hechos al reanudar: comprueba los ZIP creados y rehace los "
        "dañados. Borrar ZIP intermedios: deja solo el ZIP final.",
        "  Es reanudable: guarda «_estado_zip.jsonl» en la carpeta de salida.",
    ]),
]
