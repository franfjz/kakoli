#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""formato — utilidades de formato y tiempo comunes a todos los motores (núcleo, sin
Tkinter y sin dependencias de dominio): tamaños legibles, duraciones y marca de tiempo.

Antes vivían en `core.comun` (un cajón de sastre); se separaron aquí (Fase 6 de
mejoras) junto con `resultado`, `opciones` y `cli`."""
from __future__ import annotations

from datetime import datetime, timezone

# Cada cuántas unidades vuelca su progreso a disco un proceso reanudable (flush por
# bloques): un corte abrupto rehace como mucho este número de unidades. Lo usan el
# registro reanudable (core.reanudable) y los motores para el ritmo de sus mensajes.
PASO_REGISTRO = 50


def humano(n: float) -> str:
    """Tamaño en bytes como texto legible (B/KB/MB/…)."""
    unidades = ["B", "KB", "MB", "GB", "TB", "PB"]
    i, v = 0, float(n)
    while v >= 1024 and i < len(unidades) - 1:
        v /= 1024
        i += 1
    return f"{v:.0f} {unidades[i]}" if i == 0 else f"{v:.2f} {unidades[i]}"


def duracion(seg: float) -> str:
    """Segundos como duración corta ('5s', '1m 05s', '1h 01m')."""
    seg = int(max(0, seg))
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{h}h {m:02d}m" if h else (f"{m}m {s:02d}s" if m else f"{s}s")


def ahora() -> str:
    """Marca de tiempo local en ISO-8601 (segundos)."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
