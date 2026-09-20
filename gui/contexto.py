# -*- coding: utf-8 -*-
"""contexto — el contrato que la ventana (App) ofrece a las pestañas de tarea.

Una pestaña no accede a los atributos internos de App (v_detallado, v_hilos…):
usa este contrato. Así la pestaña depende de un interfaz explícito y estable, no
de la implementación concreta de la ventana.
"""
from __future__ import annotations

from typing import Protocol

from core import recursos


class ContextoApp(Protocol):
    """Lo que una pestaña necesita de la ventana principal."""

    def opciones_comunes(self) -> "tuple[bool, recursos.PoliticaHilos]":
        """(detallado, política de hilos) COMUNES a todas las tareas (Hilos + Modo
        ligero + Registro detallado), leídas del monitor compartido."""
        ...

    def escribir_lote(self, lineas: list[str]) -> None:
        """Vuelca líneas al registro (consola) compartido."""
        ...

    def ultima_carpeta_dialogo(self) -> str:
        """Última carpeta usada en un diálogo Examinar (para `initialdir`; '' si no
        hay ninguna). Se recuerda entre sesiones."""
        ...

    def recordar_carpeta_dialogo(self, ruta: str) -> None:
        """Recuerda la carpeta de la última selección hecha en un diálogo."""
        ...

    def bloquear(self, activa) -> None:
        """Entra en modo 'una tarea a la vez' (deshabilita navegación y hermanas)."""
        ...

    def desbloquear(self) -> None:
        """Sale del modo 'una tarea a la vez'."""
        ...

    def sugerir_entrada(self, ruta, artefacto: str, excepto=None):
        """Handoff: ofrece una salida al consumidor de `artefacto` (o None)."""
        ...

    def comprobar_cierre(self) -> None:
        """Comprueba si la app puede cerrarse (tras pausar por cierre)."""
        ...
