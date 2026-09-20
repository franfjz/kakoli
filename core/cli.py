# -*- coding: utf-8 -*-
"""cli — arnés de línea de comandos compartido por los motores y el manejo de Ctrl+C.

Reduce el `main()` de cada motor a: parsear argumentos, construir `opts`+`entradas` y
llamar a `correr_cli`. Antes vivía en `core.comun`; se separó aquí (Fase 6 de mejoras).
"""
from __future__ import annotations

import signal
import sys

from core.resultado import EstadoResultado


def preguntar_consola(msg: str, por_defecto: bool = True) -> bool:
    """Pregunta S/N por consola. Sin terminal interactiva (o EOF), el valor por defecto."""
    if not sys.stdin.isatty():
        return por_defecto
    sufijo = "[S/n]" if por_defecto else "[s/N]"
    try:
        r = input(f"{msg} {sufijo} ").strip().lower()
    except EOFError:
        return por_defecto
    return por_defecto if not r else r in ("s", "si", "sí", "y", "yes")


class Interrupcion:
    """Ctrl+C una vez -> pausa ordenada. Dos veces -> corta ya (y limpia)."""

    def __init__(self) -> None:
        self.pedida = False
        self.veces = 0

    def instalar(self) -> None:
        signal.signal(signal.SIGINT, self._manejar)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._manejar)

    def _manejar(self, signum, frame):  # noqa: ANN001
        self.veces += 1
        self.pedida = True
        if self.veces >= 2:
            print("\n[!] Cancelando de inmediato...", file=sys.stderr)
            raise KeyboardInterrupt
        print("\n[!] Pausa pedida: se terminará la parte en curso y se guardará "
              "el avance (Ctrl+C otra vez para cortar ya).", file=sys.stderr)


def correr_cli(ejecutar, entradas: dict, opts, *, si: bool = False,
               antes: "str | None" = None) -> int:
    """Ejecuta un motor por consola con lo COMÚN a todos: instala el manejador de
    Ctrl+C, llama a `ejecutar(entradas, opts, ...)` (contrato uniforme), y traduce
    el Resultado a un código de salida.

    `si`: no preguntar (equivale a --si). `antes`: línea a imprimir antes de
    arrancar (aviso de pausa, advertencia...). Devuelve el código de salida:
    0 ok/nada, 1 error/cancelado, 2 pausado, 130 cancelado con doble Ctrl+C."""
    interr = Interrupcion()
    interr.instalar()
    if antes:
        print(antes)
    res = ejecutar(entradas, opts, log=print, pausar=lambda: interr.pedida,
                   confirmar=None if si else preguntar_consola)
    if res.estado == EstadoResultado.ERROR:
        print(f"Error: {res.mensaje}", file=sys.stderr)
        return 1
    if res.estado == EstadoResultado.PAUSADO:
        return 130 if interr.veces >= 2 else 2
    return 1 if res.estado == EstadoResultado.CANCELADO else 0
