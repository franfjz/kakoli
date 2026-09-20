# -*- coding: utf-8 -*-
"""test_pyflakes_baseline — trinquete de análisis estático.

pyflakes sobre TODO el código de producción (`core gui tasks kakoli.py`). Desde la
Fase 0 de mejoras el trinquete es ESTRICTO: pyflakes no debe emitir NINGÚN aviso.

Cubre, sin distinguir categoría:
  - nombres indefinidos (`undefined name`): un símbolo usado y no definido/importado
    (el bug real P2 era de este tipo);
  - imports sin usar (`imported but unused`, F401);
  - variables locales asignadas y no usadas (`assigned to but never used`, F841).

Antes solo se vigilaban los nombres indefinidos y se ignoraban los imports sin usar
"por re-exports de compatibilidad": tras retirar la estructura antigua (Fase 13 de la
reestructuración) ya no hay tales re-exports, así que la línea base es la salida VACÍA.
El test falla en cuanto aparece cualquier aviso nuevo (regresión).

Además se corrige un fallo del propio trinquete: antes escaneaba `motores` y `clases`
—carpetas eliminadas en la Fase 13—, con lo que pyflakes fallaba en silencio (por
stderr, que no se leía) y NO cubría `tasks/`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent

# Paquetes de producción a analizar (los de test quedan fuera a propósito).
_OBJETIVOS = ["core", "gui", "tasks", "kakoli.py"]

_PATRON_INDEF = re.compile(
    r"^(?P<archivo>.+?):\d+:\d+: undefined name '(?P<nombre>[^']+)'")


def _pyflakes() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pyflakes", *_OBJETIVOS],
        cwd=_RAIZ, capture_output=True, text=True)


def test_pyflakes_sin_avisos():
    """Trinquete estricto: pyflakes no debe emitir NINGÚN aviso en producción."""
    proc = _pyflakes()
    avisos = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert not avisos, (
        "pyflakes encontró avisos en el código de producción "
        "(imports muertos, nombres indefinidos, variables sin usar):\n"
        + "\n".join(avisos))
    # stderr no vacío delataría rutas inexistentes (el fallo histórico del test).
    assert not proc.stderr.strip(), f"pyflakes error: {proc.stderr.strip()}"


def test_sin_nombres_indefinidos():
    """Guarda específico contra nombres indefinidos (incluye el bug P2 de la Fase 3)."""
    proc = _pyflakes()
    indefinidos = [ln for ln in proc.stdout.splitlines()
                   if _PATRON_INDEF.match(ln.strip())]
    assert not indefinidos, f"Nombres indefinidos: {indefinidos}"


def test_p2_corregido():
    """El bug P2 (threading indefinido en Descomprimir) quedó corregido en la Fase 3."""
    proc = _pyflakes()
    for linea in proc.stdout.splitlines():
        m = _PATRON_INDEF.match(linea.strip())
        if m:
            archivo = m.group("archivo").replace("\\", "/")
            assert not (archivo == "tasks/descomprimir/pestana.py"
                        and m.group("nombre") == "threading")
