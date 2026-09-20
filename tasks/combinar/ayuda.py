# -*- coding: utf-8 -*-
"""ayuda — sección de la vista de Ayuda de la tarea Combinar."""
from __future__ import annotations

SECCIONES: "list[tuple[str, list[str]]]" = [
    ("Combinación · Combinar", [
        "Funde varios directorios DENTRO de un directorio principal (in situ: el "
        "principal cambia). Si coinciden nombre y nivel de carpeta, se unen los "
        "contenidos. Usa una carpeta vacía como principal si quieres conservar las fuentes.",
        "Entradas: el Directorio principal, un Directorio a combinar y, con el botón, "
        "una lista de más directorios (uno por línea). Todos deben existir.",
        "• Al coincidir (mismo nombre y ruta): Renombrar (conserva ambos, añade un "
        "código de origen al entrante), Mantener (deja el del principal) o Reemplazar "
        "(gana uno por criterio; el perdedor se descarta, IRREVERSIBLE).",
        "• Código de origen: nombre de la carpeta, id corto (_d1, _d2…) o personalizado.",
        "• Crear índice para poder deshacer: guarda «.kakoli_combinacion.json» en el "
        "principal. Sin índice es más rápido y ocupa menos, pero NO se podrá descombinar.",
    ]),
]
