# -*- coding: utf-8 -*-
"""ejecucion — máquina de ejecución de una tarea en un hilo, con cola de eventos.
SIN Tkinter: la puede usar (y probar) cualquier consumidor.

El trabajo corre en un hilo daemon y se comunica por una `queue.Queue` con tres
tipos de evento: `("log", str)`, `("prog", (hechas, total, fraccion, etiqueta))` y
`("fin", Resultado)`. El consumidor (la GUI) drena la cola con `recoger()` —que NO
bloquea— y actualiza su interfaz. Cualquier excepción del trabajo se convierte en
`Resultado("error")` (nunca sube al consumidor).

Dos señales cooperativas, ambas vistas por el trabajo entre (y dentro de) unidades:
  - `pausar()`: para de forma ORDENADA cuando la unidad en curso termine (su avance
    queda en el registro reanudable).
  - `cancelar()`: aborta la unidad en curso y DESCARTA su fragmento a medias (el
    progreso queda en la última unidad completada). Ver `core.resultado.Cancelado`.
"""
from __future__ import annotations

import queue
import threading
from typing import Callable

from core.resultado import Resultado

# Tipos de los callbacks que recibe el trabajo (los mismos del contrato de motor).
Log = Callable[[str], None]
Progreso = Callable[[int, int, float, str], None]
Pausar = Callable[[], bool]
Cancelar = Callable[[], bool]
Trabajo = Callable[[Log, Progreso, Pausar, Cancelar], Resultado]


class Ejecucion:
    """Ciclo de vida de una tarea en un hilo + cola de eventos (sin Tkinter)."""

    def __init__(self) -> None:
        self.cola: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.pausa = threading.Event()
        self.cancela = threading.Event()
        self.hilo: "threading.Thread | None" = None

    def ocupada(self) -> bool:
        return bool(self.hilo and self.hilo.is_alive())

    def pedir_pausa(self) -> None:
        """Pausa cooperativa: el trabajo la ve por `pausar()` y para entre unidades."""
        self.pausa.set()

    def pedir_cancelar(self) -> None:
        """Cancelación cooperativa: el trabajo la ve por `cancelar()`, aborta la unidad
        en curso (descartando su fragmento) y deja el progreso en la unidad anterior."""
        self.cancela.set()

    def iniciar(self, trabajo: Trabajo) -> None:
        """Lanza `trabajo(log, progreso, pausar, cancelar) -> Resultado` en un hilo
        daemon. Encola sus eventos y, al terminar, un `("fin", Resultado)`. Cualquier
        excepción del trabajo se traduce a `Resultado("error")`."""
        self.pausa.clear()
        self.cancela.clear()

        def correr() -> None:
            try:
                res = trabajo(
                    lambda m: self.cola.put(("log", m)),
                    lambda h, t, f, e: self.cola.put(("prog", (h, t, f, e))),
                    self.pausa.is_set,
                    self.cancela.is_set)
            except Exception as e:  # noqa: BLE001 — nada debe subir al consumidor
                res = Resultado("error", mensaje=f"{type(e).__name__}: {e}")
            self.cola.put(("fin", res))

        self.hilo = threading.Thread(target=correr, daemon=True)
        self.hilo.start()

    def recoger(self) -> "tuple[list[str], tuple | None, list[Resultado]]":
        """Drena la cola SIN bloquear. Devuelve (líneas de log, último progreso,
        resultados finales). El consumidor decide qué hacer con cada cosa."""
        lineas: list[str] = []
        ultimo_progreso: "tuple | None" = None
        finales: list[Resultado] = []
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "log":
                    lineas.append(str(dato))
                elif tipo == "prog":
                    ultimo_progreso = dato        # type: ignore[assignment]
                elif tipo == "fin":
                    finales.append(dato)          # type: ignore[arg-type]
        except queue.Empty:
            pass
        return lineas, ultimo_progreso, finales
