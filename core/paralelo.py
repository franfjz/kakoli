#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
paralelo.py — Pool de trabajadores genérico y reutilizable (Fase 3 del roadmap).

Saca TODA la orquestación de hilos fuera de los motores. El motor ya no toca
`threading`: le pide un Ejecutor a este módulo y unos datos a recursos.py.

Reparte de un modo muy concreto:
  - Un "plan" (Plan) dice qué unidades están LISTAS en cada momento (en
    comprimir, las carpetas cuyos hijos ya se comprimieron; en descomprimir,
    los .zip contenedores que han ido apareciendo).
  - Una "función de trabajo" hace lo pesado con cada unidad (comprimir/extraer).
    Corre en un worker y LIBERA EL GIL en la parte de zlib y de E/S, así que hay
    aceleración real de CPU.
  - El Ejecutor se encarga de lo transversal: repartir, esperar a que se liberen
    dependencias, PAUSAR, CANCELAR y propagar el PRIMER error que ocurra.

Por qué aquí y no en el Planificador de motor_comprimir:
  el Planificador es LÓGICA DE DOMINIO (dependencias padre/hijo del árbol). La
  COORDINACIÓN entre hilos (esperar, despertar, parar) es genérica y va aquí.
  El mismo Ejecutor sirve para la descompresión (Fase 6) sin duplicar código.

El Plan debe ser seguro entre hilos por su cuenta (tener su propio cerrojo):
el Planificador de motor_comprimir ya lo es.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Protocol, runtime_checkable

from core.resultado import Cancelado


@runtime_checkable
class Plan(Protocol):
    """Lo que el Ejecutor espera de un planificador (dominio de cada motor)."""
    restantes: int

    def siguiente(self) -> object | None:
        """Devuelve una unidad LISTA para procesar, o None si ahora mismo no hay
        ninguna. NO bloquea. Debe entregar cada unidad una sola vez."""
        ...

    def terminada(self, item: object) -> None:
        """Marca `item` como hecho; puede liberar nuevas unidades listas."""
        ...


class PlanLista:
    """Plan LISTO PARA USAR cuando las unidades son INDEPENDIENTES entre sí (sin
    dependencias): entrega los items de una lista uno a uno y cuenta las
    terminadas. Es el patrón habitual de una transformación que se aplica a cada
    subcarpeta por separado — así un motor nuevo no reimplementa un Plan trivial.

    Para dependencias (padre/hijo del árbol de ZIPs, o cola dinámica de la
    descompresión) siguen usándose los planes de dominio de cada motor
    (`Planificador`, `_PlanDescomp`). Seguro entre hilos (cerrojo propio).

    Uso:
        Ejecutor(n).ejecutar(PlanLista(subcarpetas), trabajo=aplicar_a_una,
                             pausar=debe_pausar)
    """

    def __init__(self, items) -> None:
        self._items = list(items)
        self._i = 0
        self._pendientes = len(self._items)
        self._lock = threading.Lock()

    @property
    def restantes(self) -> int:
        with self._lock:
            return self._pendientes

    def siguiente(self) -> object | None:
        with self._lock:
            if self._i >= len(self._items):
                return None
            item = self._items[self._i]
            self._i += 1
            return item

    def terminada(self, item: object) -> None:
        with self._lock:
            self._pendientes -= 1


