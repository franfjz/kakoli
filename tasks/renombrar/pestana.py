# -*- coding: utf-8 -*-
"""pestana — la interfaz de la tarea Renombrar."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from tasks.renombrar import motor as mrenom
from gui.campo import Campo
from gui.pestana_base import PestanaBase
from gui.constantes import _valor_ui

# Mapeo (etiqueta visible -> valor del motor) del desplegable de conflictos, propio
# de esta tarea.
_CONFLICTOS_RENOM = [("Numerar los que coincidan", "numerar"),
                     ("Omitir los que coincidan", "omitir")]


class PestanaRenombrar(PestanaBase):
    nombre = "Renombrar"
    MOTOR = mrenom
    texto_inicio = "Renombrar"
    # Varias carpetas (una por línea, con Examinar múltiple y arrastrar y soltar); se
    # renombran EN EL ORDEN de la lista.
    ENTRADAS = [
        Campo("origenes", "Carpetas a renombrar:", "lista",
              titulo_dialogo="Añade una carpeta con archivos a renombrar"),
    ]

    def _opciones(self) -> None:
        self._simular_flag = False
        self.v_prefijo = tk.StringVar()
        self.v_sufijo = tk.StringVar()
        self.v_buscar = tk.StringVar()
        self.v_reemplazar = tk.StringVar()
        self.v_sensible = tk.BooleanVar(value=True)
        self.v_solo_primera = tk.BooleanVar(value=False)
        self.v_recursivo = tk.BooleanVar(value=True)
        self.v_ocultos = tk.BooleanVar(value=False)
        self.v_conflicto = tk.StringVar(value=_CONFLICTOS_RENOM[0][0])

        self._seccion("Añadir texto (respeta la extensión)")
        self._entry("Al inicio (prefijo):", self.v_prefijo,
                    "Se añade delante del nombre.",
                    detalle="Se antepone al nombre sin tocar la extensión: con "
                    "prefijo ‘2024_’, ‘foto.jpg’ → ‘2024_foto.jpg’. Útil para "
                    "ordenar por fecha o proyecto. Puedes combinarlo con sufijo y "
                    "reemplazo en una sola pasada.")
        self._entry("Al final (sufijo):", self.v_sufijo,
                    "Se añade al final del nombre, ANTES de la extensión.",
                    detalle="Se añade al final pero ANTES del punto de la extensión: "
                    "con sufijo ‘_final’, ‘informe.pdf’ → ‘informe_final.pdf’ (no "
                    "‘informe.pdf_final’). Así la extensión sigue siendo válida.")

        self._seccion("Reemplazar un fragmento")
        self._entry("Buscar:", self.v_buscar, "Fragmento del nombre a sustituir.",
                    detalle="Texto literal a buscar dentro del nombre (no es una "
                    "expresión regular). Actúa sobre el nombre sin la extensión. Si "
                    "lo dejas vacío no se reemplaza nada. Combínalo con las casillas "
                    "de abajo para afinar mayúsculas y número de coincidencias.")
        self._entry("Reemplazar por:", self.v_reemplazar,
                    "Texto por el que se sustituye (vacío = eliminar el fragmento).",
                    detalle="Sustituye cada aparición de ‘Buscar’. Déjalo vacío para "
                    "ELIMINAR ese fragmento (p. ej. buscar ‘ - copia’ y reemplazar por "
                    "nada). Respeta la extensión del archivo.")
        self._check(self.v_sensible, "Distinguir mayúsculas y minúsculas",
                    "Si está marcado, ‘ABC’ y ‘abc’ se consideran distintos.",
                    detalle="Marcado, ‘Foto’ y ‘foto’ son distintos y solo se "
                    "reemplaza la coincidencia exacta. Desmarcado, busca sin importar "
                    "may/min (‘IMG’ encuentra también ‘img’), útil cuando el mismo "
                    "texto aparece escrito de varias formas.")
        self._check(self.v_solo_primera, "Solo la primera coincidencia",
                    "Sustituye solo la primera vez que aparece en cada nombre.",
                    detalle="Marcado, cambia solo la PRIMERA aparición en cada nombre "
                    "(‘a-a-a’ con buscar ‘a’→‘x’ da ‘x-a-a’). Desmarcado, cambia "
                    "todas (‘x-x-x’). Útil cuando el fragmento se repite y solo "
                    "quieres tocar el primero.")

        self._seccion("Ámbito")
        self._check(self.v_recursivo, "Incluir subdirectorios",
                    "Renombra también los archivos de las subcarpetas.",
                    detalle="Marcado, entra en todas las subcarpetas y renombra sus "
                    "archivos también (solo archivos, no cambia nombres de carpeta). "
                    "Desmarcado, se limita a los archivos sueltos de la carpeta "
                    "elegida. En árboles grandes, usa antes ‘Vista previa’.")
        self._check(self.v_ocultos, "Omitir ocultos",
                    "Excluye archivos que empiezan por ‘.’.",
                    detalle="No renombra los archivos ocultos (nombres que empiezan "
                    "por ‘.’ y, en Windows, los de atributo oculto). Evita tocar "
                    "ficheros de configuración o del sistema por accidente.")

        self._seccion("Conflictos (el nuevo nombre ya existe)")
        self._combo(self.v_conflicto, "Al coincidir:",
                    [e for e, _ in _CONFLICTOS_RENOM],
                    "Numerar: añade ‘_2’, ‘_3’… (no se pierde nada). Omitir: deja ese "
                    "archivo con su nombre.", width=26,
                    detalle="Cuando el nuevo nombre ya lo tiene otro archivo de la "
                    "misma carpeta: ‘Numerar’ añade ‘_2’, ‘_3’… al recién renombrado "
                    "(no se pierde ni se pisa nada); ‘Omitir’ deja ese archivo con su "
                    "nombre original y sigue con el resto. Nunca sobrescribe.")

        self._seccion("Vista previa")
        b = ttk.Button(self.marco_ops, text="Vista previa (no renombra)",
                       command=self._previsualizar)
        self._add_control(b)
        self._bloqueables.append(b)
        self._add_ayuda("Muestra en la consola ‘antes → después’ sin tocar el disco.")

    def _previsualizar(self) -> None:
        if self.ocupada():
            return
        self._simular_flag = True
        self._iniciar()

    def _validar(self) -> dict:
        simular = self._simular_flag           # se lee y limpia antes de cualquier raise
        self._simular_flag = False
        origenes = [o for o in self.valores_lista("origenes") if o]
        if not origenes:
            raise ValueError("Añade al menos una carpeta con los archivos a renombrar.")
        validadas = [mrenom.rutas_validadas(Path(o)) for o in origenes]
        opts = mrenom.Opciones(
            prefijo=self.v_prefijo.get(), sufijo=self.v_sufijo.get(),
            buscar=self.v_buscar.get(), reemplazar=self.v_reemplazar.get(),
            sensible_mayusculas=self.v_sensible.get(),
            solo_primera=self.v_solo_primera.get(),
            recursivo=self.v_recursivo.get(), omitir_ocultos=self.v_ocultos.get(),
            conflicto=_valor_ui(_CONFLICTOS_RENOM, self.v_conflicto.get(), "numerar"),
            simular=simular, detallado=self._detallado(),
            politica=self._politica())
        if not (opts.prefijo or opts.sufijo or opts.buscar):
            raise ValueError("Indica algún cambio: prefijo, buscar/reemplazar o sufijo.")
        return {"entradas": {"origenes": validadas}, "opts": opts}

    def _ejecutar(self, datos, log, progreso, pausar, cancelar):
        """Renombra cada carpeta de la lista, en orden."""
        return self._ejecutar_en_orden(datos["entradas"]["origenes"], datos["opts"],
                                       log, progreso, pausar, cancelar)

    def _confirmar(self, datos: dict) -> bool:
        if datos["opts"].simular:
            return True                        # la vista previa no pregunta
        return messagebox.askyesno(
            "Confirmar renombrado",
            "Se van a renombrar archivos en bloque (esta acción no tiene ‘deshacer’).\n\n"
            "Consejo: usa ‘Vista previa’ antes para ver los cambios.\n\n¿Continuar?",
            icon="warning", default="no", parent=self)
