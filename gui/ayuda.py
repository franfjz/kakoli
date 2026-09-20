# -*- coding: utf-8 -*-
"""ayuda — texto GENERAL de la vista de Ayuda (intro + cierre). Las secciones de
cada tarea viven en su carpeta (`tasks/<tarea>/ayuda.py`) y llegan por su DESCRIPTOR;
`AYUDA_TAREAS` queda como punto de extensión (vacío tras la migración).

Cada sección es (título, [párrafos]); un párrafo que empieza por dos espacios se
pinta en gris. App compone la Ayuda así: AYUDA_INTRO + (por cada tarea del
registro: su `descriptor.ayuda` si lo trae, si no `AYUDA_TAREAS[id]`) + AYUDA_CIERRE.
A medida que cada tarea migra, su sección sale de aquí (AYUDA_TAREAS mengua) y
pasa a `tasks/<tarea>/ayuda.py`.
"""
from __future__ import annotations

AYUDA_INTRO: "list[tuple[str, list[str]]]" = [
    ("Cómo funciona la aplicación", [
        "Las tareas se agrupan en categorías. En la portada eliges una categoría "
        "(un recuadro) y dentro cambias entre sus tareas con las pestañas de arriba; "
        "la pestaña «←» vuelve a la portada.",
        "A la derecha, un panel COMÚN a todas las tareas: el equipo detectado, las "
        "opciones de Rendimiento (Hilos y Modo ligero), la consola y la versión. En "
        "Windows, ese panel incluye también los botones de la ventana (minimizar, "
        "maximizar/restaurar y cerrar): la app usa su propia barra de título.",
        "Solo se ejecuta UNA tarea a la vez. Mientras trabaja puedes Pausar (se para "
        "de forma ordenada) y luego Continuar. Muchas tareas se pueden REANUDAR aunque "
        "cierres el programa (ver la última sección).",
    ]),
    ("Elegir carpetas y atajos", [
        "Para indicar una carpeta puedes escribir la ruta, pulsar «Examinar…» o "
        "ARRASTRAR la carpeta desde el Explorador y soltarla sobre el recuadro de la "
        "zona de rutas (siempre visible).",
        "Renombrar y Eliminar aceptan VARIAS carpetas a la vez: se listan, una por "
        "línea, y se procesan en el orden en que las añades.",
        "Atajos de teclado sobre la tarea visible:",
        "• Ctrl+Intro: Iniciar / Continuar     • Ctrl+P: Pausar",
        "• Ctrl+.: Cancelar                     • Esc: volver al menú (o cerrar la Ayuda)",
    ]),
]

# Secciones por tarea NO migrada (clave = id de la tarea). Todas las tareas ya
# migraron a tasks/<tarea>/ y aportan su Ayuda por su DESCRIPTOR, así que está vacío
# (se mantiene como punto de extensión / compatibilidad).
AYUDA_TAREAS: "dict[str, list[tuple[str, list[str]]]]" = {}

AYUDA_CIERRE: "list[tuple[str, list[str]]]" = [
    ("Rendimiento y reanudación", [
        "Rendimiento (panel derecho, común a todas las tareas):",
        "• Hilos: «Auto» deja que el programa decida según el equipo; un número lo "
        "fuerza. En discos lentos o pocos núcleos, más hilos puede ir más lento (por eso "
        "algunos aparecen atenuados).",
        "• Modo ligero: baja la prioridad del proceso para que el equipo siga usable.",
        "Reanudar tras cerrar: si pausas y cierras, al volver a lanzar la MISMA tarea con "
        "el mismo origen/destino se puede continuar donde se quedó. Comprimir, Aplanar y "
        "Desaplanar preguntan «Continuar / Empezar de cero»; Descomprimir, Descombinar y "
        "Eliminar continúan solos saltando lo ya hecho.",
    ]),
]