class Ejecutor:
    """
    Reparte las unidades listas del plan entre `hilos` trabajadores.

    `trabajo(item)` corre en un worker y NO debe tocar la GUI directamente (usa
    los callbacks log/progreso, que ya son seguros entre hilos porque escriben
    en una cola). No se sostiene ningún cerrojo mientras corre `trabajo`, que es
    justo la parte donde queremos concurrencia real.
    """

    def __init__(self, hilos: int) -> None:
        self.hilos = max(1, hilos)
        self._cond = threading.Condition()
        self._en_vuelo = 0
        self._parar = False
        self._cancelado = False
        self._error: BaseException | None = None
        # Throttling (Fase 8): nº máximo de workers activos a la vez. Un
        # regulador externo puede bajarlo si el equipo se ocupa; los workers
        # sobrantes duermen hasta que el límite vuelva a subir.
        self._activos_max = self.hilos

    def ajustar_limite(self, objetivo: int) -> None:
        """Fija cuántos workers pueden estar ACTIVOS a la vez (throttling). Lo llama el
        regulador externo: si sube el límite, despierta a los workers que dormían; si
        baja, los sobrantes se dormirán al terminar su unidad. Seguro entre hilos y
        acotado a [1, hilos]."""
        objetivo = max(1, min(self.hilos, int(objetivo)))
        with self._cond:
            if objetivo != self._activos_max:
                self._activos_max = objetivo
                self._cond.notify_all()

    def pedir_parada(self) -> None:
        """Cancelación externa (Ctrl+C, archivo PAUSA, botón): los workers
        terminan la unidad en curso y salen ordenadamente."""
        with self._cond:
            self._parar = True
            self._cond.notify_all()

    def ejecutar(self, plan: Plan,
                 trabajo: Callable[[object], None],
                 pausar: Callable[[], bool] | None = None,
                 limite_activos: Callable[[], int] | None = None,
                 intervalo: float = 1.0,
                 cancelar: Callable[[], bool] | None = None) -> str:
        """
        Corre hasta agotar el plan, hasta una pausa/cancelación, o hasta el
        primer error. Devuelve 'ok' | 'pausado' | 'cancelado'. Si hubo error, lo relanza.

        `pausar()`: ningún worker toma NUEVAS unidades; las en vuelo terminan.
        `cancelar()`: además, si el `trabajo` lo comprueba por dentro, aborta la unidad
        en curso lanzando `core.resultado.Cancelado` (que aquí es parada LIMPIA, no error);
        afecta a TODOS los workers. Cancelar tiene prioridad sobre pausar.

        `limite_activos` (Fase 8): función opcional que devuelve cuántos workers
        deberían estar activos AHORA (según la carga del sistema). Se consulta
        cada `intervalo` segundos desde un hilo regulador; si baja, algún worker
        se duerme para ceder CPU. Sin ella, trabajan los `hilos` de siempre.
        """
        pausar = pausar or (lambda: False)
        cancelar = cancelar or (lambda: False)

        def parar_ya() -> bool:
            return self._parar or self._cancelado or self._error is not None \
                or cancelar() or pausar()

        def worker() -> None:
            while True:
                with self._cond:
                    while True:
                        if parar_ya():
                            return
                        # Throttling: si ya hay bastantes activos, dormir.
                        if self._en_vuelo >= self._activos_max:
                            if plan.restantes == 0 and self._en_vuelo == 0:
                                self._cond.notify_all()
                                return
                            self._cond.wait(timeout=0.2)
                            continue
                        item = plan.siguiente()
                        if item is not None:
                            self._en_vuelo += 1
                            break
                        # No hay nada listo ahora mismo.
                        if plan.restantes == 0 and self._en_vuelo == 0:
                            self._cond.notify_all()   # despierta a los demás
                            return
                        # Se re-evalúa pausar()/cancelar()/parar con un timeout corto:
                        # una pausa/cancelación se atiende sin esperar a liberar trabajo.
                        self._cond.wait(timeout=0.2)

                # --- parte pesada: SIN cerrojo (zlib/E-S liberan el GIL) ---
                try:
                    trabajo(item)
                except Cancelado:                     # parada LIMPIA (no error)
                    with self._cond:
                        self._cancelado = True
                        self._cond.notify_all()
                    return
                except BaseException as e:            # noqa: BLE001
                    with self._cond:
                        if self._error is None:
                            self._error = e
                        self._cond.notify_all()
                    return
                finally:
                    with self._cond:
                        plan.terminada(item)   # puede liberar nuevas listas
                        self._en_vuelo -= 1
                        self._cond.notify_all()

        regulador = None
        if limite_activos is not None:
            # Fija el límite inicial ya, antes de arrancar (sin pico de salida).
            try:
                self.ajustar_limite(limite_activos())
            except Exception:                     # noqa: BLE001
                self.ajustar_limite(self.hilos)
            regulador = _Regulador(self, limite_activos, intervalo)
            regulador.start()
        try:
            with ThreadPoolExecutor(max_workers=self.hilos) as ex:
                futuros = [ex.submit(worker) for _ in range(self.hilos)]
                for f in futuros:
                    f.result()   # relanza cualquier fallo interno del worker
        finally:
            if regulador is not None:
                regulador.parar()
                regulador.join(timeout=1.0)

        if self._error is not None:
            raise self._error
        if self._cancelado or cancelar():
            return "cancelado"                # cancelar tiene prioridad sobre pausar
        return "pausado" if (self._parar or pausar()) else "ok"


class _Regulador(threading.Thread):
    """
    Hilo que ajusta Ejecutor._activos_max según lo que diga `limite()` cada
    `intervalo` segundos. Vive solo mientras dura ejecutar(). Que `limite()`
    haga la medición (posiblemente lenta) aquí y no en los workers.
    """

    def __init__(self, ejec: "Ejecutor", limite: Callable[[], int],
                 intervalo: float) -> None:
        super().__init__(daemon=True)
        self._ejec = ejec
        self._limite = limite
        self._intervalo = max(0.2, intervalo)
        self._fin = threading.Event()

    def run(self) -> None:
        while not self._fin.is_set():
            try:
                objetivo = int(self._limite())
            except Exception:                     # noqa: BLE001
                objetivo = self._ejec.hilos
            self._ejec.ajustar_limite(objetivo)   # encapsulado (no toca privados)
            self._fin.wait(self._intervalo)

    def parar(self) -> None:
        self._fin.set()
