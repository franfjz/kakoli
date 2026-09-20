# -*- coding: utf-8 -*-
"""Humo de la consola de Descomprimir: `python -m tasks.descomprimir.motor --help`."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[3]


def test_help_arranca():
    proc = subprocess.run(
        [sys.executable, "-m", "tasks.descomprimir.motor", "--help"],
        cwd=_RAIZ, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "usage" in proc.stdout.lower()
