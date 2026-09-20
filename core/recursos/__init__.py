# -*- coding: utf-8 -*-
"""recursos — detección del equipo y política de rendimiento (subpaquete del núcleo).

Fachada estable: reexporta la medición (`sondas`) y la política (`politica`), de modo
que los llamadores siguen usando `from core import recursos` y `recursos.perfil`,
`recursos.calcular_hilos`, `recursos.PoliticaHilos`, `recursos.preparar`… sin saber en
qué submódulo vive cada cosa.

    sondas    mide la máquina (CPU/RAM/disco/energía) -> PerfilSistema; modo ligero.
    politica  decide hilos/throttling a partir del PerfilSistema.
"""
from core.recursos.sondas import (
    MB, cpu_utilizables, cpu_logicos, cpu_fisicos, muestra_carga,
    medidor_carga_externa, ram_total_y_disponible, swap_total_y_usado,
    es_disco_lento, espacio_libre, mismo_volumen, tipo_unidad, estado_energia,
    proceso_64bit, bajar_prioridad, PerfilSistema, perfil, resumen, main)
from core.recursos.politica import (
    PoliticaHilos, calcular_hilos, techo_hilos, objetivo_activos,
    regulador_carga, preparar, UMBRAL_EXTERNO_SUAVE, UMBRAL_EXTERNO_DURO)

__all__ = [
    "MB", "cpu_utilizables", "cpu_logicos", "cpu_fisicos", "muestra_carga",
    "medidor_carga_externa", "ram_total_y_disponible", "swap_total_y_usado",
    "es_disco_lento", "espacio_libre", "mismo_volumen", "tipo_unidad",
    "estado_energia", "proceso_64bit", "bajar_prioridad", "PerfilSistema",
    "perfil", "resumen", "main",
    "PoliticaHilos", "calcular_hilos", "techo_hilos", "objetivo_activos",
    "regulador_carga", "preparar", "UMBRAL_EXTERNO_SUAVE", "UMBRAL_EXTERNO_DURO",
]
