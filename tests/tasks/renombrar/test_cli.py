# -*- coding: utf-8 -*-
"""Humo de la consola de Renombrar: `python -m tasks.renombrar.motor` arranca y
--help funciona (la tarea es un CLI autónomo tras la migración)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[3]


def test_help_arranca():
    proc = subprocess.run(
        [sys.executable, "-m", "tasks.renombrar.motor", "--help"],
        cwd=_RAIZ, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "usage" in proc.stdout.lower()


def test_simular_no_toca_disco(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    proc = subprocess.run(
        [sys.executable, "-m", "tasks.renombrar.motor", str(tmp_path),
         "--prefijo", "p_", "--simular", "-y"],
        cwd=_RAIZ, capture_output=True, text=True)
    assert proc.returncode == 0
    assert (tmp_path / "a.txt").exists()          # simular no renombra
    assert not (tmp_path / "p_a.txt").exists()
