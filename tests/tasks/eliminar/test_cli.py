# -*- coding: utf-8 -*-
"""Humo de la consola de Eliminar: `python -m tasks.eliminar.motor` arranca y
--help funciona; --simular no borra nada."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[3]


def test_help_arranca():
    proc = subprocess.run(
        [sys.executable, "-m", "tasks.eliminar.motor", "--help"],
        cwd=_RAIZ, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "usage" in proc.stdout.lower()


def test_simular_no_borra(tmp_path):
    objetivo = tmp_path / "victima"
    objetivo.mkdir()
    (objetivo / "a.txt").write_text("x")
    proc = subprocess.run(
        [sys.executable, "-m", "tasks.eliminar.motor", str(objetivo), "--simular", "-y"],
        cwd=_RAIZ, capture_output=True, text=True)
    assert proc.returncode == 0
    assert objetivo.exists()                      # simular no borra
