# -*- coding: utf-8 -*-
"""ayuda — sección de la vista de Ayuda de la tarea Aplanar."""
from __future__ import annotations

SECCIONES: "list[tuple[str, list[str]]]" = [
    ("Aplanado · Aplanar", [
        "Copia TODOS los archivos de un árbol a una sola carpeta (un único nivel). "
        "Siempre copia: el origen no se toca.",
        "• Al aplanar: «Incluir la ruta en el nombre» codifica las carpetas en el "
        "nombre con un separador (n1/n2/a.txt → n1-n2-a.txt) y permite luego Desaplanar; "
        "«Solo el nombre final» deja a.txt (más simple, pero NO se podrá desaplanar).",
        "• Separador de niveles: texto libre (uno o varios caracteres), por defecto «-». "
        "El mismo separador se usa para desaplanar.",
        "• Al coincidir: Renombrar (añade la carpeta padre + número), Mantener el "
        "primero o Reemplazar por criterio (el perdedor se descarta).",
        "  Reanudable: guarda «.kakoli_aplanado.json» en el destino (se borra al terminar).",
    ]),
]
