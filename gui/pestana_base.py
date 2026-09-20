# -*- coding: utf-8 -*-
"""pestana_base — base común de todas las pestañas de tareas.

Aporta: campos de entrada declarativos (ENTRADAS/Campo), secciones de opciones
(_seccion/_check/_combo), botones Iniciar/Pausar, barra de progreso, el bucle
hilo+cola con la ventana, la reanudación tras cerrar (_preguntar_reanudar) y el
handoff (produce/consume). Cada pestaña concreta define su MOTOR, ENTRADAS,
_opciones(), _validar() y, si procede, _confirmar()/_al_terminar().
"""
from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import Callable, TYPE_CHECKING

from core import recursos
from core.formato import ahora, duracion
from core.resultado import EstadoResultado, Resultado
from core.ejecucion import Ejecucion
from gui import tema
from gui import componentes
from gui import dnd
from gui.campo import Campo

if TYPE_CHECKING:
    from gui.contexto import ContextoApp


class PestanaBase(ttk.Frame):
    """Selector + opciones + Iniciar/Pausar + progreso + registro."""

    nombre: str = "Tarea"              # rótulo de la pestaña (autodescriptivo)
    # Motor de la pestaña (módulo con ejecutar(entradas, opts, *, callbacks)).
    MOTOR = None
    # Campos de entrada declarativos. Si es None, se derivan de los atributos
    # clásicos de abajo (origen [+ destino]) — así las pestañas de serie no cambian.
    ENTRADAS: "list[Campo] | None" = None
    etiqueta_origen = "Carpeta:"
    tipo_origen = "carpeta"            # "carpeta" o "archivo"
    # Filtros del diálogo cuando el origen es un archivo (None = todos). P. ej.
    # Descomprimir lo fija a los .zip. Se pasa al Campo derivado de origen.
    filtros_origen: "list[tuple[str, str]] | None" = None
    etiqueta_destino: str | None = None
    titulo_dialogo = "Elige la carpeta"
    texto_inicio = "Iniciar"
    aviso: str = ""
    estilo_accion: str = tema.ACCION   # estilo del botón principal (rojo en Eliminar)
    # Tipo de ARTEFACTO que produce/consume esta tarea (para el handoff entre
    # gemelas, casado por el Registro). P. ej. Comprimir produce "zip_anidado" y
    # Descomprimir lo consume. None = no participa en el handoff por ese lado.
    produce: "str | None" = None
    consume: "str | None" = None
    # ¿ofrecer "Abrir carpeta" al completar? Lo desactivan las tareas cuyo resultado
    # no es una carpeta que tenga sentido abrir (p. ej. Eliminar, que la borra).
    ofrece_abrir: bool = True

    def __init__(self, master: tk.Misc, app: "ContextoApp") -> None:
        super().__init__(master, padding=10)
        self.app = app
        # Máquina de ejecución (hilo + cola de eventos), sin Tk: la GUI solo drena
        # sus eventos con recoger() y actualiza los widgets.
        self._ejec = Ejecucion()
        self.cerrando = False
        self.auto_destino = True
        # ¿la tarea se pausó en ESTA sesión? Si es así, "Continuar" reanuda sin el
        # modal de reanudación (ese modal es solo para reanudar tras cerrar la app).
        self._reanudando_en_sesion = False
        self._bloqueables: list[tk.Widget] = []
        # Progreso: la barra pasa a "marquesina" (indeterminada) mientras no se
        # conoce el total (exploración/conteo) y el estado muestra %/ETA cuando sí.
        self._barra_indeterminada = False
        self._prog_t0 = 0.0            # inicio de la tarea (para el ETA)
        self._prog_t_prev = 0.0       # marca de la última muestra
        self._prog_hechas_prev = 0    # unidades de la última muestra
        self._prog_rate = 0.0         # ritmo suavizado (unidades/seg), 0 = sin dato

        # Campos de entrada (declarativos): una StringVar por campo de una línea; los
        # campos de tipo "lista" (rutas multilínea) usan un Text (self._widgets_lista).
        # Se conservan los alias v_origen / v_destino para el resto del código.
        self.campos = self._campos()
        self._tiene_destino = any(c.clave == "destino" for c in self.campos)
        self.vars_entrada = {c.clave: tk.StringVar()
                             for c in self.campos if c.tipo != "lista"}
        self._widgets_lista: dict = {}                 # clave -> tk.Text (tipo "lista")
        self.v_origen = self.vars_entrada.setdefault("origen", tk.StringVar())
        self.v_destino = self.vars_entrada.setdefault("destino", tk.StringVar())
        self.v_estado = tk.StringVar(value="Listo.")
        # "Registro detallado" y las opciones de RENDIMIENTO (Hilos + Modo ligero)
        # son COMPARTIDAS: viven en App (v_hilos/v_ligero) y persisten entre tareas.
        self._ayudas_lbl: list[tk.Label] = []         # para ajustar el wraplength

        self._construir()
        self.v_origen.trace_add("write", self._origen_cambiado)
        # El vaciado de la cola lo hace App con un único temporizador para las
        # tres pestañas (menos despertares del bucle de eventos).

    def _campos(self) -> "list[Campo]":
        """Campos de entrada de la pestaña. Si `ENTRADAS` no está definido, se
        derivan de los atributos clásicos (origen [+ destino])."""
        if self.ENTRADAS is not None:
            return self.ENTRADAS
        campos = [Campo("origen", self.etiqueta_origen, self.tipo_origen,
                        filtros=self.filtros_origen, titulo_dialogo=self.titulo_dialogo)]
        if self.etiqueta_destino:
            campos.append(Campo("destino", self.etiqueta_destino, "carpeta_salida"))
        return campos

    # ---------------- construcción ----------------
    def _construir(self) -> None:
        self.configure(style=tema.TARJETA)          # el contenido es una tarjeta
        self.columnconfigure(0, weight=1)

        # ===== ARRIBA: campos de entrada declarativos (a todo el ancho) =====
        top = ttk.Frame(self, style=tema.TARJETA)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        top.columnconfigure(1, weight=1)
        r = 0
        for campo in self.campos:
            if campo.tipo == "lista":       # bloque propio de dos columnas (rutas + DnD)
                r = self._construir_campo_lista(top, campo, r)
                continue
            ttk.Label(top, text=campo.etiqueta, style=tema.LBL_TITULO).grid(
                row=r, column=0, sticky="w", padx=4, pady=4)
            entrada = ttk.Entry(top, textvariable=self.vars_entrada[campo.clave])
            entrada.grid(row=r, column=1, sticky="ew", padx=4, pady=4)
            self._bloqueables.append(entrada)
            if campo.clave == "origen":
                self.e_origen = entrada
            elif campo.clave == "destino":
                self.e_destino = entrada
                entrada.bind("<Key>",
                             lambda _e: setattr(self, "auto_destino", False))
            if campo.tipo != "texto":       # campos de ruta: fin visible + tooltip
                self._enganchar_ruta_larga(entrada, self.vars_entrada[campo.clave])
            if campo.tipo != "texto":       # los campos de texto no tienen Examinar
                boton = ttk.Button(top, text="Examinar...",
                                   command=lambda c=campo: self._examinar_campo(c))
                boton.grid(row=r, column=2, padx=4, pady=4)
                self._bloqueables.append(boton)
                if campo.clave == "origen":
                    self.b_examinar = boton
                elif campo.clave == "destino":
                    self.b_dest = boton
            r += 1
        if self.aviso:
            caja = tk.Frame(top)
            tema.estilo_caja_aviso(caja)
            caja.grid(row=r, column=0, columnspan=3, sticky="ew",
                      padx=4, pady=(6, 2))
            lbl_av = tk.Label(caja, text=self.aviso, wraplength=360, justify="left")
            tema.estilo_label(lbl_av, "danger", fondo=tema.PELIGRO_FONDO)
            lbl_av.pack(fill="x", padx=10, pady=7)
            # El texto se ajusta al ancho real de la caja (panel izquierdo estrecho).
            caja.bind("<Configure>",
                      lambda e, w=lbl_av: w.configure(wraplength=max(120, e.width - 24)))

        # ===== MEDIO: opciones agrupadas en secciones, con scroll vertical =====
        # (el contenido puede superar el alto de media pantalla; MarcoDesplazable
        #  lo hace desplazable y la barra solo aparece cuando hace falta.)
        self.rowconfigure(1, weight=1)
        marco = componentes.MarcoDesplazable(self, on_reconfigure=self._ajustar_ayudas)
        marco.grid(row=1, column=0, sticky="nsew", padx=8, pady=2)
        self._lienzo = marco.lienzo                     # para _ajustar_ayudas
        self.contenedor_ops = marco.interior            # donde _seccion coloca todo

        self.marco_ops: ttk.LabelFrame | None = None   # sección actual (la fija _seccion)
        self._fila_seccion = 0
        self._opciones()             # controles propios de la pestaña (por secciones)
        # Hilos + Modo ligero ya NO van aquí: son comunes y viven en el monitor
        # derecho (App._construir_rendimiento), compartidos por todas las tareas.

        # ===== ABAJO: botones + barra de progreso (por pestaña) =====
        bottom = ttk.Frame(self, style=tema.TARJETA)
        bottom.grid(row=2, column=0, sticky="ew", padx=8, pady=(2, 8))
        bottom.columnconfigure(0, weight=1)
        botones = ttk.Frame(bottom, style=tema.TARJETA)
        botones.grid(row=0, column=0, sticky="w")
        self.b_iniciar = ttk.Button(botones, text=self.texto_inicio,
                                    command=self._iniciar, style=self.estilo_accion)
        self.b_iniciar.pack(side="left")
        self.b_pausar = ttk.Button(botones, text="Pausar", command=self._pausar,
                                   state="disabled", style=tema.FANTASMA)
        self.b_pausar.pack(side="left", padx=6)
        # Cancelar: aborta la parte en curso (descartándola) y deja la tarea
        # reanudable desde el último punto guardado. Pide confirmación (modal).
        self.b_cancelar = ttk.Button(botones, text="Cancelar", command=self._cancelar,
                                     state="disabled", style=tema.FANTASMA)
        self.b_cancelar.pack(side="left")
        # El estado va en su propia fila: así nunca se recorta aunque la fuente
        # sea ancha (Space Mono) o el panel estrecho.
        self.lbl_estado = ttk.Label(bottom, textvariable=self.v_estado,
                                    style=tema.LBL_EXITO, anchor="w")
        self.lbl_estado.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.barra = ttk.Progressbar(bottom, maximum=1000, style=tema.BARRA)
        self.barra.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        # Acciones al terminar (no modales): "Abrir carpeta" y, si hay gemela que
        # consume el resultado, un enlace para saltar a ella (handoff visible).
        # Se crean ocultos (sin pack) y se muestran en _fin según el resultado.
        self.fila_acciones = ttk.Frame(bottom, style=tema.TARJETA)
        self.fila_acciones.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.b_abrir = ttk.Button(self.fila_acciones, text="Abrir carpeta",
                                  style=tema.FANTASMA, command=self._abrir_resultado)
        self.b_ir_gemela = ttk.Button(self.fila_acciones, style=tema.FANTASMA)
        self._ruta_resultado = ""

    # ---------------- secciones de opciones (LabelFrame por grupo) ----------------
    def _seccion(self, titulo: str) -> ttk.LabelFrame:
        """Abre una sección (LabelFrame con leyenda) dentro del contenedor de
        opciones y la fija como destino de los siguientes _add_control/_add_ayuda.
        Los controles se crean con self.marco_ops como padre, así que caen en la
        sección vigente sin cambiar cómo los construye cada pestaña."""
        lf = ttk.LabelFrame(self.contenedor_ops, text=titulo, padding=8,
                            style=tema.SECCION)
        lf.grid(row=self._fila_seccion, column=0, sticky="ew", pady=(0, 8))
        lf.columnconfigure(0, weight=1)
        self._fila_seccion += 1
        self.marco_ops = lf
        return lf

    def _add_control(self, widget: tk.Widget, sangria: int = 6) -> None:
        """Coloca un control en la sección de opciones vigente."""
        widget.pack(in_=self.marco_ops, side="top", anchor="w",
                    padx=(sangria, 6), pady=(6, 0))

    def _add_ayuda(self, texto: str) -> tk.Label:
        """Ayuda breve en gris bajo el último control, con margen a la izquierda."""
        lbl = tk.Label(self.marco_ops, text=texto, wraplength=360)
        tema.estilo_label(lbl, "muted")
        lbl.pack(side="top", anchor="w", fill="x", padx=(26, 8), pady=(0, 2))
        self._ayudas_lbl.append(lbl)
        return lbl

    def _tooltip_opcion(self, detalle: str, *widgets) -> None:
        """Adjunta a cada widget (el control y, si la hay, su línea de ayuda) un
        tooltip con información MÁS detallada de la opción, sin ningún aviso visual:
        aparece al pasar el ratón por encima. La descripción gris sigue visible."""
        if not detalle:
            return
        for w in widgets:
            if w is not None:
                componentes.Tooltip(w, detalle)

    def _ajustar_ayudas(self) -> None:
        """Ajusta el ancho de las ayudas al ancho visible del área de opciones."""
        ancho = self._lienzo.winfo_width() - 60
        if ancho > 120:
            for lbl in self._ayudas_lbl:
                lbl.configure(wraplength=ancho)

    # --- opciones declarativas: un control = una llamada -------------------
    # Cada helper crea el control en la sección vigente, lo añade a
    # self._bloqueables (se deshabilita mientras hay una tarea) y, si se pasa
    # `ayuda`, escribe la línea gris de ayuda debajo. Así una opción es una sola
    # línea y no se puede olvidar ni el bloqueo ni la ayuda.
    def _check(self, var: tk.BooleanVar, etiqueta: str, ayuda: str = "", *,
               detalle: str = "",
               command: Callable[[], None] | None = None) -> ttk.Checkbutton:
        c = ttk.Checkbutton(self.marco_ops, text=etiqueta, variable=var)
        if command is not None:
            c.configure(command=command)
        self._add_control(c)
        self._bloqueables.append(c)
        lbl = self._add_ayuda(ayuda) if ayuda else None
        self._tooltip_opcion(detalle, c, lbl)
        return c

    def _combo(self, var: tk.StringVar, etiqueta: str, valores, ayuda: str = "",
               *, detalle: str = "", width: int = 24) -> ttk.Combobox:
        fila = ttk.Frame(self.marco_ops, style=tema.TARJETA)
        ttk.Label(fila, text=etiqueta, style=tema.LBL_TITULO).pack(side="left")
        cb = ttk.Combobox(fila, textvariable=var, state="readonly",
                          width=width, values=list(valores))
        cb.pack(side="left", padx=(6, 0))
        self._add_control(fila)
        self._bloqueables.append(cb)
        lbl = self._add_ayuda(ayuda) if ayuda else None
        self._tooltip_opcion(detalle, cb, lbl)
        return cb

    def _entry(self, etiqueta: str, var: tk.StringVar, ayuda: str = "",
               *, detalle: str = "", width: int = 24) -> ttk.Entry:
        """Campo de texto (etiqueta + Entry) en la sección de opciones vigente.
        Lo registra como bloqueable y, si se pasa `ayuda`, la escribe debajo."""
        fila, entry = componentes.fila_texto(self.marco_ops, etiqueta, var, width=width)
        self._add_control(fila)
        self._bloqueables.append(entry)
        lbl = self._add_ayuda(ayuda) if ayuda else None
        self._tooltip_opcion(detalle, entry, lbl)
        return entry

    def opciones_comunes(self) -> "tuple[bool, recursos.PoliticaHilos]":
        """(detallado, política de hilos) COMUNES a todas las tareas, leídas del
        contexto (monitor compartido). Las pestañas usan esto, no `app.v_*`."""
        return self.app.opciones_comunes()

    def _detallado(self) -> bool:
        """¿'Registro detallado' activo? (opción común del monitor)."""
        return self.opciones_comunes()[0]

    def _politica(self) -> recursos.PoliticaHilos:
        """La PoliticaHilos COMÚN (Hilos + Modo ligero), del contexto compartido."""
        return self.opciones_comunes()[1]

    # ---------------- ganchos que redefine cada pestaña ----------------
    def _opciones(self) -> None:
        """Añade a self.marco_ops los controles propios de la pestaña (con
        _add_control + _add_ayuda). Cada pestaña lo redefine."""

    def _destino_automatico(self, origen: str) -> str:
        return ""

    def _validar(self) -> dict:
        """Valida en el HILO PRINCIPAL y devuelve el dict que consumirá el motor:
        {"entradas": {clave: valor, ...}, "opts": <Opciones>}. Toda lectura de
        variables Tk (self.valor(...), self.opciones_comunes()) se hace aquí, no en
        el hilo de trabajo (Tk no es seguro entre hilos). Lanza ValueError si falta algo."""
        raise NotImplementedError

    def _confirmar(self, datos: dict) -> bool:
        return True

    def _confirmador(self) -> "Callable[[str, bool], bool] | None":
        """Confirmación que el motor puede pedir DURANTE la tarea (p.ej.
        sobrescribir). None = no preguntar. Solo Descomprimir lo usa."""
        return None

    def _preguntar_reanudar(self, datos: dict) -> "bool | None":
        """Reanudación tras cerrar (roadmap_reanudar.md). Si el motor expone
        `info_reanudable(entradas, opts)` y detecta una tarea a medias (mismo
        origen/opciones), pregunta al usuario. Devuelve: False = continuar donde se
        quedó (comportamiento normal), True = empezar de cero, None = cancelar.

        Si el motor no soporta detección o no hay progreso, devuelve False (seguir)."""
        info_fn = getattr(self.MOTOR, "info_reanudable", None)
        if info_fn is None:
            return False
        try:
            info = info_fn(datos["entradas"], datos["opts"])
        except Exception:                      # noqa: BLE001 — detección best-effort
            info = None
        if not info:
            return False
        fecha = info.get("fecha") or ""
        hechas = info.get("hechas", 0)
        total = info.get("total")
        cuenta = f"{hechas} de {total}" if total else f"{hechas}"
        cuando = f" del {fecha}" if fecha else ""
        # Diálogo con botones etiquetados (Continuar / Empezar de cero / Cancelar).
        # Devuelve directamente el contrato: False=continuar, True=de cero, None=cancelar.
        mensaje = (f"Se encontró una tarea a medias{cuando} ({cuenta} ya hechas).\n\n"
                   "¿Continuar donde se quedó o empezar de cero?")
        return componentes.dialogo_reanudar(self, mensaje)

    def _ejecutar(self, datos: dict, log: Callable[[str], None],
                  progreso: Callable[[int, int, float, str], None],
                  pausar: Callable[[], bool],
                  cancelar: Callable[[], bool]) -> Resultado:
        """Genérico (B): delega en el motor de la pestaña con el contrato
        uniforme `ejecutar(entradas, opts, *, callbacks)`. Corre en el HILO DE
        TRABAJO; usa solo lo que _validar dejó en 'datos'."""
        return self.MOTOR.ejecutar(datos["entradas"], datos["opts"], log=log,
                                   progreso=progreso, pausar=pausar, cancelar=cancelar,
                                   confirmar=self._confirmador())

    def _ejecutar_en_orden(self, origenes, opts, log, progreso, pausar,
                           cancelar) -> Resultado:
        """Ejecuta `MOTOR.ejecutar` una vez por cada carpeta de `origenes`, EN EL
        ORDEN de la lista. Agrega procesadas/total/errores/segundos; se detiene si el
        usuario pausa o cancela (devuelve ese estado). Lo usan las tareas que aceptan
        varias carpetas (Renombrar, Eliminar). El progreso lleva el prefijo [i/n]."""
        conf = self._confirmador()
        n = len(origenes)
        proc = total = 0
        errores: list[str] = []
        seg = 0.0
        hubo_completado = False
        for i, carpeta in enumerate(origenes, 1):
            if pausar() or cancelar():
                estado = (EstadoResultado.PAUSADO if pausar()
                          else EstadoResultado.CANCELADO)
                return Resultado(estado, proc, n - i + 1, total, errores, None,
                                 "Interrumpido entre carpetas.", seg)
            if n > 1:
                log(f"\n=== Carpeta {i}/{n}: {carpeta} ===")
            pref = f"[{i}/{n}] " if n > 1 else ""
            prog = ((lambda h, t, f, et, _p=pref: progreso(h, t, f, _p + et))
                    if progreso else None)
            res = self.MOTOR.ejecutar({"origen": carpeta}, opts, log=log,
                                      progreso=prog, pausar=pausar, cancelar=cancelar,
                                      confirmar=conf)
            proc += res.procesadas
            total += res.total
            errores += res.errores
            seg += res.segundos
            if res.estado == EstadoResultado.COMPLETADO:
                hubo_completado = True
            if res.estado in (EstadoResultado.PAUSADO, EstadoResultado.CANCELADO):
                return Resultado(res.estado, proc, n - i, total, errores, None,
                                 res.mensaje, seg)
        if errores:
            estado = EstadoResultado.ERROR
        elif hubo_completado:
            estado = EstadoResultado.COMPLETADO
        else:
            estado = EstadoResultado.NADA
        ruta = origenes[0] if n == 1 else None      # 'Abrir' solo tiene sentido con una
        return Resultado(estado, proc, 0, total, errores, ruta, "", seg)

    def _al_terminar(self, res: Resultado) -> None:
        """Se llama en el hilo de la ventana cuando acaba el trabajo."""

    # ---------------- selectores ----------------
    def valor(self, clave: str) -> str:
        """Valor (sin espacios) de un campo de una línea, para usar en _validar."""
        return self.vars_entrada[clave].get().strip()

    def valores_lista(self, clave: str) -> list[str]:
        """Rutas no vacías (una por línea) de un campo de tipo 'lista'."""
        w = self._widgets_lista.get(clave)
        if w is None:
            return []
        return [ln.strip() for ln in w.get("1.0", "end").splitlines() if ln.strip()]

    def _construir_campo_lista(self, top: tk.Misc, campo: "Campo", r: int) -> int:
        """Campo 'lista' en DOS columnas, siempre visible:
        - Izquierda (fija arriba): etiqueta, 'Examinar…' (añade varias carpetas) y la
          zona de arrastrar y soltar (que ABSORBE el alto extra al agrandar el Text).
        - Derecha: el Text multilínea (una ruta por línea) ocupando ancho y alto; se
          puede AGRANDAR arrastrando su borde inferior y trae barra vertical (solo
          cuando el contenido no cabe) cuya rueda no arrastra los demás marcos.
        Devuelve la siguiente fila."""
        cont = ttk.Frame(top, style=tema.TARJETA)
        cont.grid(row=r, column=0, columnspan=3, sticky="nsew", padx=4, pady=4)
        cont.columnconfigure(1, weight=1)              # la columna del Text se expande
        cont.rowconfigure(0, weight=1)

        # --- Columna izquierda: etiqueta + Examinar (fijos arriba) + zona DnD ---
        izq = ttk.Frame(cont, style=tema.TARJETA)
        izq.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        izq.columnconfigure(0, weight=1)               # sus hijos ocupan todo el ancho
        izq.rowconfigure(2, weight=1, minsize=52)      # la zona DnD absorbe el alto extra
        ttk.Label(izq, text=campo.etiqueta, style=tema.LBL_TITULO).grid(
            row=0, column=0, sticky="w")

        # --- Columna derecha: Text + barra vertical + tirador de redimensionado ---
        caja = ttk.Frame(cont, style=tema.TARJETA)
        caja.grid(row=0, column=1, sticky="nsew")
        caja.columnconfigure(0, weight=1)
        caja.rowconfigure(0, weight=1)
        txt = tk.Text(caja, height=4, wrap="char")
        tema.estilo_text(txt)
        txt.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(caja, orient="vertical", command=txt.yview,
                           style="Vertical.TScrollbar")
        sb.grid(row=0, column=1, sticky="ns")

        def _auto_sb(lo, hi, _sb=sb):
            """La barra solo aparece cuando el contenido no cabe (auto-ocultado)."""
            if float(lo) <= 0.0 and float(hi) >= 1.0:
                _sb.grid_remove()
            else:
                _sb.grid()
            _sb.set(lo, hi)
        txt.configure(yscrollcommand=_auto_sb)

        def _rueda_texto(e, t=txt):
            """La rueda desplaza SOLO este Text (no propaga al resto de marcos).
            Normalizada entre plataformas (Windows/macOS/Linux)."""
            pasos = componentes.pasos_rueda(e)
            if pasos:
                t.yview_scroll(pasos, "units")
            return "break"
        for _sec in componentes.SECUENCIAS_RUEDA:
            txt.bind(_sec, _rueda_texto)

        # Placeholder (texto guía) SUPERPUESTO al Text: explica cómo se usa la lista.
        # Es una Label encima, no texto dentro del Text, así la lectura de rutas
        # (valores_lista) y el resto de la lógica no se ven afectados. Se oculta en
        # cuanto hay contenido y reaparece si se vacía.
        ph = tk.Label(
            caja, justify="left", anchor="nw", bg=tema.NEGRO, fg=tema.MUTED,
            font=tema.FUENTES["peque"], wraplength=320,
            text=("Escribe aquí los directorios, uno por línea.\n"
                  "Los duplicados se ignoran automáticamente."))
        ph.bind("<Button-1>", lambda _e, t=txt: t.focus_set())   # clic = editar el Text
        txt._ph = ph                                             # lo usa _sync_placeholder
        txt.bind("<Configure>",
                 lambda _e, t=txt, p=ph: p.configure(wraplength=max(60, t.winfo_width() - 14)),
                 add="+")
        txt.bind("<KeyRelease>", lambda _e, t=txt: self._sync_placeholder(t), add="+")
        self._sync_placeholder(txt)                              # estado inicial (vacío)

        # Tirador: arrastrar hacia abajo agranda el Text (en líneas), hacia arriba
        # lo encoge. Se calcula el alto de línea de su fuente para un paso natural.
        grip = tk.Frame(caja, height=6, bg=tema.BORDE, cursor="sb_v_double_arrow")
        grip.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        try:
            lh = max(1, tkfont.Font(font=txt.cget("font")).metrics("linespace"))
        except tk.TclError:
            lh = 16
        arr = {}

        def _grip_ini(e, d=arr, t=txt):
            d["y"], d["h"] = e.y_root, int(t.cget("height"))

        def _grip_mov(e, d=arr, t=txt, _lh=lh):
            if "y" not in d:
                return
            t.configure(height=max(2, min(40, d["h"] + (e.y_root - d["y"]) // _lh)))
        grip.bind("<Button-1>", _grip_ini)
        grip.bind("<B1-Motion>", _grip_mov)

        self._widgets_lista[campo.clave] = txt
        examinar = ttk.Button(izq, text="Examinar...",
                              command=lambda t=txt, c=campo: self._anexar_carpeta(t, c))
        examinar.grid(row=1, column=0, sticky="ew", pady=(4, 4))   # a todo el ancho
        self._bloqueables += [txt, examinar]

        # Zona de "arrastrar y soltar" carpetas (opcional): SIEMPRE visible en la
        # columna izquierda cuando el soporte está disponible (se intenta registrar
        # como destino de soltado; si el registro fallara, la caja sigue mostrándose).
        if dnd.soporta_dnd():
            zona = tk.Label(izq, text="⤓  Arrastra aquí\ncarpetas para añadirlas")
            tema.estilo_zona_soltar(zona)
            zona.grid(row=2, column=0, sticky="nsew", pady=(4, 0))

            def _soltar(e, t=txt, z=zona):
                tema.estilo_zona_soltar(z, activa=False)
                if str(t.cget("state")) == "disabled":     # no tocar durante una tarea
                    return
                self._anexar_rutas(t, dnd.solo_directorios(
                    dnd.parsear_rutas(self, e.data)))

            dnd.registrar_zona(
                zona, _soltar,
                on_enter=lambda e, z=zona: tema.estilo_zona_soltar(z, activa=True),
                on_leave=lambda e, z=zona: tema.estilo_zona_soltar(z, activa=False))
        return r + 1

    def _sync_placeholder(self, txt) -> None:
        """Muestra el texto guía superpuesto cuando el Text está vacío y lo oculta en
        cuanto hay contenido. Robusto: no hace nada si el Text no tiene placeholder."""
        ph = getattr(txt, "_ph", None)
        if ph is None:
            return
        try:
            if txt.get("1.0", "end").strip():
                ph.place_forget()
            else:
                ph.place(x=6, y=4)
        except tk.TclError:
            pass

    @staticmethod
    def _norm_ruta(p: str) -> str:
        """Clave normalizada de una ruta para comparar duplicados."""
        return os.path.normcase(os.path.normpath(p.strip()))

    def _anexar_rutas(self, txt, rutas) -> int:
        """Añade `rutas` al Text (una por línea) IGNORANDO las que ya estén
        (comparación normalizada, también entre las nuevas). Lo comparten 'Examinar'
        y el 'soltar' (drag & drop). Devuelve cuántas se añadieron (0 si ninguna)."""
        existentes = {self._norm_ruta(ln) for ln in txt.get("1.0", "end").splitlines()
                      if ln.strip()}
        nuevas = []
        for d in rutas:
            if d and d.strip() and self._norm_ruta(d) not in existentes:
                existentes.add(self._norm_ruta(d))
                nuevas.append(d.strip())
        if not nuevas:
            return 0
        previo = txt.get("1.0", "end").strip("\n")
        txt.delete("1.0", "end")
        txt.insert("1.0", (previo + "\n" if previo else "") + "\n".join(nuevas) + "\n")
        self._sync_placeholder(txt)          # ya hay contenido: oculta el texto guía
        return len(nuevas)

    def _anexar_carpeta(self, txt, campo=None) -> None:
        """Añade UNA carpeta con el diálogo estándar: se elige y se cierra (sin tener
        que Cancelar para terminar). Para añadir VARIAS a la vez está el arrastrar y
        soltar. Ignora la carpeta si ya está en la lista."""
        titulo = (campo.titulo_dialogo if campo and campo.titulo_dialogo
                  else "Añade un directorio")
        elegida = filedialog.askdirectory(
            title=titulo, parent=self,
            initialdir=self.app.ultima_carpeta_dialogo() or None)
        if not elegida:
            return
        if self._anexar_rutas(txt, [elegida]):
            self._recordar_carpeta(elegida)

    def _examinar_campo(self, campo: "Campo") -> None:
        """Abre el diálogo adecuado al tipo del campo y fija su valor. Arranca en la
        última carpeta usada (recordada entre sesiones)."""
        inicial = self.app.ultima_carpeta_dialogo() or None
        if campo.tipo == "archivo":
            elegido = filedialog.askopenfilename(
                title=campo.titulo_dialogo or self.titulo_dialogo,
                initialdir=inicial,
                filetypes=campo.filtros or [("Todos los archivos", "*.*")])
        else:                              # carpeta / carpeta_salida
            titulo = (self.titulo_dialogo if campo.clave == "origen"
                      else "Elige la carpeta de destino")
            elegido = filedialog.askdirectory(title=titulo, initialdir=inicial)
        if not elegido:
            return
        if campo.clave == "origen":
            self.auto_destino = True
        elif campo.clave == "destino":
            self.auto_destino = False
        self.vars_entrada[campo.clave].set(elegido)
        self._recordar_carpeta(elegido)

    def _recordar_carpeta(self, ruta: str) -> None:
        """Recuerda la carpeta del elemento elegido (su carpeta contenedora si es un
        archivo) para que el próximo diálogo arranque ahí."""
        carpeta = ruta if os.path.isdir(ruta) else os.path.dirname(ruta)
        if carpeta:
            self.app.recordar_carpeta_dialogo(carpeta)

    def _enganchar_ruta_larga(self, entrada: "ttk.Entry", var: tk.StringVar) -> None:
        """En un campo de ruta: al cambiar el valor, desplaza la vista al FINAL (una
        ruta larga muestra el nombre, no el principio) y ofrece la ruta completa en un
        tooltip."""
        tip = componentes.Tooltip(entrada)

        def _al_cambiar(*_a) -> None:
            entrada.xview_moveto(1.0)
            tip.actualizar(var.get())

        var.trace_add("write", _al_cambiar)

    def _origen_cambiado(self, *_a) -> None:
        if self._tiene_destino and self.auto_destino:
            self.v_destino.set(self._destino_automatico(self.v_origen.get().strip()))

    def establecer_origen(self, ruta: str) -> None:
        self.auto_destino = True
        self.v_origen.set(ruta)

    # ---------------- registro (COMPARTIDO en App) ----------------
    def escribir(self, linea: str) -> None:
        self.app.escribir_lote([linea])

    def escribir_lote(self, lineas: list[str]) -> None:
        self.app.escribir_lote(lineas)

    # ---------------- control ----------------
    def _estado(self, texto: str, estilo: str = tema.LBL_EXITO) -> None:
        """Fija el texto de estado y su color (Listo/Completado=lima,
        Trabajando/progreso=verde, Pausado/Cancelado=ámbar, Error=rojo)."""
        self.v_estado.set(texto)
        self.lbl_estado.configure(style=estilo)

    @property
    def hilo(self):
        """Hilo de trabajo actual (o None). Lo posee la máquina de ejecución."""
        return self._ejec.hilo

    def ocupada(self) -> bool:
        return self._ejec.ocupada()

    def pedir_cierre(self) -> None:
        self.cerrando = True
        self._ejec.pedir_pausa()
        self._estado("Cerrando: terminando la parte en curso...", tema.LBL_PAUSA)

    def _iniciar(self) -> None:
        if self.ocupada():
            return
        try:
            datos = self._validar()
        except ValueError as e:
            messagebox.showerror("No se puede empezar", str(e), parent=self)
            return
        # Reanudación tras cerrar (roadmap_reanudar.md): si el motor detecta una
        # tarea a medias con el mismo origen/opciones, preguntar continuar/de cero.
        # NO se pregunta al continuar una tarea pausada en la misma sesión (el
        # usuario acaba de pulsar "Continuar"): el modal es solo para tras cerrar.
        if not self._reanudando_en_sesion:
            reiniciar = self._preguntar_reanudar(datos)
            if reiniciar is None:              # el usuario canceló
                return
            if reiniciar and hasattr(datos["opts"], "reiniciar"):
                datos["opts"].reiniciar = True  # solo si el motor lo soporta
        if not self._confirmar(datos):
            return

        self.b_iniciar.configure(state="disabled")
        self.b_pausar.configure(state="normal")
        self.b_cancelar.configure(state="normal")
        for w in self._bloqueables:
            w.configure(state="disabled")
        self._estado("Trabajando...", tema.LBL_TRABAJANDO)
        self._reset_progreso()
        self.b_abrir.pack_forget()               # oculta acciones de una tarea previa
        self.b_ir_gemela.pack_forget()
        self.escribir(f"\n=== {ahora()} ===")

        # El trabajo corre en un hilo (Ejecucion); _ejecutar usa solo lo de 'datos'.
        self._ejec.iniciar(
            lambda log, progreso, pausar, cancelar:
            self._ejecutar(datos, log, progreso, pausar, cancelar))
        # Una sola tarea a la vez: se bloquea el acceso al resto de pestañas.
        self.app.bloquear(self)

    def _pausar(self) -> None:
        self._ejec.pedir_pausa()
        self.b_pausar.configure(state="disabled")
        self._estado("Pausando: terminando la parte en curso...", tema.LBL_PAUSA)

    def _cancelar(self) -> None:
        """Cancela la tarea en curso, previo aviso. A diferencia de Pausar (que espera
        a que la parte en curso termine), Cancelar la ABORTA y descarta su fragmento a
        medias; el avance queda en el último punto guardado, así que se puede reanudar."""
        if not messagebox.askyesno(
                "Cancelar",
                "Se cancelará la tarea en curso. La parte que se esté procesando en "
                "este momento se descarta, pero podrás reanudar desde el último punto "
                "guardado.\n\n¿Cancelar?",
                parent=self):
            return
        self._ejec.pedir_cancelar()
        self.b_cancelar.configure(state="disabled")
        self.b_pausar.configure(state="disabled")
        self._estado("Cancelando: descartando la parte en curso...", tema.LBL_PAUSA)

    def procesar_cola(self) -> None:
        """Drena los eventos del hilo de trabajo y actualiza la UI. La llama App
        cada 150 ms. El drenado (sin Tk) lo hace la máquina de ejecución."""
        lineas, ultimo_progreso, finales = self._ejec.recoger()
        if lineas:
            self.escribir_lote(lineas)
        if ultimo_progreso is not None:
            hechas, total, frac, etiqueta = ultimo_progreso
            if total:
                self._barra_modo(False)                # determinada: %
                self.barra["value"] = max(0, min(1000, int(frac * 1000)))
            else:
                self._barra_modo(True)                 # total desconocido: marquesina
            # Mientras se pausa o se cancela, no pisar el texto de estado ("Pausando…"
            # / "Cancelando…") con el progreso en curso.
            if not self._ejec.pausa.is_set() and not self._ejec.cancela.is_set():
                self._estado(self._texto_progreso(hechas, total, frac, etiqueta),
                             tema.LBL_TRABAJANDO)
        for res in finales:
            self._fin(res)

    # ---------------- progreso (barra + estado con %/ETA) ----------------
    def _reset_progreso(self) -> None:
        """Deja la barra determinada a 0 y reinicia el cálculo del ETA."""
        self._barra_modo(False)
        self.barra["value"] = 0
        self._prog_t0 = self._prog_t_prev = time.monotonic()
        self._prog_hechas_prev = 0
        self._prog_rate = 0.0

    def _barra_modo(self, indeterminada: bool) -> None:
        """Cambia la barra entre determinada (muestra %) e indeterminada
        (marquesina, mientras no se conoce el total). Idempotente."""
        if indeterminada == self._barra_indeterminada:
            return
        self._barra_indeterminada = indeterminada
        if indeterminada:
            self.barra.configure(mode="indeterminate")
            self.barra.start(60)                       # ms por paso de la marquesina
        else:
            self.barra.stop()
            self.barra.configure(mode="determinate")

    def _texto_progreso(self, hechas: int, total: int, frac: float,
                        etiqueta: str) -> str:
        """Estado en curso: sin total, 'hechas — etiqueta'; con total, añade el
        porcentaje y, cuando el ritmo se estabiliza, un ETA aproximado."""
        if not total:
            return f"{hechas} — {etiqueta}"
        pct = max(0, min(100, int(frac * 100)))
        eta = self._eta(hechas, total)
        return f"{pct} % · {hechas}/{total}{eta} — {etiqueta}"

    def _eta(self, hechas: int, total: int) -> str:
        """ETA aproximado por media móvil del ritmo (unidades/seg). Devuelve '' hasta
        tener una muestra fiable (evita cifras erráticas al arrancar)."""
        ahora_t = time.monotonic()
        dt = ahora_t - self._prog_t_prev
        d_hechas = hechas - self._prog_hechas_prev
        if dt >= 0.2 and d_hechas > 0:                 # actualiza el ritmo suavizado
            ritmo = d_hechas / dt
            self._prog_rate = (0.3 * ritmo + 0.7 * self._prog_rate
                               if self._prog_rate else ritmo)
            self._prog_t_prev = ahora_t
            self._prog_hechas_prev = hechas
        # Solo tras un pequeño calentamiento y con ritmo positivo.
        if self._prog_rate > 0 and hechas < total and (ahora_t - self._prog_t0) > 1.0:
            seg = (total - hechas) / self._prog_rate
            return f" · ~{duracion(seg)}"
        return ""

    def _fin(self, res: Resultado) -> None:
        self._barra_modo(False)                  # detiene la marquesina si estaba activa
        for w in self._bloqueables:
            w.configure(state="normal")
        self.b_pausar.configure(state="disabled")
        self.b_cancelar.configure(state="disabled")
        self.b_iniciar.configure(state="normal")
        # Si quedó pausada O CANCELADA en esta sesión, el próximo "Continuar" reanuda
        # sin modal; cualquier otro final (completada/error) reactiva el modal.
        self._reanudando_en_sesion = res.estado in (EstadoResultado.PAUSADO,
                                                    EstadoResultado.CANCELADO)

        if res.estado == EstadoResultado.COMPLETADO:
            self.b_iniciar.configure(text=self.texto_inicio)
            self.barra["value"] = 1000
            self._estado(f"Completado en {duracion(res.segundos)}.", tema.LBL_EXITO)
            if res.ruta_final:                   # deja constancia de la ruta (sin modal)
                self.escribir(f"Completado: {res.ruta_final}")
        elif res.estado == EstadoResultado.NADA:
            self._estado("No había nada que hacer.", tema.LBL_EXITO)
        elif res.estado == EstadoResultado.PAUSADO:
            self.b_iniciar.configure(text="Continuar")
            self._estado(f"Pausado: quedan {res.restantes}.", tema.LBL_PAUSA)
        elif res.estado == EstadoResultado.CANCELADO:
            # Cancelada: reanudable desde el último punto guardado ("Continuar").
            self.b_iniciar.configure(text="Continuar")
            if res.restantes:
                self._estado(f"Cancelado: quedan {res.restantes}.", tema.LBL_PAUSA)
            else:
                self._estado("Cancelado.", tema.LBL_PAUSA)
        elif res.estado == EstadoResultado.ERROR:
            self.b_iniciar.configure(text="Continuar")
            self._estado("Error.", tema.LBL_PELIGRO)
            self.escribir(f"[!] {res.mensaje}")
            if not self.cerrando:
                messagebox.showerror("Error", res.mensaje, parent=self)
        else:
            self._estado("Cancelado.", tema.LBL_PAUSA)

        # Handoff: ofrecer la salida a la pestaña que CONSUME este artefacto (el
        # Registro casa produce->consume; la productora no nombra a la consumidora).
        receptora = None
        if (self.produce and res.ruta_final
                and res.estado in (EstadoResultado.COMPLETADO, EstadoResultado.NADA)):
            receptora = self.app.sugerir_entrada(res.ruta_final, self.produce,
                                                 excepto=self)
        self._acciones_finales(res, receptora)
        if not self.cerrando:
            self._al_terminar(res)
        self.app.desbloquear()               # se reactiva el acceso a las pestañas
        if self.cerrando:
            self.app.comprobar_cierre()

    # ---------------- remate final: acciones no modales ----------------
    def _acciones_finales(self, res: Resultado, receptora) -> None:
        """Al completar, muestra las acciones no modales: "Abrir carpeta" del
        resultado y, si el handoff casó una gemela, un enlace para saltar a ella.
        Sustituye a los `messagebox.showinfo` de fin que interrumpían."""
        completada = res.estado in (EstadoResultado.COMPLETADO, EstadoResultado.NADA)
        if completada and res.ruta_final and self.ofrece_abrir:
            self._ruta_resultado = str(res.ruta_final)
            self.b_abrir.pack(side="left", padx=(0, 6))
        else:
            self.b_abrir.pack_forget()
        if receptora is not None:
            self.b_ir_gemela.configure(
                text=f"Ir a {receptora.nombre} →",
                command=lambda r=receptora: self.app.mostrar(type(r)))
            self.b_ir_gemela.pack(side="left")
        else:
            self.b_ir_gemela.pack_forget()

    def _abrir_resultado(self) -> None:
        """Abre en el explorador la carpeta del último resultado (botón del remate)."""
        if self._ruta_resultado:
            componentes.abrir_en_explorador(self._ruta_resultado)
