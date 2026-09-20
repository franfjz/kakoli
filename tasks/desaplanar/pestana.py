# -*- coding: utf-8 -*-
"""pestana — la interfaz de la tarea Desaplanar."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from tasks.desaplanar import motor as mdesaplan
from tasks.formatos.nombres_aplanado import separador_ok
from gui.pestana_base import PestanaBase
from gui.constantes import _valor_ui

# Mapeo (etiqueta visible -> valor del motor) del desplegable de conflictos, propio
# de esta tarea.
_POLITICAS_DESAPLANAR = [("Renombrar (sufijo numérico)", "renombrar"),
                         ("Mantener el primero", "mantener"),
                         ("Reemplazar", "reemplazar")]


class PestanaDesaplanar(PestanaBase):
    nombre = "Desaplanar"
    MOTOR = mdesaplan
    consume = "carpeta_aplanada"        # recibe la carpeta que produce Aplanar
    etiqueta_origen = "Carpeta aplanada:"
    etiqueta_destino = "Carpeta de salida:"
    titulo_dialogo = "Elige la carpeta aplanada"
    texto_inicio = "Desaplanar"

    def _opciones(self) -> None:
        self.v_sep = tk.StringVar(value="-")
        self.v_conflicto = tk.StringVar(value=_POLITICAS_DESAPLANAR[0][0])
        self.v_ocultos = tk.BooleanVar(value=False)

        self._seccion("Reconstrucción del árbol")
        self.e_sep = self._entry(
            "Separador de niveles:", self.v_sep,
            "El árbol se deduce partiendo cada nombre por este separador (debe "
            "coincidir con el usado al aplanar). Aviso: un nombre que ya contenga "
            "ese texto creará carpetas no deseadas.",
            width=8,
            detalle="Debe ser EXACTAMENTE el mismo texto que usaste al aplanar (por "
            "defecto ‘-’). Cada aparición del separador en el nombre se convierte en "
            "un nivel de carpeta: por eso, si un nombre real ya contenía ese texto, "
            "aparecerán carpetas de más. Si no recuerdas cuál usaste, abre un nombre "
            "aplanado y fíjate en qué lo separa.")

        self._seccion("Conflictos (misma ruta reconstruida)")
        self._combo(self.v_conflicto, "Al coincidir:",
                    [e for e, _ in _POLITICAS_DESAPLANAR],
                    "Qué hacer si dos nombres reconstruyen la misma ruta.", width=28,
                    detalle="Puede pasar si el aplanado no era reversible o se editó "
                    "a mano. ‘Renombrar’ añade un sufijo numérico y conserva ambos; "
                    "‘Mantener el primero’ ignora los siguientes; ‘Reemplazar’ pisa "
                    "el anterior. ‘Renombrar’ es la opción segura: no pierde datos.")

        self._seccion("Filtros")
        self._check(self.v_ocultos, "Omitir ocultos",
                    "Excluir archivos del sistema o invisibles (empiezan por ‘.’).",
                    detalle="No reconstruye los archivos ocultos presentes en la "
                    "carpeta aplanada (los que empiezan por ‘.’ y, en Windows, los de "
                    "atributo oculto). Normalmente déjalo desmarcado para no perder "
                    "nada del original.")

    def _destino_automatico(self, origen: str) -> str:
        if not origen:
            return ""
        p = Path(origen).expanduser()
        return str(p.parent / f"{p.name}_desaplanado") if p.name else ""

    def _validar(self) -> dict:
        origen = self.valor("origen")
        if not origen:
            raise ValueError("Elige la carpeta aplanada que quieres desaplanar.")
        destino = self.valor("destino")
        o, d = mdesaplan.rutas_validadas(Path(origen), Path(destino) if destino else None)
        sep = self.v_sep.get()
        err = separador_ok(sep)
        if err:
            raise ValueError(err)
        opts = mdesaplan.Opciones(
            separador=sep,
            conflicto=_valor_ui(_POLITICAS_DESAPLANAR, self.v_conflicto.get(), "renombrar"),
            omitir_ocultos=self.v_ocultos.get(),
            detallado=self._detallado(),
            politica=self._politica())
        return {"entradas": {"origen": o, "destino": d}, "opts": opts}


