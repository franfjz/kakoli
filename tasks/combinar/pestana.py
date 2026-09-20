# -*- coding: utf-8 -*-
"""pestana — la interfaz de la tarea Combinar."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from tasks.combinar import motor as mcombi
from gui import tema
from gui import componentes
from gui.campo import Campo
from gui.pestana_base import PestanaBase
from gui.constantes import _valor_ui

# Mapeos (etiqueta visible -> valor del motor) de los desplegables, propios de esta
# tarea (duplicación intencionada: Combinar es independiente de otras tareas).
# La política de conflicto va en radios (una fila): la variable guarda el valor del
# motor directamente, con etiquetas breves para que quepan en una fila.
_POLITICAS_RADIO = [("Mantener principal", "mantener"),
                    ("Renombrar", "renombrar"),
                    ("Reemplazar según criterio", "reemplazar")]
_CRITERIOS = [("El más reciente", "mas_reciente"), ("El más antiguo", "mas_antiguo"),
              ("El de mayor tamaño", "mayor"), ("El de menor tamaño", "menor")]
_CODIGOS = [("Nombre de la carpeta de origen", "basename"),
            ("Id corto estable (_d1, _d2…)", "id"),
            ("Personalizado", "personalizado")]


class PestanaCombinar(PestanaBase):
    nombre = "Combinar"
    MOTOR = mcombi
    produce = "carpeta_combinada"       # el directorio combinado (lo consume Descombinar)
    titulo_dialogo = "Elige un directorio"
    texto_inicio = "Combinar"
    ENTRADAS = [
        Campo("principal", "Directorio principal:", "carpeta"),
        Campo("mas", "Directorios a combinar:", "lista",
              titulo_dialogo="Añade un directorio a combinar"),
    ]

    def _opciones(self) -> None:
        # La política de conflicto guarda el valor del motor directamente (los radios
        # llevan value= ese valor); el resto de desplegables guardan su etiqueta.
        self.v_conflicto = tk.StringVar(value=_POLITICAS_RADIO[0][1])
        self.v_criterio = tk.StringVar(value=_CRITERIOS[0][0])
        self.v_codigo = tk.StringVar(value=_CODIGOS[0][0])
        self.v_codigo_texto = tk.StringVar()
        self.v_ocultos = tk.BooleanVar(value=False)
        self.v_indice = tk.BooleanVar(value=True)

        # --- helpers locales: colocan por grid (para poder ocultar dependientes con
        #     grid_remove conservando su estado) y registran bloqueo/ayuda/tooltip ---
        def _combo_en(parent, row, var, etiqueta, valores, width):
            fila = ttk.Frame(parent, style=tema.TARJETA)
            fila.grid(row=row, column=0, sticky="w", pady=(2, 0))
            ttk.Label(fila, text=etiqueta, style=tema.LBL_TITULO).pack(side="left")
            cb = ttk.Combobox(fila, textvariable=var, state="readonly",
                              width=width, values=[e for e, _ in valores])
            cb.pack(side="left", padx=(6, 0))
            self._bloqueables.append(cb)
            return cb

        def _entry_en(parent, row, etiqueta, var, width):
            fila, entry = componentes.fila_texto(parent, etiqueta, var, width=width)
            fila.grid(row=row, column=0, sticky="w", pady=(2, 0))
            self._bloqueables.append(entry)
            return entry

        def _ayuda_en(parent, row, texto, detalle, *widgets):
            lbl = tk.Label(parent, text=texto, wraplength=360)
            tema.estilo_label(lbl, "muted")
            lbl.grid(row=row, column=0, sticky="w", padx=(2, 8), pady=(0, 2))
            self._ayudas_lbl.append(lbl)
            self._tooltip_opcion(detalle, lbl, *widgets)
            return lbl

        # ===== Conflictos entre archivos (recuadro): ayuda + radios + dependientes ====
        blq = ttk.LabelFrame(self.contenedor_ops, text="Conflictos entre archivos",
                             padding=8, style=tema.SECCION)
        blq.grid(row=self._fila_seccion, column=0, sticky="ew", pady=(0, 8))
        blq.columnconfigure(0, weight=1)
        self._fila_seccion += 1

        # Los radios se crean primeros pero se colocan en la fila 1: la ayuda va en la
        # fila 0 (bajo el título del recuadro, SOBRE los botones).
        fila_pol = ttk.Frame(blq, style=tema.TARJETA)
        fila_pol.grid(row=1, column=0, sticky="w")
        self._radios_conflicto = []
        for etiqueta, valor in _POLITICAS_RADIO:
            rb = tk.Radiobutton(fila_pol, text=etiqueta, value=valor,
                                variable=self.v_conflicto)
            tema.estilo_radio_seg(rb)
            rb.pack(side="left", padx=(0, 4))
            self._radios_conflicto.append(rb)
            self._bloqueables.append(rb)
        _ayuda_en(blq, 0, "Qué hacer cuando un archivo coincide en ruta y nombre.",
                  "Hay conflicto cuando dos fuentes traen un archivo con el MISMO "
                  "nombre en la MISMA ruta relativa. ‘Renombrar’ conserva ambos (añade "
                  "el código de origen al que llega después). ‘Mantener principal’ "
                  "descarta el de las fuentes. ‘Reemplazar’ decide por el criterio de "
                  "abajo. Los archivos en rutas distintas nunca chocan.",
                  *self._radios_conflicto)

        # Dependiente de 'Renombrar': código de origen (con su caja Personalizado).
        self.blq_codigo = ttk.Frame(blq, style=tema.TARJETA)
        self.blq_codigo.grid(row=2, column=0, sticky="ew", padx=(16, 0))
        self.blq_codigo.columnconfigure(0, weight=1)
        ttk.Label(self.blq_codigo, text="Código de origen (para los renombrados)",
                  style=tema.LBL_TITULO).grid(row=0, column=0, sticky="w", pady=(4, 2))
        self.cb_codigo = _combo_en(self.blq_codigo, 1, self.v_codigo, "Código:",
                                   _CODIGOS, 30)
        self.cb_codigo.bind("<<ComboboxSelected>>", self._actualizar_codigo)
        _ayuda_en(self.blq_codigo, 2,
                  "Sufijo que identifica de qué carpeta viene el archivo renombrado "
                  "(p. ej. ‘informe_dir2.pdf’).",
                  "Solo afecta a los archivos que se RENOMBRAN por conflicto. ‘Nombre "
                  "de la carpeta de origen’ es legible (informe_fotos.pdf) pero puede "
                  "alargar mucho el nombre. ‘Id corto’ usa _d1, _d2… (compacto y "
                  "estable). ‘Personalizado’ te deja fijar el texto del sufijo abajo.",
                  self.cb_codigo)
        self.blq_personalizado = ttk.Frame(self.blq_codigo, style=tema.TARJETA)
        self.blq_personalizado.grid(row=3, column=0, sticky="ew")
        self.blq_personalizado.columnconfigure(0, weight=1)
        self.e_codigo = _entry_en(self.blq_personalizado, 0, "Personalizado:",
                                  self.v_codigo_texto, 18)
        _ayuda_en(self.blq_personalizado, 1,
                  "Texto que se añade al nombre de los archivos renombrados.",
                  "Texto que se añadirá al nombre de los archivos renombrados cuando "
                  "el código es ‘Personalizado’. Evita caracteres inválidos para "
                  "nombres de archivo (\\ / : * ? \" < > |). Si lo dejas vacío se usará "
                  "el criterio por defecto.", self.e_codigo)

        # Dependiente de 'Reemplazar según criterio': con qué criterio gana un archivo.
        self.blq_criterio = ttk.Frame(blq, style=tema.TARJETA)
        self.blq_criterio.grid(row=3, column=0, sticky="ew", padx=(16, 0))
        self.blq_criterio.columnconfigure(0, weight=1)
        self.cb_criterio = _combo_en(self.blq_criterio, 0, self.v_criterio,
                                     "Reemplazar por:", _CRITERIOS, 22)
        _ayuda_en(self.blq_criterio, 1,
                  "Con qué criterio gana un archivo. El perdedor se descarta "
                  "(IRREVERSIBLE).",
                  "Se aplica solo con la política ‘Reemplazar’. El ganador se queda y "
                  "el perdedor se BORRA sin pasar por la papelera. ‘Más reciente’ usa "
                  "la fecha de modificación; ‘mayor/menor tamaño’, los bytes. Como es "
                  "irreversible, si no estás seguro usa ‘Renombrar’ (conserva los dos) "
                  "y revisa después.", self.cb_criterio)

        self._seccion("Filtros")
        self._check(self.v_ocultos, "Omitir ocultos",
                    "Excluir archivos del sistema o invisibles (empiezan por ‘.’).",
                    detalle="No copia los archivos ocultos de las fuentes: los que "
                    "empiezan por ‘.’ (.git, .DS_Store…) y, en Windows, los marcados "
                    "como ocultos. Útil para no mezclar metadatos de control de "
                    "versiones al fundir varios árboles.")

        self._seccion("Reversibilidad")
        self._check(self.v_indice,
                    "Crear índice para poder deshacer (Descombinar)",
                    "Guarda un índice en el principal para poder revertir la "
                    "combinación. Desactívalo solo en procesos enormes que no vas "
                    "a deshacer: más rápido y sin espacio extra, pero NO se podrá "
                    "descombinar.",
                    detalle="El índice es un pequeño JSON en la carpeta principal que "
                    "anota de qué fuente vino cada archivo y su renombrado, para que "
                    "Descombinar pueda devolver todo a su sitio. Ocupa muy poco. "
                    "Solo tiene sentido quitarlo en fusiones enormes y definitivas "
                    "donde la escritura del índice sea un coste medible; sin él, la "
                    "combinación es un viaje sin retorno.")
        # La selección de conflicto gobierna qué dependientes se ven y repinta los
        # radios (activo/inactivo inequívocos). Se dispara ahora y en cada cambio.
        self.v_conflicto.trace_add("write", lambda *_: self._actualizar_conflicto())
        self._actualizar_conflicto()

    def _pintar_conflicto(self) -> None:
        """Colorea los radios de política: el elegido en verde, el resto apagado
        (el indicador circular nativo se veía igual marcado que sin marcar)."""
        actual = self.v_conflicto.get()
        for rb in self._radios_conflicto:
            tema.pintar_radio_seg(rb, str(rb.cget("value")) == actual, False)

    def _actualizar_conflicto(self, *_a) -> None:
        """Muestra solo los ajustes de la política elegida (conservando su estado):
        'Renombrar' → código de origen; 'Reemplazar' → criterio; 'Mantener' → nada."""
        self._pintar_conflicto()
        v = self.v_conflicto.get()
        if v == "renombrar":
            self.blq_codigo.grid()
            self.blq_criterio.grid_remove()
        elif v == "reemplazar":
            self.blq_criterio.grid()
            self.blq_codigo.grid_remove()
        else:
            self.blq_codigo.grid_remove()
            self.blq_criterio.grid_remove()
        if not self.ocupada():
            self.cb_criterio.configure(
                state="readonly" if v == "reemplazar" else "disabled")
        self._actualizar_codigo()

    def _actualizar_codigo(self, *_a) -> None:
        """La caja 'Personalizado' solo se ve con 'Renombrar' + código Personalizado."""
        mostrar_codigo = self.v_conflicto.get() == "renombrar"
        personalizado = (mostrar_codigo and
                         _valor_ui(_CODIGOS, self.v_codigo.get(), "") == "personalizado")
        if personalizado:
            self.blq_personalizado.grid()
        else:
            self.blq_personalizado.grid_remove()
        if not self.ocupada():
            self.cb_codigo.configure(
                state="readonly" if mostrar_codigo else "disabled")
            self.e_codigo.configure(state="normal" if personalizado else "disabled")

    def _al_terminar(self, res) -> None:
        """Tras la tarea, la base reactiva TODO a 'normal'; re-aplica los estados
        correctos (combos readonly/disabled, dependientes ocultos, radios pintados)."""
        self._actualizar_conflicto()

    def _validar(self) -> dict:
        principal = self.valor("principal")
        if not principal:
            raise ValueError("Elige el directorio principal.")
        fuentes = [f for f in self.valores_lista("mas") if f]
        if not fuentes:
            raise ValueError("Añade al menos un directorio para combinar.")
        # rutas_validadas comprueba que TODAS las fuentes existen (y crea el principal).
        p, fs = mcombi.rutas_validadas(Path(principal), [Path(f) for f in fuentes])
        opts = mcombi.Opciones(
            conflicto=self.v_conflicto.get(),
            criterio_reemplazo=_valor_ui(_CRITERIOS, self.v_criterio.get(), "mas_reciente"),
            modo_codigo=_valor_ui(_CODIGOS, self.v_codigo.get(), "basename"),
            codigo_personalizado=self.v_codigo_texto.get().strip(),
            crear_indice=self.v_indice.get(),
            omitir_ocultos=self.v_ocultos.get(),
            detallado=self._detallado(),
            politica=self._politica())
        return {"entradas": {"principal": p, "fuentes": fs}, "opts": opts}

    def _confirmar(self, datos: dict) -> bool:
        opts = datos["opts"]
        avisos = []
        if opts.conflicto == "reemplazar":
            avisos.append("• Con 'Reemplazar', los archivos descartados NO se podrán "
                          "recuperar.")
        if not opts.crear_indice:
            avisos.append("• Sin índice, el resultado NO se podrá descombinar "
                          "(no se podrá volver a las carpetas de origen).")
        if not avisos:
            return True
        return messagebox.askyesno(
            "Confirmar combinación",
            "Aviso:\n\n" + "\n".join(avisos) + "\n\n¿Continuar?",
            icon="warning", default="no", parent=self)


