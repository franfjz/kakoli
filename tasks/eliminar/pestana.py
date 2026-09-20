# -*- coding: utf-8 -*-
"""pestana — la interfaz de la tarea Eliminar."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import TYPE_CHECKING

from gui import tema
from tasks.eliminar import motor as melim
from gui.campo import Campo
from gui.pestana_base import PestanaBase

if TYPE_CHECKING:
    from core.resultado import Resultado


class PestanaEliminar(PestanaBase):
    nombre = "Eliminar"
    MOTOR = melim
    texto_inicio = "Eliminar"
    # Varias carpetas (una por línea, con Examinar múltiple y arrastrar y soltar); se
    # eliminan EN EL ORDEN de la lista.
    ENTRADAS = [
        Campo("origenes", "Carpetas a eliminar:", "lista",
              titulo_dialogo="Añade una carpeta a eliminar"),
    ]
    aviso = ("AVISO: el borrado es DEFINITIVO. Los archivos no van a la papelera "
             "de reciclaje y no se pueden recuperar. Se eliminan primero los "
             "archivos de los niveles más bajos y al final la carpeta principal.")
    estilo_accion = tema.PELIGRO_BTN     # botón principal en rojo
    ofrece_abrir = False                 # la carpeta se borra: no hay nada que abrir

    def _opciones(self) -> None:
        self.v_simular = tk.BooleanVar(value=False)
        self.v_confirmo = tk.BooleanVar(value=False)
        self.v_sin_contar = tk.BooleanVar(value=False)

        self._seccion("Seguridad")
        self._check(self.v_simular, "Solo simular (no borra nada)",
                    "Enumera y cuenta sin borrar nada, para comprobar antes. "
                    "El botón pasa a decir ‘Simular’.",
                    detalle="Recorre el árbol y lista en la consola qué se borraría, "
                    "con el recuento total, SIN tocar el disco. Es la forma segura de "
                    "comprobar que has elegido la carpeta correcta antes de un borrado "
                    "definitivo. Con esto marcado no hace falta la casilla de "
                    "confirmación.",
                    command=self._actualizar_boton)
        self._check(self.v_sin_contar,
                    "Borrar sin contar antes (más rápido en árboles enormes)",
                    "Salta el conteo previo: empieza antes en carpetas enormes; "
                    "a cambio la barra de progreso será aproximada.",
                    detalle="Normalmente se cuentan los archivos antes de empezar "
                    "para que la barra sea exacta. En árboles con cientos de miles de "
                    "archivos ese recuento tarda: con esto se salta y el borrado "
                    "empieza de inmediato, a cambio de una barra de progreso solo "
                    "aproximada. No cambia QUÉ se borra.")
        self._check(self.v_confirmo,
                    "Confirmo que quiero borrar esta carpeta definitivamente",
                    "Puerta de seguridad: hay que marcarla para habilitar el "
                    "borrado. Es DEFINITIVO (no va a la papelera).",
                    detalle="Mientras no la marques, el botón ‘Eliminar’ está "
                    "deshabilitado. El borrado es DEFINITIVO: no pasa por la papelera "
                    "de reciclaje y no hay ‘deshacer’. Aun así, al pulsar se pide una "
                    "última confirmación. Si solo quieres comprobar, usa ‘Solo "
                    "simular’.",
                    command=self._actualizar_boton)
        self.after(50, self._actualizar_boton)

    def _actualizar_boton(self) -> None:
        if self.ocupada():
            return
        listo = self.v_simular.get() or self.v_confirmo.get()
        self.b_iniciar.configure(state="normal" if listo else "disabled",
                                 text="Simular" if self.v_simular.get() else "Eliminar")

    def _validar(self) -> dict:
        origenes = [o for o in self.valores_lista("origenes") if o]
        if not origenes:
            raise ValueError("Añade al menos una carpeta que quieras eliminar.")
        if not self.v_simular.get() and not self.v_confirmo.get():
            raise ValueError("Marca la casilla de confirmación para poder borrar.")
        # Variables Tk leídas en el hilo principal (ver PestanaComprimir).
        validadas = [melim.rutas_validadas(Path(o)) for o in origenes]
        opts = melim.Opciones(simular=self.v_simular.get(),
                              detallado=self._detallado(),
                              contar=not self.v_sin_contar.get(),
                              politica=self._politica())
        return {"entradas": {"origenes": validadas}, "opts": opts}

    def _ejecutar(self, datos, log, progreso, pausar, cancelar):
        """Elimina cada carpeta de la lista, en orden."""
        return self._ejecutar_en_orden(datos["entradas"]["origenes"], datos["opts"],
                                       log, progreso, pausar, cancelar)

    def _confirmar(self, datos: dict) -> bool:
        if self.v_simular.get():
            return True
        carpetas = datos["entradas"]["origenes"]
        lista = "\n".join(f"  • {c}" for c in carpetas)
        return messagebox.askyesno(
            "Confirmar borrado definitivo",
            f"Se van a eliminar por completo estas {len(carpetas)} carpeta(s), "
            f"en este orden:\n\n{lista}\n\n"
            f"Los archivos NO van a la papelera de reciclaje y no se podrán "
            f"recuperar.\n\n¿Seguro que quieres continuar?",
            icon="warning", default="no", parent=self)

    def _al_terminar(self, res: "Resultado") -> None:
        # Reactiva la puerta de seguridad tras cada intento (el remate final —estado
        # y consola— lo pone PestanaBase; aquí no hace falta ningún aviso modal).
        self.v_confirmo.set(False)
        self._actualizar_boton()

    def _fin(self, res: "Resultado") -> None:
        super()._fin(res)
        self._actualizar_boton()



