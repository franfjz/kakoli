# -*- coding: utf-8 -*-
"""ayuda — sección de la vista de Ayuda de la tarea Desaplanar."""
from __future__ import annotations

SECCIONES: "list[tuple[str, list[str]]]" = [
    ("Aplanado · Desaplanar", [
        "Reconstruye el árbol a partir de una carpeta aplanada, SOLO por los nombres, "
        "partiendo cada nombre por el separador (último trozo = archivo, resto = carpetas).",
        "• Separador de niveles: debe coincidir con el usado al aplanar.",
        "  Aviso: es una reconstrucción por convención de nombres, no un undo exacto. Un "
        "nombre que ya contenga el separador creará carpetas no deseadas. Lo aplanado con "
        "«Solo el nombre final» no lleva ruta y quedará en la raíz.",
    ]),
]
