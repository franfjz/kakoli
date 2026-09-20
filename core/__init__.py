# -*- coding: utf-8 -*-
"""core — núcleo estable y agnóstico de dominio y de la GUI (solo biblioteca
estándar, sin Tkinter):

    resultado  Resultado, EstadoResultado, Cancelado (tipos del contrato de motor).
    opciones   OpcionesBase (campos de opciones comunes a todo motor).
    formato    humano/duracion/ahora y PASO_REGISTRO (formato/tiempo).
    cli        correr_cli, Interrupcion, preguntar_consola (arnés de consola).
    reanudable RegistroReanudable: progreso reanudable (JSONL) común a las tareas.
    control    Control: parada común (pausa/cancelar/PAUSA/límite) del bucle de proceso.
    recursos   detección del equipo (CPU/RAM/disco/carga) y cálculo de hilos.
    paralelo   orquestación de la ejecución en paralelo (Ejecutor, planes).
    registro   contrato de tarea y registro de tareas (Categoria/DescriptorTarea).
    ejecucion  Ejecucion: hilo de trabajo + cola de eventos (sin Tk).

Se importa como paquete, p. ej. `from core import recursos` o
`from core.resultado import Resultado`.
"""
