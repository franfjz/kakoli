# -*- coding: utf-8 -*-
"""tasks — manifiesto de tareas: construye el REGISTRO (categorías → tareas) que
consume la GUI. Es la FUENTE DE VERDAD para escalar: añadir una tarea =
`tasks/<tarea>/` (motor + pestana + ayuda + DESCRIPTOR) y una línea aquí; añadir
una categoría = una `Categoria`. Cada tarea es un paquete vertical y autónomo; el
handoff entre gemelas lo casa el Registro por tipo de artefacto.
"""
from __future__ import annotations

from core.registro import Categoria, Registro

from tasks.combinar import DESCRIPTOR as COMBINAR
from tasks.descombinar import DESCRIPTOR as DESCOMBINAR
from tasks.comprimir import DESCRIPTOR as COMPRIMIR
from tasks.descomprimir import DESCRIPTOR as DESCOMPRIMIR
from tasks.aplanar import DESCRIPTOR as APLANAR
from tasks.desaplanar import DESCRIPTOR as DESAPLANAR
from tasks.renombrar import DESCRIPTOR as RENOMBRAR
from tasks.eliminar import DESCRIPTOR as ELIMINAR


REGISTRO = Registro([
    Categoria("Combinación",
              "Fundir varios árboles de directorios en uno, y deshacer la fusión.",
              (COMBINAR, DESCOMBINAR)),
    Categoria("Compresión",
              "Comprimir una carpeta en ZIPs anidados y volver a extraerla.",
              (COMPRIMIR, DESCOMPRIMIR)),
    Categoria("Aplanado",
              "Llevar todos los archivos a una sola carpeta, y reconstruir el árbol.",
              (APLANAR, DESAPLANAR)),
    Categoria("Renombrado",
              "Renombrar archivos en bloque: prefijo, reemplazo interno y sufijo.",
              (RENOMBRAR,)),
    Categoria("Eliminar",
              "Borrado definitivo y recursivo (no pasa por la papelera).",
              (ELIMINAR,)),
])
