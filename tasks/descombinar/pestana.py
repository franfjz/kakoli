# -*- coding: utf-8 -*-
"""pestana — la interfaz de la tarea Descombinar."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from tasks.descombinar import motor as mdescombi
from gui.pestana_base import PestanaBase


class PestanaDescombinar(PestanaBase):
    nombre = "Descombinar"
    MOTOR = mdescombi
    consume = "carpeta_combinada"       # recibe el directorio que produce Combinar
    etiqueta_origen = "Directorio combinado:"
    etiqueta_destino = "Carpeta de salida:"
    titulo_dialogo = "Elige el directorio combinado"
    texto_inicio = "Descombinar"

    def _opciones(self) -> None:
        self.v_sobrescribir = tk.BooleanVar(value=False)
        self._seccion("Opciones para descombinar")
        self._check(self.v_sobrescribir, "Sobrescribir si ya existe en el destino",
                    "Rehace los archivos que ya estén en la carpeta de salida. "
                    "Sin marcar, se conservan los que ya haya.",
                    detalle="Al reconstruir las carpetas de origen desde el índice, "
                    "decide qué hacer si un archivo ya existe en el destino. Marcado, "
                    "lo pisa con la versión del combinado; sin marcar, respeta el que "
                    "ya está (útil para reanudar sin rehacer lo hecho o para no tocar "
                    "cambios locales posteriores).")

    def _destino_automatico(self, origen: str) -> str:
        if not origen:
            return ""
        p = Path(origen).expanduser()
        return str(p.parent / f"{p.name}_descombinado") if p.name else ""

    def _validar(self) -> dict:
        origen = self.valor("origen")
        if not origen:
            raise ValueError("Elige el directorio combinado que quieres descombinar.")
        destino = self.valor("destino")
        combinado, dst = mdescombi.rutas_validadas(
            Path(origen), Path(destino) if destino else None)
        opts = mdescombi.Opciones(sobrescribir=self.v_sobrescribir.get(),
                                  detallado=self._detallado(),
                                  politica=self._politica())
        return {"entradas": {"origen": combinado, "destino": dst}, "opts": opts}


