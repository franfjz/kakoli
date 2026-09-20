# -*- coding: utf-8 -*-
"""app — la ventana principal (App): portada de categorías en dos niveles, monitor
derecho común (equipo + rendimiento + consola + info), vista de Ayuda y el bucle de
eventos que reparte el trabajo de las pestañas.

App NO conoce las tareas concretas: recibe un `Registro` (core/registro.py) con las
categorías y sus tareas, e instancia cada pestaña a partir de la clase (fábrica de
UI) que trae su descriptor. La raíz de composición (kakoli.py) le pasa el REGISTRO
que arma el manifiesto `tasks/`."""
from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from core import recursos
from core.registro import Categoria, Registro
from gui import tema
from gui import componentes
from gui import preferencias
from gui import marco_ventana
from gui.pestana_base import PestanaBase
from gui.ayuda import AYUDA_INTRO, AYUDA_TAREAS, AYUDA_CIERRE
from gui.constantes import (
    AUTOR, ICONO_CAFE, INTERVALO_BOMBA_MS, LINEAS_A_CONSERVAR,
    MAX_LINEAS_REGISTRO, SUBTITULO, URL_AUTOR, URL_CAFE, VERSION, politica_desde)


class App(tk.Tk):
    """Ventana principal. Se construye con un `Registro` de tareas; añadir una
    tarea o categoría se hace en ese registro (manifiesto tasks/), no aquí."""

    def __init__(self, registro: Registro) -> None:
        tema.activar_dpi()             # DPI-aware ANTES de crear el root (HiDPI nítido)
        super().__init__()
        self.registro = registro
        self.title("kakoli")
        # Ajustes persistentes entre sesiones (rendimiento, última tarea, carpeta
        # de diálogos, geometría). Robusto: si falta o está corrupto, `{}`.
        self._prefs = preferencias.cargar()
        tema.configurar(self)          # tema retro (colores/fuentes) — Fase 2
        tema.aplicar_icono(self)       # icono de la app en la barra de título
        self._restaurar_geometria()    # geometría guardada o maximizada por defecto
        self.cerrando = False

        # Se mide el equipo UNA vez para saber qué opciones de rendimiento tienen
        # sentido aquí (p.ej. cuántos hilos aprovecha sin perjudicarse). Robusto:
        # si fallara, no se atenúa nada.
        try:
            self.perfil_base = recursos.perfil()
            self.techo_hilos = recursos.techo_hilos(self.perfil_base)
        except Exception:  # noqa: BLE001
            self.perfil_base = None
            self.techo_hilos = 99

        # "Registro detallado", el registro y las opciones de RENDIMIENTO (Hilos +
        # Modo ligero) son ÚNICOS: compartidos por todas las tareas y persistentes.
        # Rendimiento y registro: valores guardados o los de serie. El nº de hilos
        # se valida contra ESTE equipo (si se guardó en otra máquina más potente y
        # ya no es seleccionable, se cae a 'Auto').
        self.v_detallado = tk.BooleanVar(value=bool(self._prefs.get("detallado", False)))
        self.v_hilos = tk.StringVar(value=self._hilos_validos(
            self._prefs.get("hilos", "Auto")))
        self.v_ligero = tk.BooleanVar(value=bool(self._prefs.get("ligero", True)))
        self._perf_bloqueables: "list[tuple[tk.Widget, str]]" = []

        # Layout: [ Navegador (expandible) ‖ Monitor ] con divisor arrastrable.
        # El navegador lleva weight=1 (absorbe el redimensionado) y el monitor
        # weight=0 (conserva su ancho); el usuario mueve el "sash" y su posición se
        # recuerda entre sesiones (ver _restaurar_sash / _guardar_prefs).
        princ = ttk.Frame(self)
        princ.pack(fill="both", expand=True, padx=8, pady=8)
        self._paned = ttk.PanedWindow(princ, orient="horizontal")
        self._paned.pack(fill="both", expand=True)

        # Panel izquierdo = barra de navegación (repoblable) + área de la tarea.
        izq = ttk.Frame(self._paned, style=tema.TARJETA)
        izq.rowconfigure(1, weight=1)
        izq.columnconfigure(0, weight=1)
        self.barra_nav = ttk.Frame(izq, style=tema.TARJETA)
        self.barra_nav.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.area_tarea = ttk.Frame(izq, style=tema.TARJETA)
        self.area_tarea.grid(row=1, column=0, sticky="nsew")
        self.area_tarea.rowconfigure(0, weight=1)
        self.area_tarea.columnconfigure(0, weight=1)
        self._paned.add(izq, weight=1)

        self._construir_monitor(self._paned)               # panel derecho compartido

        # La posición del divisor se fija cuando el paned tiene ya un tamaño real.
        self._sash_restaurado = False
        self._paned.bind("<Configure>", self._al_configurar_paned)
        # Respeta los anchos mínimos mientras el usuario arrastra el divisor.
        self._paned.bind("<B1-Motion>", self._clamp_sash, add="+")
        self._paned.bind("<ButtonRelease-1>", self._clamp_sash, add="+")

        # Las tareas se instancian PEREZOSAMENTE: cada pestaña (padre = area_tarea)
        # se crea la primera vez que se muestra, no al arrancar (arranque más rápido
        # en el equipo lento). `_clases` es el orden del registro; `_por_clase` la
        # caché de instancias ya creadas. `_instancia(clase)` crea-y-cachea.
        self._clases = tuple(d.clase for d in registro.descriptores())
        self._por_clase: dict = {}
        # id de tarea <-> clase (para persistir la navegación por un id estable, no
        # por el nombre de la clase, que podría cambiar al refactorizar).
        self._clase_por_id = {d.id: d.clase for d in registro.descriptores()}
        self._id_por_clase = {d.clase: d.id for d in registro.descriptores()}

        # Estado de navegación (dos niveles): None = nivel 1 (menú de categorías).
        self._categoria_actual: "Categoria | None" = None
        self._tarea_actual: "PestanaBase | None" = None
        self._bloqueado = False
        self._portada: "ttk.Frame | None" = None
        self._portada_interior: "ttk.Frame | None" = None
        self._ultima_tarea: dict = self._cargar_ultimas()  # categoría.nombre -> clase
        self._ayuda_frame: "ttk.Frame | None" = None       # vista README (Ayuda)
        self._en_ayuda = False
        self._ayuda_parrafos: "list[tk.Label]" = []
        self._restaurar_navegacion()                       # donde se dejó, o el menú

        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        # La "bomba" (drenado de colas) solo corre mientras hay una tarea en
        # marcha: se arma en bloquear() y se detiene sola al terminar, así el
        # proceso puede quedarse inactivo en reposo (CPU/batería). None = parada.
        self._id_bomba: "str | None" = None
        self._configurar_atajos()
        # Pre-calentado en reposo: al pulsar una pestaña por primera vez esta se
        # construye en el acto (se veía un instante la anterior y luego la correcta).
        # Para que el cambio sea instantáneo, tras el arranque —cuando la ventana ya
        # está pintada y el equipo, ocioso— se van construyendo OCULTAS las pestañas
        # aún no abiertas, una por tick y espaciadas, sin ralentizar el arranque ni
        # competir con una tarea en marcha.
        self._id_prewarm: "str | None" = self.after(900, self._precalentar_pestanas)

    # ---------------- atajos de teclado (Fase 6) ----------------
    def _configurar_atajos(self) -> None:
        """Atajos globales que actúan sobre la TAREA VISIBLE. Se enganchan al
        Toplevel: los eventos de teclado de los widgets hijos llegan siempre aquí
        (bindtags), tenga el foco donde lo tenga.

        - Ctrl+Enter: Iniciar/Continuar     - Ctrl+P: Pausar
        - Ctrl+.: Cancelar                   - Esc: volver al menú / cerrar Ayuda

        Iniciar/Pausar/Cancelar se hacen con `boton.invoke()`, que NO hace nada si el
        botón está deshabilitado: así el atajo respeta exactamente el mismo estado que
        el clic (p. ej. Pausar solo mientras se trabaja)."""
        self.bind("<Control-Return>", lambda _e: self._atajo_boton("b_iniciar"))
        self.bind("<Control-KP_Enter>", lambda _e: self._atajo_boton("b_iniciar"))
        self.bind("<Control-p>", lambda _e: self._atajo_boton("b_pausar"))
        self.bind("<Control-period>", lambda _e: self._atajo_boton("b_cancelar"))
        self.bind("<Escape>", self._atajo_escape)

    def _atajo_boton(self, attr: str) -> str:
        """Pulsa por teclado un botón de la tarea visible (respeta 'disabled')."""
        pes = self._tarea_actual
        if pes is not None and not self._en_ayuda:
            boton = getattr(pes, attr, None)
            if boton is not None:
                boton.invoke()
        return "break"

    def _atajo_escape(self, _e=None):
        """Esc: vuelve al menú (o cierra la Ayuda). No navega mientras hay una tarea
        en marcha, ni cuando el foco está en un campo editable (ahí Esc es del
        widget: cerrar un desplegable, etc.)."""
        if self._bloqueado:
            return None
        foco = self.focus_get()
        if isinstance(foco, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text, tk.Listbox)):
            return None
        if self._en_ayuda or self._tarea_actual is not None:
            self._ir_menu()
            return "break"
        return None

    # ---------------- instanciación perezosa de pestañas ----------------
    def _instancia(self, clase: "type[PestanaBase]") -> "PestanaBase":
        """Devuelve la pestaña `clase`, creándola (y cacheándola) la primera vez.
        Es el único punto que instancia una pestaña."""
        pes = self._por_clase.get(clase)
        if pes is None:
            pes = clase(self.area_tarea, self)
            self._por_clase[clase] = pes
        return pes

    @property
    def pestanas(self) -> "tuple[PestanaBase, ...]":
        """Las pestañas YA instanciadas (no fuerza crear las que no se han abierto).
        La bomba de colas y el cierre solo tienen que atender a estas."""
        return tuple(self._por_clase.values())

    def _precalentar_pestanas(self) -> None:
        """Construye en reposo, UNA por tick, las pestañas aún no abiertas (ocultas:
        no se hacen `grid`), para que cambiar a ellas luego sea instantáneo. No compite
        con una tarea en marcha (si está bloqueado, espera) y es best-effort. Se detiene
        sola cuando ya están todas."""
        self._id_prewarm = None
        if self.cerrando or not self.winfo_exists():
            return
        if not self._bloqueado:
            for clase in self._clases:
                if clase not in self._por_clase:
                    try:
                        self._instancia(clase)             # se crea oculta (sin grid)
                    except Exception:  # noqa: BLE001 — precalentar es una comodidad
                        pass
                    break
        if any(c not in self._por_clase for c in self._clases):
            # Quedan pestañas: reprograma (más espaciado si hay una tarea ocupando CPU).
            demora = 600 if self._bloqueado else 250
            self._id_prewarm = self.after(demora, self._precalentar_pestanas)

    # ---------------- navegación en dos niveles (categorías → tareas) --------
    def _pintar_barra(self) -> None:
        """Repuebla la barra según el nivel. En el **nivel 1 (portada) la barra se
        OCULTA**: la navegación son las tarjetas de categoría. En el nivel 2 muestra
        '←' + las tareas de la categoría. Respeta el bloqueo (una tarea a la vez)."""
        for w in self.barra_nav.winfo_children():
            w.destroy()
        if self._categoria_actual is None:                 # nivel 1: solo tarjetas
            self.barra_nav.grid_remove()                   # sin pestañas arriba
            return
        self.barra_nav.grid()                              # nivel 2: se muestra
        # nivel 2: volver + tareas de la categoría
        vol = ttk.Button(self.barra_nav, text="[ ← Menú ]", style=tema.PESTANA_VOLVER,
                         command=self._ir_menu,
                         state=("disabled" if self._bloqueado else "normal"))
        vol.pack(side="left", padx=(0, 8))
        componentes.Tooltip(vol, "Volver al menú de categorías (Esc)")
        for desc in self._categoria_actual.tareas:
            # No se instancia la pestaña solo para pintar la barra: el nombre y la
            # comparación de "activa" salen de la CLASE; se crea al pulsar.
            activa = (self._tarea_actual is not None
                      and type(self._tarea_actual) is desc.clase)
            estado = "disabled" if (self._bloqueado and not activa) else "normal"
            ttk.Button(self.barra_nav,
                       text=self._rotulo(desc.clase.nombre, activa and self._bloqueado),
                       style=(tema.PESTANA_ACT if activa else tema.PESTANA),
                       state=estado,
                       command=lambda c=desc.clase:
                       self._seleccionar(self._instancia(c))).pack(
                side="left", padx=(0, 4))

    def _ir_menu(self) -> None:
        """Vuelve al nivel 1 (portada). También cierra la vista de Ayuda si estaba."""
        if self._bloqueado:
            return
        if self._tarea_actual is not None:
            self._tarea_actual.grid_remove()
            self._tarea_actual = None
        if self._en_ayuda and self._ayuda_frame is not None:
            self._ayuda_frame.grid_remove()
            self._en_ayuda = False
        self._categoria_actual = None
        self._mostrar_portada()
        self._pintar_barra()

    def _entrar(self, categoria: "Categoria",
                clase: "type[PestanaBase] | None" = None) -> None:
        """Entra en una categoría (nivel 2) y muestra `clase`, o la última tarea usada
        (o la primera la primera vez) si no se indica. Se selecciona la tarea destino
        DE UNA (no se muestra una intermedia): así el handoff no enseña primero otra
        pestaña y luego la correcta."""
        if self._bloqueado:
            return
        self._categoria_actual = categoria
        clases = [d.clase for d in categoria.tareas]
        if clase is None or clase not in clases:
            clase = self._ultima_tarea.get(categoria.nombre, clases[0])
            if clase not in clases:                        # por si el registro cambió
                clase = clases[0]
        self._seleccionar(self._instancia(clase))

    def _seleccionar(self, pes: "PestanaBase") -> None:
        """Muestra el frame de una tarea (oculta el anterior) y repinta la barra.

        Para que el cambio no parpadee (no se vea un instante la pestaña anterior),
        la nueva se coloca y se sube ENCIMA (`tkraise`) ANTES de retirar la anterior:
        así nunca hay un fotograma con la vista vacía o con la de antes."""
        if self._bloqueado:
            return
        self._ocultar_portada()
        anterior = self._tarea_actual
        pes.grid(row=0, column=0, sticky="nsew")
        pes.tkraise()
        if anterior is not None and anterior is not pes:
            anterior.grid_remove()
        self._tarea_actual = pes
        if self._categoria_actual is not None:
            self._ultima_tarea[self._categoria_actual.nombre] = type(pes)
        self._pintar_barra()

    def mostrar(self, clase: type[PestanaBase]) -> "PestanaBase | None":
        """Navega hasta dejar visible la tarea `clase` (entra en su categoría y la
        selecciona). Para scripts/pruebas y para navegación tras un handoff."""
        for cat in self.registro.categorias:
            if clase in {d.clase for d in cat.tareas}:
                self._entrar(cat, clase)               # selecciona la destino de una
                return self._tarea_actual
        return None

    def estado_barra(self) -> "list[tuple[str, bool, bool]]":
        """(texto, habilitado, es_activa) de cada botón de la barra. Para pruebas."""
        out = []
        for w in self.barra_nav.winfo_children():
            if isinstance(w, ttk.Button):
                out.append((str(w.cget("text")),
                            str(w.cget("state")) != "disabled",
                            str(w.cget("style")) == tema.PESTANA_ACT))
        return out

    def _mostrar_portada(self) -> None:
        if self._portada is None:
            # Portada con scroll vertical: crece al añadir tareas y al reducir el
            # alto de la ventana. El margen de 8 px evita mostrar la barra por un
            # desbordamiento mínimo (redondeos del padding).
            cont = componentes.MarcoDesplazable(self.area_tarea, padding=16, margen=8)
            interior = cont.interior
            self._portada = cont
            self._portada_interior = interior
            ttk.Label(interior, text="Elige una categoría",
                      style=tema.LBL_TITULO).pack(anchor="w")
            ttk.Label(interior,
                      text="Cada categoría agrupa tareas relacionadas. Pulsa una "
                           "categoría para abrirla.",
                      style=tema.LBL_MUTED).pack(anchor="w", pady=(2, 12))
            for cat in self.registro.categorias:
                self._tarjeta_categoria(cat)
            self._tarjeta_ayuda()                          # tarjeta final: Ayuda
        self._portada.grid(row=0, column=0, sticky="nsew")

    def _tarjeta(self, titulo_txt: str, descripcion: str, sub_txt: str,
                 comando: "Callable[[], None]") -> None:
        """Tarjeta clicable de la portada: título (head) + descripción + subtítulo
        gris. `comando` se ejecuta al pulsarla."""
        card = tk.Frame(self._portada_interior)
        tema.estilo_tarjeta_menu(card)
        card.pack(fill="x", pady=(0, 8))
        titulo = tk.Label(card, text=titulo_txt)
        tema.estilo_label(titulo, "head")
        titulo.pack(anchor="w", padx=12, pady=(8, 0))
        etiquetas = [titulo]
        if descripcion:
            desc = tk.Label(card, text=descripcion, justify="left")
            tema.estilo_label(desc, "normal")
            desc.pack(anchor="w", padx=12, pady=(2, 0))
            etiquetas.append(desc)
        if sub_txt:
            sub = tk.Label(card, text=sub_txt)
            tema.estilo_label(sub, "muted")
            sub.pack(anchor="w", padx=12, pady=(0, 8))
            etiquetas.append(sub)
        for w in (card, *etiquetas):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda _e: comando())
            w.bind("<Enter>", lambda _e, f=card: tema.estilo_tarjeta_menu(f, True))
            w.bind("<Leave>", lambda _e, f=card: tema.estilo_tarjeta_menu(f, False))

    def _tarjeta_categoria(self, cat: "Categoria") -> None:
        """Tarjeta de una categoría: nombre + descripción + tareas que agrupa."""
        tareas = " · ".join(d.nombre for d in cat.tareas)
        self._tarjeta(cat.nombre, cat.descripcion, tareas,
                      lambda c=cat: self._entrar(c))

    def _tarjeta_ayuda(self) -> None:
        """Tarjeta final de la portada: abre la vista de Ayuda (README)."""
        self._tarjeta("Ayuda", "Guía detallada de todas las tareas y sus opciones.",
                      "Referencia técnica", self._entrar_ayuda)

    # ---------------- Ayuda (README de solo lectura) ----------------
    def _entrar_ayuda(self) -> None:
        """Muestra la vista de Ayuda (solo lectura) con la barra reducida a '←'."""
        self._ocultar_portada()
        if self._tarea_actual is not None:
            self._tarea_actual.grid_remove()
            self._tarea_actual = None
        self._construir_ayuda()
        self._ayuda_frame.grid(row=0, column=0, sticky="nsew")
        self._en_ayuda = True
        for w in self.barra_nav.winfo_children():
            w.destroy()
        self.barra_nav.grid()
        vol = ttk.Button(self.barra_nav, text="[ ← Menú ]", style=tema.PESTANA_VOLVER,
                         command=self._ir_menu)
        vol.pack(side="left", padx=(0, 8))
        componentes.Tooltip(vol, "Volver al menú de categorías (Esc)")

    def _construir_ayuda(self) -> None:
        """Construye una vez la vista de Ayuda: un Canvas con scroll vertical y el
        contenido de AYUDA_SECCIONES."""
        if self._ayuda_frame is not None:
            return
        # La barra de la Ayuda NO se auto-oculta (el contenido siempre desborda);
        # al redimensionar se ajusta el wraplength de los párrafos al ancho.
        cont = componentes.MarcoDesplazable(
            self.area_tarea, padding=12, auto_ocultar=False,
            on_reconfigure=lambda m=None: self._ajustar_ayuda_wrap(cont))
        self._render_ayuda(cont.interior)
        self._ayuda_frame = cont

    def _ajustar_ayuda_wrap(self, marco) -> None:
        ancho = marco.lienzo.winfo_width() - 40
        if ancho > 120:
            for lbl in self._ayuda_parrafos:
                lbl.configure(wraplength=ancho)

    def _secciones_ayuda(self) -> "list[tuple[str, list[str]]]":
        """Compone la Ayuda: intro general + la sección de cada tarea (del propio
        descriptor si la trae, si no de AYUDA_TAREAS) en orden de registro + cierre."""
        secciones = list(AYUDA_INTRO)
        for desc in self.registro.descriptores():
            secciones += (desc.ayuda if desc.ayuda is not None
                          else AYUDA_TAREAS.get(desc.id, []))
        secciones += AYUDA_CIERRE
        return secciones

    def _render_ayuda(self, interior: tk.Misc) -> None:
        """Pinta la Ayuda compuesta: cada sección = título (head) + párrafos."""
        for titulo, parrafos in self._secciones_ayuda():
            t = tk.Label(interior, text=titulo, justify="left")
            tema.estilo_label(t, "head")
            t.pack(anchor="w", pady=(12, 2))
            for p in parrafos:
                tono = "muted" if p.startswith("  ") else "normal"
                lbl = tk.Label(interior, text=p, justify="left")
                tema.estilo_label(lbl, tono)
                lbl.configure(wraplength=900)
                lbl.pack(anchor="w", pady=(0, 2))
                self._ayuda_parrafos.append(lbl)

    def _ocultar_portada(self) -> None:
        if self._portada is not None:
            self._portada.grid_remove()

    # ---------------- panel derecho COMPARTIDO (perfil + consola) ----------
    def _construir_monitor(self, paned: ttk.PanedWindow) -> None:
        mon = self._mon = ttk.Frame(paned, style=tema.TARJETA)
        mon.columnconfigure(0, weight=1)
        f = 0

        # 0) Controles de ventana (solo Windows, chrome propio): min/maximizar/cerrar
        #    arriba del panel derecho; la franja hace de asa para arrastrar.
        if marco_ventana.es_windows():
            self._construir_controles_ventana(mon, f)
            f += 1

        # 1) Equipo detectado (perfil del ordenador).
        perf = ttk.LabelFrame(mon, text="Equipo detectado", padding=6,
                              style=tema.SECCION)
        perf.grid(row=f, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        perf.columnconfigure(0, weight=1)
        self.lbl_perfil = tk.Label(perf, text=self._texto_perfil())
        tema.estilo_label(self.lbl_perfil, "normal")
        self.lbl_perfil.grid(row=0, column=0, sticky="ew")
        f += 1

        # 2) Rendimiento (Hilos + Modo ligero) — COMPARTIDO por todas las tareas.
        self._construir_rendimiento(mon, f)
        f += 1

        # 3) Consola: cabecera (título + "Registro detallado"), fila de acciones
        #    (Limpiar/Copiar/Guardar) y el registro.
        consh = ttk.Frame(mon, style=tema.TARJETA)
        consh.grid(row=f, column=0, columnspan=2, sticky="ew", padx=6)
        consh.columnconfigure(0, weight=1)
        f += 1
        ttk.Label(consh, text="Consola", style=tema.LBL_TITULO).grid(
            row=0, column=0, sticky="w")
        ttk.Checkbutton(consh, text="Registro detallado",
                        variable=self.v_detallado).grid(row=0, column=1, sticky="e")
        acciones = ttk.Frame(consh, style=tema.TARJETA)
        acciones.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        for texto, cmd in (("Limpiar", self.limpiar_consola),
                           ("Copiar", self.copiar_consola),
                           ("Guardar…", self.guardar_consola)):
            ttk.Button(acciones, text=texto, style=tema.MINI, command=cmd).pack(
                side="left", padx=(0, 4))

        self.texto_log = tk.Text(mon, wrap="word", width=28, height=8,
                                 state="disabled")
        tema.estilo_text(self.texto_log)
        tema.tags_consola(self.texto_log)
        self.texto_log.tag_configure("placeholder", foreground=tema.MUTED)
        self.texto_log.bind("<Button-3>", self._menu_consola)   # menú contextual
        self._log_vacio = False                                 # lo fija el placeholder
        self.texto_log.grid(row=f, column=0, sticky="nsew", padx=(6, 6), pady=6)
        mon.rowconfigure(f, weight=1)          # el registro se estira
        sb = self._sb_consola = ttk.Scrollbar(
            mon, orient="vertical", command=self.texto_log.yview)
        sb.grid(row=f, column=1, sticky="ns", pady=6, padx=(0, 6))
        f += 1

        def _auto_sb(lo, hi, _sb=sb):
            """Muestra la barra solo cuando el contenido no cabe (auto-ocultado)."""
            if float(lo) <= 0.0 and float(hi) >= 1.0:
                _sb.grid_remove()
            else:
                _sb.grid()
            _sb.set(lo, hi)
        self.texto_log.configure(yscrollcommand=_auto_sb)
        _auto_sb(0.0, 1.0)                          # arranca oculta (consola vacía)
        self._mostrar_placeholder_consola()         # empty state inicial

        # 4) Información de la app (fondo: marca+versión, subtítulo y enlaces).
        info = ttk.Frame(mon, style=tema.NEGRO_FRAME, padding=8)
        info.grid(row=f, column=0, columnspan=2, sticky="ew")
        info.columnconfigure(0, weight=1)
        fila_marca = ttk.Frame(info, style=tema.NEGRO_FRAME)
        fila_marca.grid(row=0, column=0)                 # centrado
        ttk.Label(fila_marca, text="kakoli", style=tema.LBL_MARCA).pack(side="left")
        ttk.Label(fila_marca, text=f"v{VERSION}", style=tema.LBL_MARCA_VER).pack(
            side="left", padx=(8, 0))
        ttk.Label(info, text=SUBTITULO, style=tema.LBL_MARCA_VER, wraplength=240,
                  justify="center").grid(row=1, column=0, pady=(2, 0))
        enlaces = ttk.Frame(info, style=tema.NEGRO_FRAME)
        enlaces.grid(row=2, column=0, pady=(4, 0))
        l_autor = tk.Label(enlaces, text=AUTOR)
        tema.estilo_enlace(l_autor, fondo=tema.NEGRO)
        l_autor.pack(side="left", padx=(0, 14))
        l_autor.bind("<Button-1>", lambda _e: self._abrir(URL_AUTOR))
        componentes.Tooltip(l_autor, "Ver el proyecto")
        l_cafe = tk.Label(enlaces, text=ICONO_CAFE)
        tema.estilo_enlace(l_cafe, fondo=tema.NEGRO)
        l_cafe.configure(font=tema.fuente("bold"))       # icono: sin subrayado, mayor
        l_cafe.pack(side="left")
        l_cafe.bind("<Button-1>", lambda _e: self._abrir(URL_CAFE))
        componentes.Tooltip(l_cafe, "Invítame a un café")

        paned.add(mon, weight=0)               # panel derecho: conserva su ancho

    # ---------------- chrome propio de la ventana (sin barra nativa) ----------
    def _construir_controles_ventana(self, mon: tk.Misc, fila: int) -> None:
        """Franja superior del panel derecho con los controles de la ventana
        (minimizar, maximizar/restaurar, cerrar) que sustituyen a la barra de título
        nativa. La franja hace de asa para arrastrar la ventana."""
        strip = ttk.Frame(mon, style=tema.TARJETA)
        strip.grid(row=fila, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 4))
        strip.columnconfigure(0, weight=1)
        asa = ttk.Frame(strip, style=tema.TARJETA, height=20)   # zona de arrastre
        asa.grid(row=0, column=0, sticky="ew")
        botones = ttk.Frame(strip, style=tema.TARJETA)
        botones.grid(row=0, column=1, sticky="e")
        ttk.Button(botones, text="—", width=3, style=tema.MINI,
                   command=self._minimizar).pack(side="left", padx=(0, 2))
        self._b_maximizar = ttk.Button(botones, text="▢", width=3, style=tema.MINI,
                                       command=self._alternar_maximizar)
        self._b_maximizar.pack(side="left", padx=(0, 2))
        ttk.Button(botones, text="✕", width=3, style=tema.MINI,
                   command=self._cerrar).pack(side="left")
        # Arrastrar la ventana desde la franja (y su zona vacía).
        for w in (strip, asa):
            marco_ventana.hacer_arrastrable(w, self, al_empezar=self._antes_de_arrastrar)

    def activar_marco_sin_barra(self) -> None:
        """Quita la barra de título nativa (Windows) y añade el tirador de
        redimensionado. Se llama SOLO en el arranque real (kakoli.py), no en los
        tests. Silencioso: fuera de Windows conserva la barra nativa."""
        if not marco_ventana.es_windows():
            return
        if marco_ventana.sin_barra_titulo(self):
            marco_ventana.agregar_tirador_redim(self, self, tema.BORDE)
            self._pintar_boton_maximizar()
            if self._maximizada:               # re-asegura el área de trabajo
                x, y, w, h = self._area_trabajo()
                self.geometry(f"{w}x{h}+{x}+{y}")
            # Icono GRANDE nítido en la barra de tareas: tras el baile de
            # WS_EX_APPWINDOW (va con after(10)), se fija sobre el HWND ya estable.
            self.after(80, lambda: marco_ventana.fijar_icono(self, tema.ruta_ico()))

    def _minimizar(self) -> None:
        marco_ventana.minimizar(self)

    def _alternar_maximizar(self) -> None:
        """Maximiza (ocupa el área de trabajo) o restaura el tamaño anterior. No usa
        'zoomed' (taparía la barra de tareas con el chrome propio)."""
        if self._maximizada:
            self.geometry(self._geo_normal)
            self._maximizada = False
        else:
            self._geo_normal = self.geometry()
            x, y, w, h = self._area_trabajo()
            self.geometry(f"{w}x{h}+{x}+{y}")
            self._maximizada = True
        self._pintar_boton_maximizar()

    def _pintar_boton_maximizar(self) -> None:
        b = getattr(self, "_b_maximizar", None)
        if b is not None:
            b.configure(text="❐" if self._maximizada else "▢")

    def _antes_de_arrastrar(self) -> None:
        """Al empezar a arrastrar una ventana maximizada, se restaura primero para
        poder moverla."""
        if getattr(self, "_maximizada", False):
            self._alternar_maximizar()

    def _construir_rendimiento(self, mon: tk.Misc, fila: int = 1) -> None:
        """Panel COMPARTIDO 'Rendimiento' (Hilos + Modo ligero), bajo el perfil.
        Las opciones son comunes a todas las tareas y persisten (viven en App)."""
        rend = ttk.LabelFrame(mon, text="Rendimiento", padding=6, style=tema.SECCION)
        rend.grid(row=fila, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        rend.columnconfigure(0, weight=1)

        techo = getattr(self, "techo_hilos", 99)
        maxh = min(max(1, recursos.cpu_logicos()), 8)
        ttk.Label(rend, text="Hilos (a la vez):", style=tema.LBL_TITULO).grid(
            row=0, column=0, sticky="w")
        filaradios = ttk.Frame(rend, style=tema.TARJETA)
        filaradios.grid(row=1, column=0, sticky="ew", pady=(2, 4))
        # Selector segmentado RESPONSIVO: 'Auto' aislado en la primera columna
        # (solo fila 0) y los números repartidos en las cuatro columnas siguientes
        # según los hilos disponibles. Todas las columnas usadas llevan el mismo
        # peso (uniform) y los botones se pegan a "ew", así el ancho de columnas
        # y botones se reparte automáticamente con el ancho del panel. Cada radio
        # es un botón que se ilumina al elegirlo (el indicador circular nativo se
        # veía igual marcado que sin marcar sobre el tema oscuro).
        self._radios_hilos = []
        self._atenuados_hilos = {}                  # rb -> True si el hardware lo desaconseja
        NUMCOLS = 4                                 # columnas para los números (tras 'Auto')
        rb_auto = tk.Radiobutton(filaradios, text="Auto", value="Auto",
                                 variable=self.v_hilos, width=4)
        tema.estilo_radio_seg(rb_auto)
        rb_auto.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        componentes.Tooltip(rb_auto, "Deja que la app elija cuántas tareas hace a "
                            "la vez según tu equipo (recomendado).")
        self._radios_hilos.append(rb_auto)
        self._atenuados_hilos[rb_auto] = False
        self._perf_bloqueables.append((rb_auto, "normal"))
        for j, n in enumerate(range(1, maxh + 1)):
            val = str(n)
            atenuar = n > techo
            rb = tk.Radiobutton(filaradios, text=val, value=val,
                                variable=self.v_hilos, width=2,
                                state=("disabled" if atenuar else "normal"))
            tema.estilo_radio_seg(rb)
            if atenuar:
                componentes.Tooltip(rb, "Tu equipo rinde mejor con hasta "
                                    f"{techo} " + ("hilo" if techo == 1 else "hilos")
                                    + " a la vez; más puede ir más lento.")
            rb.grid(row=j // NUMCOLS, column=1 + j % NUMCOLS,
                    sticky="ew", padx=1, pady=1)
            self._radios_hilos.append(rb)
            self._atenuados_hilos[rb] = atenuar
            self._perf_bloqueables.append((rb, "disabled" if atenuar else "normal"))
        # Reparto elástico: todas las columnas realmente usadas (Auto + los números
        # que quepan en las 4 siguientes) comparten el ancho a partes iguales.
        for col in range(1 + min(maxh, NUMCOLS)):
            filaradios.columnconfigure(col, weight=1, uniform="hilos")
        # Repinta la selección ahora y en cada cambio (incluye clics del usuario).
        self.v_hilos.trace_add("write", lambda *_: self._pintar_hilos())
        self._pintar_hilos()

        cl = ttk.Checkbutton(rend, text="Modo ligero (prioridad baja)",
                             variable=self.v_ligero)
        cl.grid(row=2, column=0, sticky="w", pady=(2, 0))
        self._perf_bloqueables.append((cl, "normal"))

    def _abrir(self, url: str) -> None:
        """Abre una URL en el navegador del sistema (enlaces de la info de la app)."""
        try:
            webbrowser.open(url, new=2)
        except Exception:  # noqa: BLE001
            pass

    def _texto_perfil(self) -> str:
        """Varias líneas con el perfil del ordenador (para el widget 'Equipo')."""
        p = self.perfil_base
        if p is None:
            return "Perfil del equipo no disponible."

        def gb(n: int) -> str:
            return f"{n / (1024 ** 3):.1f} GB"

        disco = ("HDD" if p.disco_lento else
                 "SSD" if p.disco_lento is False else "disco desconocido")
        nucleos = (f"{p.cpu_fisicos} físicos · {p.cpu_logicos} lógicos"
                   if p.cpu_fisicos else f"{p.cpu_logicos} lógicos")
        lineas = [
            f"Núcleos: {nucleos}",
            f"RAM libre: {gb(p.ram_disponible)} de {gb(p.ram_total)}",
            f"Disco: {disco} ({p.tipo_unidad})",
        ]
        if self.techo_hilos:
            lineas.append(f"Paralelo recomendado: hasta {self.techo_hilos} "
                          + ("hilo" if self.techo_hilos == 1 else "hilos"))
        if p.energia == "bateria":
            lineas.append("Alimentación: batería")
        return "\n".join(lineas)

    # Protocolo textual implícito motor -> consola (P12): la GUI colorea cada línea
    # del registro según su prefijo. Se documenta aquí como constantes; los motores
    # solo tienen que empezar la línea por el prefijo adecuado (el contrato no
    # cambia). '[!]' = aviso (rojo); cabecera/perfil/simulación = gris; remates de
    # fin = verde lima; el resto, normal.
    PREFIJO_AVISO = ("[!]",)
    PREFIJOS_SISTEMA = ("===", "Máquina:", "[Simulaci")
    PREFIJOS_EXITO = ("Completado", "Eliminado:", "Nada que hacer")

    @classmethod
    def _tag_log(cls, linea: str) -> str:
        """Color (tag de la consola) de una línea del registro según su prefijo."""
        s = linea.lstrip()
        if s.startswith(cls.PREFIJO_AVISO):
            return "aviso"
        if s.startswith(cls.PREFIJOS_SISTEMA):
            return "sistema"
        if s.startswith(cls.PREFIJOS_EXITO):
            return "exito"
        return "normal"

    def escribir(self, linea: str) -> None:
        self.escribir_lote([linea])

    def escribir_lote(self, lineas: list[str]) -> None:
        """Vuelca líneas al registro COMPARTIDO y recorta si crece demasiado."""
        if not lineas:
            return
        self.texto_log.configure(state="normal")
        if self._log_vacio:                      # retira el empty state al primer mensaje
            self.texto_log.delete("1.0", "end")
            self._log_vacio = False
        bloque: list[str] = []
        etiqueta_actual = ""
        for linea in lineas:
            etiqueta = self._tag_log(linea)
            if etiqueta != etiqueta_actual and bloque:
                self.texto_log.insert("end", "".join(bloque), etiqueta_actual)
                bloque = []
            etiqueta_actual = etiqueta
            bloque.append(linea + "\n")
        if bloque:
            self.texto_log.insert("end", "".join(bloque), etiqueta_actual)

        total = int(self.texto_log.index("end-1c").split(".")[0])
        if total > MAX_LINEAS_REGISTRO:
            self.texto_log.delete("1.0", f"{total - LINEAS_A_CONSERVAR}.0")
        self.texto_log.see("end")
        self.texto_log.configure(state="disabled")

    # ---------------- acciones de la consola (Fase 5) ----------------
    def _mostrar_placeholder_consola(self) -> None:
        """Empty state: texto gris de guía cuando el registro está vacío."""
        self.texto_log.configure(state="normal")
        self.texto_log.delete("1.0", "end")
        self.texto_log.insert("1.0", "Aquí aparecerá el registro de la tarea.",
                              "placeholder")
        self.texto_log.configure(state="disabled")
        self._log_vacio = True

    def _texto_consola(self) -> str:
        """Contenido real del registro (vacío si solo está el empty state)."""
        if self._log_vacio:
            return ""
        return self.texto_log.get("1.0", "end-1c")

    def limpiar_consola(self) -> None:
        """Vacía el registro y restaura el empty state."""
        self._mostrar_placeholder_consola()

    def copiar_consola(self) -> None:
        """Copia al portapapeles la selección (si la hay) o todo el registro."""
        try:
            texto = self.texto_log.get("sel.first", "sel.last")
        except tk.TclError:
            texto = self._texto_consola()
        if texto:
            self.clipboard_clear()
            self.clipboard_append(texto)

    def guardar_consola(self) -> None:
        """Guarda el registro en un archivo de texto elegido por el usuario."""
        texto = self._texto_consola()
        if not texto:
            return
        ruta = filedialog.asksaveasfilename(
            title="Guardar registro", defaultextension=".txt",
            initialfile="kakoli_registro.txt",
            filetypes=[("Texto", "*.txt"), ("Todos los archivos", "*.*")])
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(texto + "\n")
        except OSError as e:
            messagebox.showerror("No se pudo guardar", str(e))

    def _seleccionar_consola(self) -> None:
        if self._log_vacio:
            return
        self.texto_log.tag_add("sel", "1.0", "end-1c")

    def _menu_consola(self, event) -> None:
        """Menú contextual del registro (clic derecho): copiar/seleccionar/limpiar."""
        menu = tk.Menu(self, tearoff=0, bg=tema.NEGRO, fg=tema.TEXT,
                       activebackground=tema.PRIMARY, activeforeground=tema.NEGRO,
                       bd=0)
        menu.add_command(label="Copiar", command=self.copiar_consola)
        menu.add_command(label="Seleccionar todo", command=self._seleccionar_consola)
        menu.add_separator()
        menu.add_command(label="Limpiar", command=self.limpiar_consola)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    @staticmethod
    def _rotulo(nombre: str, activa: bool = False) -> str:
        """Rótulo de pestaña con estética de corchete: '[ Comprimir ]'
        (y un punto '[ Comprimir • ]' en la que está trabajando)."""
        return f"[ {nombre} • ]" if activa else f"[ {nombre} ]"

    def pestana(self, clase: type[PestanaBase]) -> PestanaBase:
        """Instancia de una pestaña por su clase (la crea perezosamente si aún no
        existe). Permite que una tarea entregue su salida a otra sin acoplarse."""
        return self._instancia(clase)

    def opciones_comunes(self) -> "tuple[bool, recursos.PoliticaHilos]":
        """(detallado, política de hilos) COMUNES a todas las tareas (del monitor
        compartido: Registro detallado + Hilos + Modo ligero). Es el contrato que
        usan las pestañas en vez de leer las variables Tk directamente."""
        return (self.v_detallado.get(),
                politica_desde(self.v_hilos.get(), self.v_ligero.get()))

    def sugerir_entrada(self, ruta, artefacto: str, excepto=None):
        """Handoff: ofrece una salida recién producida (`ruta`, de tipo `artefacto`)
        a la pestaña que CONSUME ese artefacto según el registro, rellenando su
        selector de origen. Devuelve la pestaña que la recibió, o None."""
        desc = self.registro.consumidor_de(artefacto)
        if desc is None:
            return None
        # La consumidora puede no haberse abierto aún: se instancia para poder
        # rellenar su origen (el handoff crea la gemela si hace falta).
        pes = self._instancia(desc.clase)
        if pes is excepto:
            return None
        pes.establecer_origen(str(ruta))
        return pes

    def _pintar_hilos(self) -> None:
        """Colorea los radios de 'Hilos': el elegido en verde, el resto apagado.
        Da retroalimentación clara de la selección (el indicador nativo apenas
        se distinguía sobre el tema oscuro)."""
        actual = self.v_hilos.get()
        for rb in getattr(self, "_radios_hilos", ()):
            tema.pintar_radio_seg(rb, rb.cget("value") == actual,
                                  self._atenuados_hilos.get(rb, False))

    # ---------------- bloqueo (una tarea a la vez) ----------------
    def bloquear(self, activa: "PestanaBase") -> None:
        """Mientras una tarea trabaja: no se puede volver al menú ni cambiar de
        tarea (se deshabilitan '←' y las hermanas; la activa lleva '•'), ni tocar
        las opciones de rendimiento compartidas."""
        self._bloqueado = True
        self._tarea_actual = activa
        for w, _est in self._perf_bloqueables:
            w.configure(state="disabled")
        self._pintar_barra()
        self._arrancar_bomba()

    def desbloquear(self) -> None:
        """Reactiva la navegación y las opciones de rendimiento al terminar/pausar
        (las opciones de hilos atenuadas por hardware siguen deshabilitadas)."""
        self._bloqueado = False
        for w, est in self._perf_bloqueables:
            w.configure(state=est)
        self._pintar_barra()

    # ---------------- persistencia de preferencias (Fase 2) ----------------
    def _hilos_validos(self, valor) -> str:
        """Normaliza el valor guardado de 'Hilos' contra ESTE equipo: 'Auto' o un
        entero seleccionable (1..min(cpu,8) y no mayor que el techo del equipo);
        cualquier otra cosa se cae a 'Auto'."""
        if valor == "Auto" or valor is None:
            return "Auto"
        try:
            n = int(valor)
        except (TypeError, ValueError):
            return "Auto"
        maxh = min(max(1, recursos.cpu_logicos()), 8)
        if 1 <= n <= min(maxh, getattr(self, "techo_hilos", maxh) or maxh):
            return str(n)
        return "Auto"

    def _restaurar_geometria(self) -> None:
        """Aplica la geometría guardada (si es válida y visible) o, por defecto,
        maximiza la ventana al área de trabajo. Con chrome propio (Windows, sin barra
        nativa) 'maximizar' es ocupar el área de trabajo a mano (no 'zoomed', que
        taparía la barra de tareas); `_geo_normal` guarda el tamaño al restaurar."""
        x, y, w, h = self._area_trabajo()
        geo = self._prefs.get("geometria")
        base = geo if self._geometria_valida(geo) else f"{w}x{h}+{x}+{y}"
        self._geo_normal = base
        self.geometry(base)
        self.minsize(520, 480)
        self._maximizada = bool(self._prefs.get("maximizada", True))
        if not self._maximizada:
            return
        if marco_ventana.es_windows():
            self.geometry(f"{w}x{h}+{x}+{y}")          # área de trabajo (sin la barra)
        else:
            try:
                self.state("zoomed")
            except tk.TclError:
                pass

    # Anchura mínima del navegador izquierdo (para que la tarea no se ahogue).
    _IZQ_MIN = 300

    def _monitor_min_px(self) -> int:
        """Ancho mínimo del panel derecho para que se vean todos sus botones y
        textos. Se toma del ancho que REALMENTE pide el contenido (varía algo por
        equipo, p. ej. las líneas del perfil), acotado a un rango sensato."""
        try:
            req = self._mon.winfo_reqwidth()
        except (AttributeError, tk.TclError):
            req = 300
        return max(300, min(req, 380))

    def _al_configurar_paned(self, _e=None) -> None:
        """Fija la posición del divisor la primera vez que el paned tiene tamaño real
        (en el arranque el ancho aún es 1). Luego el navegador (weight=1) absorbe el
        redimensionado y el monitor conserva su ancho, así que no hay que reajustar."""
        if not self._sash_restaurado:
            # Ventana lo bastante ancha para navegador + monitor completos.
            self.minsize(self._IZQ_MIN + self._monitor_min_px() + 24, 480)
            self._restaurar_sash()

    def _restaurar_sash(self) -> None:
        ancho = self._paned.winfo_width()
        if ancho <= 1:
            return                             # aún sin tamaño real; se reintenta
        mon_min = self._monitor_min_px()
        mon_ancho = self._prefs.get("monitor_ancho", mon_min)
        try:
            mon_ancho = int(mon_ancho)
        except (TypeError, ValueError):
            mon_ancho = mon_min
        # Límites: el monitor nunca por debajo de su mínimo ni tanto que ahogue la
        # tarea (que conserva al menos _IZQ_MIN).
        mon_ancho = max(mon_min, min(mon_ancho, max(mon_min, ancho - self._IZQ_MIN)))
        try:
            self._paned.sashpos(0, ancho - mon_ancho)
        except tk.TclError:
            return
        self._sash_restaurado = True

    def _clamp_sash(self, _e=None) -> None:
        """Al arrastrar el divisor, impide que el monitor baje de su ancho mínimo
        (se recortarían botones/textos) o que el navegador quede más estrecho que
        `_IZQ_MIN`. Se reajusta la posición tras cada movimiento."""
        ancho = self._paned.winfo_width()
        if ancho <= 1:
            return
        try:
            pos = self._paned.sashpos(0)
        except tk.TclError:
            return
        maxpos = ancho - self._monitor_min_px()    # monitor >= su mínimo
        minpos = self._IZQ_MIN                      # navegador >= su mínimo
        nuevo = maxpos if maxpos < minpos else min(max(pos, minpos), maxpos)
        if nuevo != pos:
            try:
                self._paned.sashpos(0, nuevo)
            except tk.TclError:
                pass

    def _geometria_valida(self, geo) -> bool:
        """True si `geo` ('WxH+X+Y') está en pantalla (evita restaurar una ventana
        fuera de la vista si cambió el monitor)."""
        if not isinstance(geo, str):
            return False
        import re
        m = re.fullmatch(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", geo)
        if not m:
            return False
        _w, _h, gx, gy = (int(v) for v in m.groups())
        if _w < 400 or _h < 300:                       # descarta tamaños degenerados
            return False
        return (-50 <= gx < self.winfo_screenwidth()
                and -50 <= gy < self.winfo_screenheight())

    def _cargar_ultimas(self) -> dict:
        """{categoría.nombre -> clase} de la última tarea usada por categoría, a
        partir de los ids guardados (descartando los que ya no existan)."""
        guardadas = self._prefs.get("ultimas")
        if not isinstance(guardadas, dict):
            return {}
        out = {}
        for cat, tid in guardadas.items():
            clase = self._clase_por_id.get(tid)
            if clase is not None:
                out[cat] = clase
        return out

    def _restaurar_navegacion(self) -> None:
        """Abre la app donde se dejó la última vez: una tarea, la Ayuda o la portada."""
        abierto = self._prefs.get("abierto")
        if abierto == "ayuda":
            self._entrar_ayuda()
            return
        if isinstance(abierto, str):
            clase = self._clase_por_id.get(abierto)
            if clase is not None:
                self.mostrar(clase)
                return
        self._ir_menu()

    def ultima_carpeta_dialogo(self) -> str:
        """Última carpeta usada en un diálogo Examinar (para `initialdir`)."""
        ruta = self._prefs.get("carpeta_dialogo", "")
        return ruta if isinstance(ruta, str) else ""

    def recordar_carpeta_dialogo(self, ruta: str) -> None:
        """Recuerda la carpeta de la última selección (se persiste al cerrar)."""
        if ruta:
            self._prefs["carpeta_dialogo"] = ruta

    def _guardar_prefs(self) -> None:
        """Vuelca el estado actual a `self._prefs` y lo persiste. Silencioso: un
        fallo al guardar nunca debe impedir cerrar la app."""
        try:
            self._prefs["hilos"] = self.v_hilos.get()
            self._prefs["ligero"] = bool(self.v_ligero.get())
            self._prefs["detallado"] = bool(self.v_detallado.get())
            self._prefs["ultimas"] = {
                cat: self._id_por_clase.get(cl)
                for cat, cl in self._ultima_tarea.items()
                if cl in self._id_por_clase}
            if self._en_ayuda:
                self._prefs["abierto"] = "ayuda"
            elif self._tarea_actual is not None:
                self._prefs["abierto"] = self._id_por_clase.get(
                    type(self._tarea_actual))
            else:
                self._prefs["abierto"] = None
            if marco_ventana.es_windows():
                # Chrome propio: 'maximizada' la lleva el flag; se guarda el tamaño
                # NORMAL (no el del área de trabajo) para restaurar bien al abrir.
                maxi = getattr(self, "_maximizada", False)
                geo = self._geo_normal if maxi else self.geometry()
            else:
                try:
                    maxi = self.state() == "zoomed"
                except tk.TclError:
                    maxi = False
                geo = self.geometry()
            if self._geometria_valida(geo):            # no guardar 1x1 (oculta)
                self._prefs["geometria"] = geo
                self._prefs["maximizada"] = maxi
            ancho_paned = self._paned.winfo_width()    # ancho del monitor (divisor)
            if ancho_paned > 1:
                self._prefs["monitor_ancho"] = ancho_paned - self._paned.sashpos(0)
            preferencias.guardar(self._prefs)
        except Exception:  # noqa: BLE001 — persistir es una comodidad, no crítico
            pass

    def _area_trabajo(self) -> tuple[int, int, int, int]:
        """(x, y, ancho, alto) del área utilizable de la pantalla (sin barra de
        tareas). En Windows usa SPI_GETWORKAREA; si no, la pantalla completa."""
        try:
            import ctypes
            from ctypes import wintypes

            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                            ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

            r = RECT()
            SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETWORKAREA, 0, ctypes.byref(r), 0):
                return r.left, r.top, r.right - r.left, r.bottom - r.top
        except Exception:  # noqa: BLE001
            pass
        return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

    def _arrancar_bomba(self) -> None:
        """Arma la bomba si no está ya corriendo (idempotente). La llama
        bloquear() al empezar una tarea."""
        if self._id_bomba is None:
            self._id_bomba = self.after(INTERVALO_BOMBA_MS, self._bomba)

    def _bomba(self) -> None:
        """Un solo temporizador vacía las colas de las pestañas. Se re-arma solo
        mientras haya una tarea en marcha (`_bloqueado`): ese flag no baja hasta
        que _fin drena el evento `fin` y llama a desbloquear(), así que ninguna
        línea ni el remate final se pierden. En reposo, la bomba queda parada."""
        for pes in self.pestanas:
            pes.procesar_cola()
        if self._bloqueado:
            self._id_bomba = self.after(INTERVALO_BOMBA_MS, self._bomba)
        else:
            self._id_bomba = None

    def comprobar_cierre(self) -> None:
        if self.cerrando and not any(p.ocupada() for p in self.pestanas):
            self.destroy()

    def _cerrar(self) -> None:
        ocupadas = [p for p in self.pestanas if p.ocupada()]
        if ocupadas:
            if not messagebox.askyesno(
                    "Salir",
                    "Hay trabajo en marcha. Se terminará la parte en curso y se "
                    "guardará el avance antes de cerrar. ¿Salir?"):
                return
            self.cerrando = True
            for p in ocupadas:
                p.pedir_cierre()
            return
        self.destroy()

    def destroy(self) -> None:
        """Persiste las preferencias y cancela la bomba pendiente antes de destruir
        la ventana. Cubre el cierre directo y el ordenado (comprobar_cierre)."""
        self._guardar_prefs()
        for attr in ("_id_bomba", "_id_prewarm"):
            tid = getattr(self, attr, None)
            if tid is not None:
                try:
                    self.after_cancel(tid)
                except Exception:  # noqa: BLE001
                    pass
                setattr(self, attr, None)
        super().destroy()


