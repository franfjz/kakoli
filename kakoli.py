#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
kakoli.py — Punto de entrada de la aplicación: herramientas de gestión de
directorios y archivos (GUI Tkinter). Es la RAÍZ DE COMPOSICIÓN: arma la ventana
`App` con el `REGISTRO` de tareas y arranca el bucle.

El código está organizado en paquetes por responsabilidad:

    core/    núcleo estable, agnóstico de dominio y de la GUI (comun, recursos,
             paralelo, registro, ejecucion); solo stdlib, sin Tkinter.
    gui/     estructura general de la interfaz (tema, App, PestanaBase, componentes,
             contexto, Campo, constantes, ayuda); no conoce las tareas concretas.
    tasks/   el manifiesto (REGISTRO) + una carpeta por tarea (tasks/<tarea>/:
             motor + pestana + ayuda + DESCRIPTOR) y los formatos compartidos
             entre gemelas (tasks/formatos/).

Cadena de dependencias: core ← gui ← tasks ← kakoli. Añadir una tarea es crear su
carpeta en tasks/ y una línea en tasks/__init__.py; no se toca core/ ni gui/.

Lanzar:      python kakoli.py
Ejecutable:  .\build_nuitka.ps1   (Nuitka onefile con las fuentes y el icono)
"""
from __future__ import annotations

import sys
import tkinter as tk

from gui.app import App
from gui.constantes import VERSION
from tasks import REGISTRO


def main() -> int:
    # `--version` no abre la ventana (útil para comprobar el arranque del paquete).
    if "--version" in sys.argv[1:]:
        print(f"kakoli {VERSION}")
        return 0
    try:
        app = App(REGISTRO)
    except tk.TclError as e:
        print(f"No se pudo abrir la ventana ({e}). Usa los motores por consola:\n"
              f"  python -m tasks.comprimir.motor CARPETA\n"
              f"  python -m tasks.descomprimir.motor ARCHIVO.zip\n"
              f"  python -m tasks.eliminar.motor CARPETA", file=sys.stderr)
        return 1
    app.activar_marco_sin_barra()      # quita la barra de título nativa (Windows)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
