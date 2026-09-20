# -*- coding: utf-8 -*-
"""pestana — la interfaz de la tarea Aplanar."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from tasks.aplanar import motor as maplan
from gui import tema
from gui.pestana_base import PestanaBase
from gui.constantes import _valor_ui

# Mapeos (etiqueta visible -> valor del motor) de los desplegables, propios de esta
# tarea (duplicación intencionada: Aplanar es independiente de otras tareas).
_MODOS_NOMBRE = [("Incluir la ruta en el nombre", "ruta"),
                 ("Solo el nombre final", "final")]
# La política de conflicto va en radios (una fila, mismo sistema que Combinar): la
# variable guarda el valor del motor directamente, con etiquetas breves.
_POLITICAS_RADIO = [("Renombrar", "renombrar"),
                    ("Mantener el primero", "mantener"),
                    ("Reemplazar según criterio", "reemplazar")]
_CRITERIOS = [("El más reciente", "mas_reciente"), ("El más antiguo", "mas_antiguo"),
              ("El de mayor tamaño", "mayor"), ("El de menor tamaño", "menor")]


class PestanaAplanar(PestanaBase):
    nombre = "Aplanar"
    MOTOR = maplan
    produce = "carpeta_aplanada"        # la carpeta aplanada (la consume Desaplanar)
    etiqueta_origen = "Directorio a aplanar:"
    etiqueta_destino = "Carpeta de salida:"
    titulo_dialogo = "Elige el directorio a aplanar"
    texto_inicio = "Aplanar"

    def _opciones(self) -> None:
        self.v_modo = tk.StringVar(value=_MODOS_NOMBRE[0][0])
        self.v_sep = tk.StringVar(value="-")
        # La política de conflicto guarda el valor del motor directamente (radios).
        self.v_conflicto = tk.StringVar(value=_POLITICAS_RADIO[0][1])
        self.v_criterio = tk.StringVar(value=_CRITERIOS[0][0])
        self.v_ocultos = tk.BooleanVar(value=False)

        self._seccion("Nombre de los archivos")
        self.cb_modo = self._combo(
            self.v_modo, "Al aplanar:", [e for e, _ in _MODOS_NOMBRE],
            "‘Incluir la ruta’ codifica las carpetas en el nombre (n1/n2/a.txt → "
            "n1-n2-a.txt) y permite luego Desaplanar. ‘Solo el nombre final’ deja "
            "a.txt (no se podrá desaplanar).", width=34,
            detalle="‘Incluir la ruta’ guarda el árbol completo dentro del nombre "
            "usando el separador de abajo, así Desaplanar puede reconstruirlo tal "
            "cual: es la opción reversible. ‘Solo el nombre final’ deja los nombres "
            "originales (más cortos y legibles) pero pierde la ruta, por lo que el "
            "resultado NO se puede desaplanar y son frecuentes los choques de nombre.")
        self.cb_modo.bind("<<ComboboxSelected>>", self._actualizar_modo)
        self.e_sep = self._entry(
            "Separador de niveles:", self.v_sep,
            "Texto que separa los niveles dentro del nombre (uno o varios "
            "caracteres). Por defecto ‘-’. El mismo texto se usará para desaplanar.",
            width=8,
            detalle="Elige un texto que NO aparezca en tus nombres de carpeta, o "
            "Desaplanar partirá donde no debe y creará subcarpetas de más. Puede "
            "tener varios caracteres (p. ej. ‘__’) para hacerlo más único. Apunta cuál "
            "usaste: al desaplanar hay que indicar exactamente el mismo.")

        # ===== Conflictos entre archivos (mismo sistema que Combinar) =====
        # Recuadro con: ayuda (bajo el título, sobre los botones) + política en radios
        # (una fila) + el criterio, que SOLO aparece si se elige 'Reemplazar'.
        def _ayuda_en(parent, row, texto, detalle, *widgets):
            lbl = tk.Label(parent, text=texto, wraplength=360)
            tema.estilo_label(lbl, "muted")
            lbl.grid(row=row, column=0, sticky="w", padx=(2, 8), pady=(0, 2))
            self._ayudas_lbl.append(lbl)
            self._tooltip_opcion(detalle, lbl, *widgets)
            return lbl

        blq = ttk.LabelFrame(self.contenedor_ops, text="Conflictos entre archivos",
                             padding=8, style=tema.SECCION)
        blq.grid(row=self._fila_seccion, column=0, sticky="ew", pady=(0, 8))
        blq.columnconfigure(0, weight=1)
        self._fila_seccion += 1

        # Radios en la fila 1; la ayuda en la fila 0 (bajo el título, sobre los botones).
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
        _ayuda_en(blq, 0,
                  "Qué hacer cuando dos archivos llegan con el mismo nombre al destino "
                  "(frecuente en ‘Solo el nombre final’).",
                  "Al llevar todo a una sola carpeta, dos archivos pueden acabar con "
                  "el mismo nombre (sobre todo en modo ‘Solo el nombre final’). "
                  "‘Renombrar’ los conserva ambos añadiendo la carpeta padre; ‘Mantener "
                  "el primero’ ignora los siguientes; ‘Reemplazar’ aplica el criterio "
                  "de abajo y descarta el perdedor.", *self._radios_conflicto)

        # Dependiente de 'Reemplazar según criterio': con qué criterio gana un archivo.
        self.blq_criterio = ttk.Frame(blq, style=tema.TARJETA)
        self.blq_criterio.grid(row=2, column=0, sticky="ew", padx=(16, 0))
        self.blq_criterio.columnconfigure(0, weight=1)
        fila_crit = ttk.Frame(self.blq_criterio, style=tema.TARJETA)
        fila_crit.grid(row=0, column=0, sticky="w", pady=(2, 0))
        ttk.Label(fila_crit, text="Reemplazar por:", style=tema.LBL_TITULO).pack(
            side="left")
        self.cb_criterio = ttk.Combobox(fila_crit, textvariable=self.v_criterio,
                                        state="readonly", width=22,
                                        values=[e for e, _ in _CRITERIOS])
        self.cb_criterio.pack(side="left", padx=(6, 0))
        self._bloqueables.append(self.cb_criterio)
        _ayuda_en(self.blq_criterio, 1,
                  "Con qué criterio gana un archivo. El perdedor se descarta "
                  "(IRREVERSIBLE).",
                  "Solo con la política ‘Reemplazar’. El perdedor se BORRA sin "
                  "papelera. ‘Más reciente/antiguo’ mira la fecha de modificación; "
                  "‘mayor/menor tamaño’, los bytes. Ante la duda, usa ‘Renombrar’: no "
                  "pierde nada y luego decides tú.", self.cb_criterio)

        self._seccion("Filtros")
        self._check(self.v_ocultos, "Omitir ocultos",
                    "Excluir archivos del sistema o invisibles (empiezan por ‘.’).",
                    detalle="No incluye en el aplanado los archivos ocultos: los que "
                    "empiezan por ‘.’ y, en Windows, los marcados como ocultos. Evita "
                    "arrastrar metadatos del sistema o de control de versiones a la "
                    "carpeta plana.")
        self.after(50, self._actualizar_modo)
        # La selección de conflicto gobierna el criterio y repinta los radios
        # (activo/inactivo inequívocos); se dispara ahora y en cada cambio.
        self.v_conflicto.trace_add("write", lambda *_: self._actualizar_conflicto())
        self._actualizar_conflicto()

    def _destino_automatico(self, origen: str) -> str:
        if not origen:
            return ""
        p = Path(origen).expanduser()
        return str(p.parent / f"{p.name}_aplanado") if p.name else ""

    def _actualizar_modo(self, *_a) -> None:
        usa_sep = _valor_ui(_MODOS_NOMBRE, self.v_modo.get(), "ruta") == "ruta"
        if not self.ocupada():
            self.e_sep.configure(state="normal" if usa_sep else "disabled")

    def _pintar_conflicto(self) -> None:
        """Colorea los radios de política: el elegido en verde, el resto apagado
        (el indicador circular nativo se veía igual marcado que sin marcar)."""
        actual = self.v_conflicto.get()
        for rb in self._radios_conflicto:
            tema.pintar_radio_seg(rb, str(rb.cget("value")) == actual, False)

    def _actualizar_conflicto(self, *_a) -> None:
        """Muestra el criterio SOLO con 'Reemplazar' (conservando su estado) y repinta
        los radios."""
        self._pintar_conflicto()
        es_reemplazo = self.v_conflicto.get() == "reemplazar"
        if es_reemplazo:
            self.blq_criterio.grid()
        else:
            self.blq_criterio.grid_remove()
        if not self.ocupada():
            self.cb_criterio.configure(state="readonly" if es_reemplazo else "disabled")

    def _al_terminar(self, res) -> None:
        """Tras la tarea, la base reactiva todo a 'normal'; re-aplica los estados
        correctos (criterio readonly/oculto, radios pintados)."""
        self._actualizar_conflicto()

    def _validar(self) -> dict:
        origen = self.valor("origen")
        if not origen:
            raise ValueError("Elige el directorio que quieres aplanar.")
        destino = self.valor("destino")
        o, d = maplan.rutas_validadas(Path(origen), Path(destino) if destino else None)
        modo = _valor_ui(_MODOS_NOMBRE, self.v_modo.get(), "ruta")
        sep = self.v_sep.get()
        if modo == "ruta":
            err = maplan.separador_ok(sep)
            if err:
                raise ValueError(err)
        opts = maplan.Opciones(
            modo_nombre=modo, separador=sep,
            conflicto=self.v_conflicto.get(),
            criterio_reemplazo=_valor_ui(_CRITERIOS, self.v_criterio.get(), "mas_reciente"),
            omitir_ocultos=self.v_ocultos.get(),
            detallado=self._detallado(),
            politica=self._politica())
        return {"entradas": {"origen": o, "destino": d}, "opts": opts}

    def _confirmar(self, datos: dict) -> bool:
        opts = datos["opts"]
        avisos = []
        if opts.conflicto == "reemplazar":
            avisos.append("• Con ‘Reemplazar’, los archivos descartados NO se podrán "
                          "recuperar.")
        if opts.modo_nombre == "final":
            avisos.append("• En modo ‘Solo el nombre final’ el resultado NO se podrá "
                          "desaplanar (los nombres no guardan la ruta).")
        if not avisos:
            return True
        return messagebox.askyesno(
            "Confirmar aplanado", "Aviso:\n\n" + "\n".join(avisos) + "\n\n¿Continuar?",
            icon="warning", default="no", parent=self)


