# -*- coding: utf-8 -*-
"""ayuda — sección de la vista de Ayuda de la tarea Eliminar."""
from __future__ import annotations

SECCIONES: "list[tuple[str, list[str]]]" = [
    ("Eliminar", [
        "Borra una o varias carpetas y todo su contenido de forma DEFINITIVA y "
        "recursiva. NO pasa por la papelera de reciclaje: no se puede recuperar.",
        "• Varias carpetas: se listan una por línea (o se arrastran) y se borran en orden.",
        "• Simular: recorre y muestra qué se borraría, sin borrar nada. Úsalo antes.",
    ]),
]
