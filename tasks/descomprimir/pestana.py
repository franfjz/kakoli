# -*- coding: utf-8 -*-
"""pestana — la interfaz de la tarea Descomprimir."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from tasks.descomprimir import motor as mdesc
from gui.pestana_base import PestanaBase


class PestanaDescomprimir(PestanaBase):
    nombre = "Descomprimir"
    MOTOR = mdesc
    consume = "zip_anidado"             # recibe el .zip que produce Comprimir
    etiqueta_origen = "Archivo ZIP:"
    tipo_origen = "archivo"
    filtros_origen = [("Archivos ZIP", "*.zip"), ("Todos los archivos", "*.*")]
    etiqueta_destino = "Carpeta de destino:"
    titulo_dialogo = "Elige el archivo ZIP a descomprimir"
    texto_inicio = "Descomprimir"

    def _opciones(self) -> None:
        self.v_verificar = tk.BooleanVar(value=False)
        self.v_conservar = tk.BooleanVar(value=False)
        self.v_todos = tk.BooleanVar(value=False)

        self._seccion("Opciones de extracción")
        self._check(self.v_todos, "Expandir cualquier .zip (archivos antiguos)",
                    "Expande todo .zip, lleve o no la marca de kakoli. Úsalo solo "
                    "para archivos de versiones antiguas: si no, podría expandir "
                    ".zip que eran datos legítimos.",
                    detalle="Normalmente kakoli solo expande los ZIP que él mismo "
                    "creó (llevan una marca interna ‘zip-anidado’), para no tocar "
                    "un .zip que forme parte de tus datos. Actívalo para reconstruir "
                    "archivos hechos con versiones antiguas que aún no ponían la "
                    "marca. Riesgo: si dentro hay .zip legítimos, también se abrirán.")
        self._check(self.v_verificar, "Verificar CRC al extraer",
                    "Comprueba que cada ZIP no esté dañado antes de extraerlo. "
                    "Más seguro, más lento.",
                    detalle="Contrasta cada archivo con su suma de control (CRC-32) "
                    "antes de escribirlo. Detecta corrupción por disco defectuoso, "
                    "transferencias truncadas o medios viejos. Añade una lectura "
                    "completa de cada ZIP: recomendable en archivos importantes o de "
                    "procedencia dudosa; prescindible si acabas de crearlos.")
        self._check(self.v_conservar, "Conservar los .zip ya expandidos",
                    "No borra los .zip internos tras convertirlos en carpetas. "
                    "Deja copias (más espacio); útil para inspeccionar.",
                    detalle="Por defecto, cada .zip interno se borra en cuanto se "
                    "convierte en su carpeta, para no duplicar. Con esto se conservan "
                    "los .zip junto a las carpetas extraídas: ocupa casi el doble, "
                    "pero permite comparar el original con lo extraído o reintentar "
                    "si algo sale mal.")

    def _destino_automatico(self, origen: str) -> str:
        return str(Path(origen).expanduser().parent) if origen else ""

    def _validar(self) -> dict:
        origen = self.valor("origen")
        if not origen:
            raise ValueError("Elige el archivo ZIP que quieres descomprimir.")
        destino = self.valor("destino")
        z, dst = mdesc.rutas_validadas(Path(origen), Path(destino) if destino else None)
        # Variables Tk leídas en el hilo principal (ver PestanaComprimir).
        opts = mdesc.Opciones(verificar=self.v_verificar.get(),
                              conservar_zips=self.v_conservar.get(),
                              expandir_todos=self.v_todos.get(),
                              detallado=self._detallado(),
                              politica=self._politica())
        return {"entradas": {"origen": z, "destino": dst}, "opts": opts}

    def _confirmador(self):
        return self._preguntar

    def _preguntar(self, mensaje: str, por_defecto: bool) -> bool:
        """El motor pregunta desde su hilo; la respuesta se pide en la ventana."""
        respuesta: list[bool] = []
        evento = threading.Event()

        def en_ventana() -> None:
            try:
                respuesta.append(messagebox.askyesno("Descomprimir", mensaje,
                                                     parent=self))
            finally:
                evento.set()

        self.after(0, en_ventana)
        if not evento.wait(timeout=300):
            return por_defecto
        return respuesta[0] if respuesta else por_defecto

