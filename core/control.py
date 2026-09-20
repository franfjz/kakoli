# -*- coding: utf-8 -*-
"""control — señales de parada COMUNES del bucle de proceso de los motores.

Centraliza el patrón que cada motor repetía en su bucle (T3): comprobar en cada
frontera de unidad si hay que PARAR y por qué —cancelación del usuario, pausa del
usuario, archivo `PAUSA` en disco o límite de unidades— y traducirlo al estado del
`Resultado` (`"pausado"` | `"cancelado"`). Así el criterio, la precedencia
(cancelar > pausar) y los mensajes viven en un solo sitio.

Uso SECUENCIAL:
    ctrl = Control(pausar=pausar, cancelar=cancelar, pausa_ruta=ruta,
                   limite=opts.max_dirs, contador=lambda: procesadas,
                   nombre_unidad="carpetas")
    for unidad in ...:
        if ctrl.debe_parar():
            break
        ...  # procesar la unidad; actualizar el contador
    if ctrl.motivo:
        return Resultado(ctrl.estado, ...)

Uso PARALELO (con core.paralelo.Ejecutor): `debe_pausar` es el callback de pausa que
espera el Ejecutor (la cancelación va por su parámetro `cancelar`), y `desde_ejecutor`
traduce el estado que devuelve:
    ctrl.desde_ejecutor(
        ejec.ejecutar(plan, trabajo, ctrl.debe_pausar, cancelar=cancelar))
    if ctrl.motivo:
        return Resultado(ctrl.estado, ...)
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable


class Control:
    """Comprueba las causas de parada comunes y recuerda el motivo y si fue cancelación.

    `contador()` devuelve cuántas unidades se llevan hechas (para el límite); en modo
    paralelo lo llaman varios hilos, así que basta con que sea una lectura barata (el
    límite es aproximado, como antes)."""

    def __init__(self, *, pausar: "Callable[[], bool] | None" = None,
                 cancelar: "Callable[[], bool] | None" = None,
                 pausa_ruta: "Path | None" = None,
                 limite: int = 0,
                 contador: "Callable[[], int] | None" = None,
                 nombre_unidad: str = "unidades") -> None:
        self._pausar = pausar or (lambda: False)
        self._cancelar = cancelar or (lambda: False)
        self._pausa_ruta = pausa_ruta
        self._limite = limite
        self._contador = contador or (lambda: 0)
        self._nombre_unidad = nombre_unidad
        self.motivo = ""
        self.cancelado = False

    # ---------------- consultas de parada ----------------
    def debe_pausar(self) -> bool:
        """¿Hay que PAUSAR? (pausa del usuario, archivo PAUSA o límite de unidades).
        Fija `motivo`. Es el callback de pausa que espera `paralelo.Ejecutor`; la
        cancelación va aparte (parámetro `cancelar` del Ejecutor)."""
        if self._pausar():
            self.motivo = "Pausado a petición del usuario."
            return True
        if self._pausa_ruta is not None and self._pausa_ruta.exists():
            self.motivo = (f"Pausado: existe el archivo {self._pausa_ruta.name} "
                           f"(bórralo para continuar).")
            return True
        if self._limite and self._contador() >= self._limite:
            self.motivo = (f"Pausado: alcanzado el límite de {self._limite} "
                           f"{self._nombre_unidad}.")
            return True
        return False

    def debe_parar(self) -> bool:
        """¿Hay que PARAR ya (bucle secuencial)? La cancelación tiene prioridad sobre
        la pausa. Fija `motivo` y `cancelado`."""
        if self._cancelar():
            self.cancelado = True
            self.motivo = "Cancelado a petición del usuario."
            return True
        return self.debe_pausar()

    def desde_ejecutor(self, resultado: str) -> None:
        """Traduce el estado que devuelve `Ejecutor.ejecutar` ('ok'|'pausado'|
        'cancelado') a `motivo`/`cancelado` (para el camino paralelo)."""
        if resultado == "cancelado":
            self.cancelado = True
            if not self.motivo:
                self.motivo = "Cancelado a petición del usuario."
        elif resultado == "pausado" and not self.motivo:
            self.motivo = "Pausado a petición del usuario."

    @property
    def estado(self) -> str:
        """'cancelado' si hubo cancelación; si no, 'pausado'."""
        return "cancelado" if self.cancelado else "pausado"
