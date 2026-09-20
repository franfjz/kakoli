# -*- coding: utf-8 -*-
"""Punto de entrada de `python -m core.recursos` (diagnóstico del perfil)."""
import sys

from core.recursos.sondas import main

if __name__ == "__main__":
    sys.exit(main())
