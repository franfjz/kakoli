# -*- coding: utf-8 -*-
"""ayuda — sección de la vista de Ayuda de la tarea Renombrar.

`SECCIONES` es una lista de (título, [párrafos]); un párrafo que empieza por dos
espacios se pinta en gris. La compone App junto a las demás en orden de registro.
"""
from __future__ import annotations

SECCIONES: "list[tuple[str, list[str]]]" = [
    ("Renombrado · Renombrar", [
        "Renombra archivos en bloque (en una o varias carpetas o, si lo marcas, en sus "
        "subdirectorios), SIN tocar la extensión (se conservan también las compuestas, "
        "como .tar.gz).",
        "• Varias carpetas: se listan una por línea (o se arrastran) y se procesan en orden.",
        "• Al inicio (prefijo) y Al final (sufijo): el sufijo va antes de la extensión.",
        "• Reemplazar un fragmento: sustituye «Buscar» por «Reemplazar por» dentro del "
        "nombre. Puedes distinguir mayúsculas y limitar a la primera coincidencia. "
        "Reemplazar por vacío elimina el fragmento.",
        "• Ámbito: incluir subdirectorios; omitir ocultos.",
        "• Al coincidir (el nuevo nombre ya existe): Numerar (añade _2, _3…; no se pierde "
        "nada) u Omitir.",
        "• Vista previa: muestra «antes → después» en la consola sin renombrar nada. "
        "Úsala antes: el renombrado no tiene «deshacer».",
    ]),
]
