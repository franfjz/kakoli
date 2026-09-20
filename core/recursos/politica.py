# -*- coding: utf-8 -*-
"""politica — política de rendimiento COMÚN a todas las tareas (subpaquete recursos).

A partir del `PerfilSistema` que mide `core.recursos.sondas`, decide cuántos hilos
usar (`calcular_hilos`/`techo_hilos`), el throttling adaptativo
(`objetivo_activos`/`regulador_carga`) y ofrece el punto de entrada común
`preparar()`. Es el criterio de rendimiento; se puede testear sin tocar hardware
pasándole un `PerfilSistema` construido a mano.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.recursos.sondas import (
    MB, bajar_prioridad, medidor_carga_externa, perfil, resumen, _tiempos_cpu)

if TYPE_CHECKING:
    from core.recursos.sondas import PerfilSistema


@dataclass
class PoliticaHilos:
    """
    Ajustes de rendimiento COMPARTIDOS por comprimir/descomprimir/eliminar.
    Cada motor lleva uno en sus Opciones; así el criterio es común y se toca en
    un solo sitio. Los valores son puntos de partida (la Fase 8 los afina).
    """
    hilos: int = 0                    # 0 = automático; >0 = lo fuerza el usuario
    hilos_max: int = 8                # tope absoluto (evita paliza de E/S)
    ram_por_hilo_mb: int = 128        # colchón por hilo (medido real ~0.5 MB;
                                      #   128 sigue siendo muy conservador, Fase 8)
    ram_reservada_mb: int = 0         # 0 = adaptativo: max(512, 20% de RAM total)
    ram_minima_paralelo_mb: int = 1024  # por debajo -> secuencial
    prioridad_baja: bool = True       # modo ligero por defecto
    throttling: bool = True           # ceder CPU si el equipo se ocupa (Fase 8)


def calcular_hilos(p: PerfilSistema, pol: PoliticaHilos,
                   unidades: int = 0) -> int:
    """
    Nº de hilos a usar. `unidades` = tareas realmente disponibles (no tiene
    sentido tener más hilos que carpetas/zips por procesar).

    Combina CPU (dejando un núcleo libre y sin pasar de los núcleos FÍSICOS),
    RAM disponible (con colchón), y baja o cae a secuencial ante señales de
    apuro: poca RAM, swap en uso, HDD (más si origen y destino comparten disco),
    unidad de red/USB, otros procesos ya ocupando CPU (carga externa), batería o
    proceso de 32 bits. Ante la duda, conservador.
    """
    if pol.hilos > 0:                      # el usuario lo forzó: se respeta
        base = pol.hilos
    else:
        cpu = p.cpu
        # 1) Límite por CPU, dejando un núcleo libre si hay pocos.
        por_cpu = 1 if cpu <= 2 else cpu - 1
        # No más hilos CPU-bound que núcleos físicos reales (SMT no dobla).
        if p.cpu_fisicos:
            por_cpu = min(por_cpu, p.cpu_fisicos)
        por_cpu = min(por_cpu, pol.hilos_max or por_cpu)

        # 2) Límite por RAM disponible (si la conocemos).
        if p.ram_disponible > 0:
            reserva = (pol.ram_reservada_mb * MB
                       or max(512 * MB, int(p.ram_total * 0.20)))
            util = max(0, p.ram_disponible - reserva)
            por_ram = max(1, util // (max(1, pol.ram_por_hilo_mb) * MB))
        else:
            por_ram = 2                    # RAM desconocida -> prudencia
        # Proceso de 32 bits: espacio de direcciones ~2-4 GB, no te pases.
        if not p.proceso_64bit:
            por_ram = min(por_ram, 2)

        base = max(1, min(por_cpu, por_ram))

        # 3) Poca RAM libre o swap en uso -> secuencial, pase lo que pase.
        if 0 < p.ram_disponible < pol.ram_minima_paralelo_mb * MB:
            base = 1
        if p.swap_usado > 0:
            base = 1

        # 4) Penalizaciones por E/S y estado (cada una a la mitad, mín. 1).
        if p.disco_lento is True and base > 1:      # HDD: saltos de cabezal
            base = max(1, base // 2)
            # Leer del origen y escribir los ZIP en el MISMO disco mecánico a la
            # vez es el peor caso (el cabezal salta entre lectura y escritura):
            # otra mitad. En discos distintos, las dos corrientes no compiten.
            if p.mismo_volumen and base > 1:
                base = max(1, base // 2)
        if p.tipo_unidad in ("red", "extraible") and base > 1:
            base = max(1, base // 2)
        # Otros procesos ya ocupan CPU al arrancar -> empezar con menos hilos.
        # Mismo criterio y umbral que el throttling en marcha (carga EXTERNA).
        if (p.carga_externa is not None
                and p.carga_externa >= UMBRAL_EXTERNO_SUAVE and base > 1):
            base = max(1, base // 2)
        if p.energia == "bateria" and base > 2:
            base = 2                                 # con batería, suave

    # 5) Nunca más hilos que tareas disponibles.
    if unidades > 0:
        base = min(base, unidades)
    return max(1, int(base))


def techo_hilos(p: PerfilSistema, pol: "PoliticaHilos | None" = None) -> int:
    """Máximo de hilos que la máquina puede APROVECHAR por sus características
    ESTABLES (núcleos y tipo de disco), ignorando lo volátil (RAM libre del
    momento, carga, swap). Para la GUI: por encima de este techo, más hilos
    suelen PERJUDICAR el rendimiento en ESTE equipo, así que se muestran pero no
    se dejan elegir. Siempre >= 1."""
    pol = pol or PoliticaHilos()
    cpu = p.cpu
    techo = 1 if cpu <= 2 else cpu - 1
    if p.cpu_fisicos:
        techo = min(techo, p.cpu_fisicos)
    techo = min(techo, pol.hilos_max or techo)
    if p.disco_lento is True and techo > 1:          # HDD: saltos de cabezal
        techo = max(1, techo // 2)
        if p.mismo_volumen and techo > 1:            # mismo disco: peor
            techo = max(1, techo // 2)
    if p.tipo_unidad in ("red", "extraible") and techo > 1:
        techo = max(1, techo // 2)
    return max(1, techo)


# Throttling adaptativo (Fase 8). Se regula por CARGA EXTERNA (fracción 0..1 de
# CPU que usan OTROS procesos, sin contar el nuestro): es la señal correcta de
# "el equipo se ocupa con otras cosas". Por debajo de SUAVE, a toda máquina; por
# encima de DURO, un solo worker; en medio, escala lineal.
UMBRAL_EXTERNO_SUAVE = 0.25  # otros procesos usan <25% -> pleno
UMBRAL_EXTERNO_DURO = 0.75   # otros procesos usan >75% -> un worker


def objetivo_activos(externo: float | None, hilos: int) -> int:
    """Cuántos workers deberían estar activos según la CARGA EXTERNA (0..1).
    None (no medible) o baja -> todos; alta -> se reduce hasta 1."""
    if externo is None or externo <= UMBRAL_EXTERNO_SUAVE:
        return hilos
    if externo >= UMBRAL_EXTERNO_DURO:
        return 1
    frac = ((UMBRAL_EXTERNO_DURO - externo)
            / (UMBRAL_EXTERNO_DURO - UMBRAL_EXTERNO_SUAVE))
    return max(1, min(hilos, round(hilos * frac)))


def regulador_carga(cpu: int, hilos: int):
    """Devuelve un callable para Ejecutor.ejecutar(limite_activos=...): mide la
    carga EXTERNA y la traduce a un nº de workers. None si no se puede medir en
    esta máquina (entonces no tiene sentido regular)."""
    if _tiempos_cpu() is None:
        return None
    medir = medidor_carga_externa()

    def limite() -> int:
        return objetivo_activos(medir(), hilos)

    return limite


def preparar(ruta_trabajo="." , politica: "PoliticaHilos | None" = None, *,
             ruta_origen=None, log=print) -> PerfilSistema:
    """
    PUNTO DE ENTRADA COMÚN a todos los motores. Mide la máquina, registra el
    perfil en el log (transparencia) y aplica el modo ligero si procede.
    Devuelve el PerfilSistema para que el motor calcule hilos cuando toque.

    Los motores NO vuelven a medir la máquina por su cuenta: llaman a esto.
    """
    politica = politica or PoliticaHilos()
    p = perfil(str(ruta_trabajo),
               str(ruta_origen) if ruta_origen is not None else None)
    log(f"Máquina: {resumen(p)}")
    if politica.prioridad_baja:
        bajar_prioridad()
    return p


# ==========================================================================
# Consola (diagnóstico)
# ==========================================================================
