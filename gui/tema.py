#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
tema.py — Tema visual "retro-modern" de kakoli (Fase 1 del roadmap de diseño).

Este módulo concentra TODO lo visual: paleta de colores, fuentes y estilos de
los widgets. NO sabe nada de la organización de la interfaz (frames, pestañas,
qué opción va dónde): eso vive en la GUI (app.py y las pestañas). Así el aspecto se
cambia en un único sitio, independiente del layout.

Cómo se usa desde la GUI:
    from gui import tema
    tema.configurar(root)                 # una vez, sobre la ventana raíz (tk.Tk)
    ttk.Button(..., style=tema.ACCION)    # ttk: se pasa el nombre de estilo
    lbl = tk.Label(...); tema.estilo_label(lbl, "muted")   # tk clásico: helper

Para PROBAR el tema aislado (galería de widgets):
    python -m gui.tema

Basado en los tokens del diseño (Figma Make): fondo #1E2522, verde #4AF626,
rojo #EF4444, fuente Space Mono. Sobre ttk se usa la base 'clam' (la única que
respeta los colores en Windows).
"""

from __future__ import annotations

import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# ==========================================================================
# Paleta (tokens del diseño). Cambiar aquí recolorea toda la app.
# ==========================================================================
BG = "#1E2522"          # fondo de la ventana
CONTAINER = "#141917"   # paneles / tarjetas
NEGRO = "#000000"       # inputs, consola y cabecera del monitor
PRIMARY = "#4AF626"     # verde principal: acentos, bordes activos, acción
SUCCESS = "#A3E635"     # verde lima: estado "Listo.", éxito en el log
DANGER = "#EF4444"      # rojo: Eliminar, aviso definitivo
BORDE = "#313D39"       # bordes y separadores tenues
TEXT = "#E5E7EB"        # texto normal
MUTED = "#9CA3AF"       # descripciones / etiquetas secundarias
BLANCO = "#FFFFFF"      # texto sobre el rojo de Eliminar / hover
AMBAR = "#F59E0B"       # ámbar: estado en pausa / cancelado
PELIGRO_FONDO = "#2A1717"  # relleno tenue rojizo (caja de aviso de Eliminar)

# Familias de fuente candidatas, de preferida a último recurso.
_FAMILIAS = ("Space Mono", "Consolas", "DejaVu Sans Mono", "Courier New")

# Rellenados por configurar(): fuentes con nombre reutilizables.
FUENTES: dict[str, tkfont.Font] = {}

# Carpeta donde se buscan .ttf/.otf a registrar en runtime (p.ej. Space Mono).
# Deja ahí SpaceMono-Regular/Bold/Italic/BoldItalic.ttf y el tema los usará.
# `fuentes/` (e `iconos/`) viven en la RAÍZ del proyecto; este módulo está en `gui/`,
# así que se sube un nivel. Al compilar con Nuitka, esas carpetas se incluyen como
# DATOS (`--include-data-dir=fuentes=fuentes`, etc.) junto al árbol de módulos
# extraído; Nuitka NO define `sys.frozen`, así que `__file__` apunta ahí y se
# resuelve igual que ejecutando desde el código fuente.
def _raiz_datos() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # gui/ -> raíz


_DIR_FUENTES = os.path.join(_raiz_datos(), "fuentes")
_DIR_ICONOS = os.path.join(_raiz_datos(), "iconos")
_fuentes_registradas = False


def ruta_ico() -> "str | None":
    """Ruta al `.ico` de la app si existe (para fijar el icono nítido de la barra de
    tareas en Windows), o None."""
    ico = os.path.join(_DIR_ICONOS, "kakoli.ico")
    return ico if os.path.exists(ico) else None


def aplicar_icono(ventana) -> None:
    """Pone el icono de la app en la barra de título / barra de tareas de la
    ventana. Silencioso y robusto: si no encuentra el archivo o el sistema no lo
    admite, no hace nada (Tk deja su icono por defecto). En Windows usa el .ico
    (con `default=` se hereda a los diálogos); como respaldo multiplataforma,
    un PNG vía `iconphoto`."""
    try:
        ico = os.path.join(_DIR_ICONOS, "kakoli.ico")
        if os.path.exists(ico):
            ventana.iconbitmap(default=ico)
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        import tkinter as tk
        png = os.path.join(_DIR_ICONOS, "icono_piramide_jungla_256.png")
        if os.path.exists(png):
            img = tk.PhotoImage(file=png)
            ventana._icono_app = img          # referencia viva (evita el GC)
            ventana.iconphoto(True, img)
    except Exception:  # noqa: BLE001
        pass
_FR_PRIVATE = 0x10   # AddFontResourceExW: fuente privada del proceso (sin admin)


def registrar_fuentes(dir_fuentes: str | None = None) -> int:
    """Registra en runtime las fuentes .ttf/.otf de la carpeta `fuentes` SOLO para
    este proceso (FR_PRIVATE: no se instala en el sistema ni pide permisos de
    administrador), de modo que Tk pueda usarlas aunque no estén instaladas.

    Es silenciosa y robusta: si no hay carpeta, no hay archivos, no es Windows o
    algo falla, no hace nada y se sigue con el fallback (Consolas/Courier New).
    Devuelve cuántos archivos se registraron. Idempotente entre llamadas."""
    global _fuentes_registradas
    if _fuentes_registradas:
        return 0
    _fuentes_registradas = True
    carpeta = dir_fuentes or _DIR_FUENTES
    registradas = 0
    try:
        import ctypes
        gdi32 = ctypes.windll.gdi32   # solo Windows; en otros SO lanza y se ignora
        gdi32.AddFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint,
                                             ctypes.c_void_p]
        for nombre in sorted(os.listdir(carpeta)):
            if nombre.lower().endswith((".ttf", ".otf")):
                ruta = os.path.join(carpeta, nombre)
                if gdi32.AddFontResourceExW(ruta, _FR_PRIVATE, None):
                    registradas += 1
    except Exception:  # noqa: BLE001  (FileNotFoundError, AttributeError, OSError…)
        pass
    return registradas

# ==========================================================================
# Nombres de estilo ttk (para no usar strings mágicos en la GUI)
# ==========================================================================
# Frames
TARJETA = "Tarjeta.TFrame"          # fondo CONTAINER (paneles)
NEGRO_FRAME = "Negro.TFrame"        # fondo NEGRO
# Labels (fondo + color según contexto)
LBL = "TLabel"                      # texto normal sobre CONTAINER
LBL_FONDO = "Fondo.TLabel"          # texto normal sobre BG
LBL_MUTED = "Muted.TLabel"          # gris (descripciones)
LBL_TITULO = "Titulo.TLabel"        # verde negrita (encabezados, "Nivel:", etc.)
LBL_MARCA = "Marca.TLabel"          # verde negrita sobre NEGRO (marca)
LBL_MARCA_VER = "MarcaVer.TLabel"   # gris sobre NEGRO (versión)
LBL_EXITO = "Exito.TLabel"          # verde lima ("Listo." / "Completado")
LBL_TRABAJANDO = "Trabajando.TLabel"  # verde principal ("Trabajando..." / progreso)
LBL_PAUSA = "Pausa.TLabel"          # ámbar ("Pausado" / "Cancelado")
LBL_PELIGRO = "Peligro.TLabel"      # rojo (aviso / "Error")
# Botones
BTN = "TButton"                     # genérico (Examinar, secundarios)
ACCION = "Accion.TButton"           # verde relleno (Comprimir/Descomprimir)
PELIGRO_BTN = "Peligro.TButton"     # rojo relleno (Eliminar)
FANTASMA = "Fantasma.TButton"       # apagado (Pausar)
MINI = "Mini.TButton"               # compacto y apagado (acciones de la consola)
# Otros
ENTRADA = "TEntry"
COMBO = "TCombobox"
CHECK = "TCheckbutton"
SECCION = "TLabelframe"             # LabelFrame (legend verde)
NOTA = "TNotebook"
BARRA = "Horizontal.TProgressbar"
# Pestañas de la barra de navegación (menú de 2 niveles): botones con estética de
# pestaña. PESTANA = inactiva/categoría/volver; PESTANA_ACT = tarea seleccionada.
PESTANA = "Pestana.TButton"           # tarea inactiva (nivel 2)
PESTANA_ACT = "PestanaAct.TButton"    # tarea seleccionada (nivel 2)
PESTANA_CAT = "PestanaCat.TButton"    # categoría (nivel 1)
PESTANA_VOLVER = "PestanaVol.TButton" # botón '←' de volver al menú


# ==========================================================================
# Fuentes
# ==========================================================================
def _familia(root: tk.Misc) -> str:
    try:
        disponibles = set(tkfont.families(root))
    except tk.TclError:
        disponibles = set()
    for fam in _FAMILIAS:
        if fam in disponibles:
            return fam
    return "Courier New"   # presente en Windows como último recurso


def _crear_fuentes(root: tk.Misc) -> None:
    registrar_fuentes()          # activa Space Mono si su .ttf está en fuentes/
    fam = _familia(root)
    FUENTES["familia"] = fam                                   # str, informativo
    FUENTES["base"] = tkfont.Font(root=root, family=fam, size=10)
    FUENTES["bold"] = tkfont.Font(root=root, family=fam, size=10, weight="bold")
    FUENTES["peque"] = tkfont.Font(root=root, family=fam, size=9)   # ayuda/consola
    FUENTES["peque_bold"] = tkfont.Font(root=root, family=fam, size=9,
                                        weight="bold")
    FUENTES["italic"] = tkfont.Font(root=root, family=fam, size=10,
                                    slant="italic")
    FUENTES["enlace"] = tkfont.Font(root=root, family=fam, size=9,
                                    underline=True)


def fuente(tipo: str = "base") -> tkfont.Font:
    """Devuelve una fuente con nombre ('base' | 'bold' | 'peque' | 'peque_bold')."""
    return FUENTES[tipo]


# ==========================================================================
# Configuración de estilos
# ==========================================================================
def activar_dpi() -> None:
    """Declara el proceso CONSCIENTE del DPI en Windows, para que Tk dibuje nítido en
    pantallas HiDPI (escaladas al 125/150/…%) en vez de dejar que el sistema haga un
    escalado borroso de la ventana. Debe llamarse ANTES de crear el root Tk. Silencioso
    y robusto: si no es Windows, ya se llamó o falla, no hace nada."""
    try:
        import ctypes
        try:                                   # per-monitor DPI aware (Win 8.1+)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:                      # noqa: BLE001 — respaldo (Win Vista+)
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001 — no-Windows o ya configurado
        pass


def _ajustar_escala(root: tk.Misc) -> None:
    """Ajusta la escala de Tk al DPI REAL de la pantalla, para que las fuentes (medidas
    en puntos) tengan el tamaño físico correcto en HiDPI. En pantallas estándar (96 DPI)
    coincide con el valor por defecto (1.333): no cambia nada. Robusto y silencioso."""
    try:
        dpi = float(root.winfo_fpixels("1i"))  # píxeles por pulgada reales
        if dpi > 0:
            root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:  # noqa: BLE001
        pass


def configurar(root: tk.Misc) -> ttk.Style:
    """Aplica el tema retro a la ventana `root`. Idempotente. Devuelve el Style."""
    _ajustar_escala(root)                      # escala HiDPI antes de crear las fuentes
    if not FUENTES:
        _crear_fuentes(root)
    base, bold, peque = FUENTES["base"], FUENTES["bold"], FUENTES["peque"]

    try:
        root.configure(bg=BG)
    except tk.TclError:
        pass

    st = ttk.Style(root)
    st.theme_use("clam")   # única base ttk que respeta los colores en Windows

    # ---- Frames ----
    st.configure("TFrame", background=BG)
    st.configure(TARJETA, background=CONTAINER)
    st.configure(NEGRO_FRAME, background=NEGRO)

    # ---- Labels (semánticos: combinan fondo + color) ----
    st.configure(LBL, background=CONTAINER, foreground=TEXT, font=base)
    st.configure(LBL_FONDO, background=BG, foreground=TEXT, font=base)
    st.configure(LBL_MUTED, background=CONTAINER, foreground=MUTED, font=peque)
    st.configure(LBL_TITULO, background=CONTAINER, foreground=PRIMARY, font=bold)
    st.configure(LBL_MARCA, background=NEGRO, foreground=PRIMARY, font=bold)
    st.configure(LBL_MARCA_VER, background=NEGRO, foreground=MUTED, font=peque)
    st.configure(LBL_EXITO, background=CONTAINER, foreground=SUCCESS, font=bold)
    st.configure(LBL_TRABAJANDO, background=CONTAINER, foreground=PRIMARY, font=bold)
    st.configure(LBL_PAUSA, background=CONTAINER, foreground=AMBAR, font=bold)
    st.configure(LBL_PELIGRO, background=CONTAINER, foreground=DANGER, font=bold)

    # ---- Botones ----
    st.configure(BTN, background=BORDE, foreground=TEXT, font=bold,
                 bordercolor=BORDE, focuscolor=PRIMARY, relief="flat",
                 padding=(10, 3))
    st.map(BTN,
           background=[("active", PRIMARY), ("pressed", PRIMARY)],
           foreground=[("active", NEGRO), ("pressed", NEGRO)])

    st.configure(ACCION, background=PRIMARY, foreground=NEGRO, font=bold,
                 bordercolor=PRIMARY, focuscolor=NEGRO, relief="flat",
                 padding=(16, 3))
    st.map(ACCION,
           background=[("active", NEGRO), ("pressed", NEGRO)],
           foreground=[("active", PRIMARY), ("pressed", PRIMARY)])

    st.configure(PELIGRO_BTN, background=DANGER, foreground=BLANCO, font=bold,
                 bordercolor=DANGER, focuscolor=NEGRO, relief="flat",
                 padding=(16, 3))
    st.map(PELIGRO_BTN,
           background=[("active", NEGRO), ("pressed", NEGRO)],
           foreground=[("active", DANGER), ("pressed", DANGER)])

    st.configure(FANTASMA, background=CONTAINER, foreground=MUTED, font=base,
                 bordercolor=BORDE, focuscolor=PRIMARY, relief="flat",
                 padding=(12, 3))
    st.map(FANTASMA,
           background=[("active", BORDE), ("pressed", BORDE)],
           foreground=[("active", BLANCO), ("pressed", BLANCO)])

    # Compacto (acciones de la consola): fuente pequeña y poco relleno, para caber
    # en el monitor estrecho. Apagado en reposo, verde al pasar el ratón.
    st.configure(MINI, background=CONTAINER, foreground=MUTED, font=peque,
                 bordercolor=BORDE, focuscolor=PRIMARY, relief="flat",
                 padding=(6, 2))
    st.map(MINI,
           background=[("active", BORDE), ("pressed", BORDE)],
           foreground=[("active", PRIMARY), ("pressed", PRIMARY),
                       ("disabled", BORDE)])

    # Botón deshabilitado (común): apagado y sin hover.
    for estilo in (BTN, ACCION, PELIGRO_BTN, FANTASMA):
        st.map(estilo, background=[("disabled", CONTAINER)],
               foreground=[("disabled", MUTED)])

    # ---- Entry ----
    st.configure(ENTRADA, fieldbackground=NEGRO, foreground=TEXT,
                 insertcolor=TEXT, bordercolor=BORDE, lightcolor=BORDE,
                 darkcolor=BORDE, borderwidth=1, padding=3)
    st.map(ENTRADA,
           bordercolor=[("focus", PRIMARY)],
           lightcolor=[("focus", PRIMARY)],
           darkcolor=[("focus", PRIMARY)])

    # ---- Combobox (el desplegable es un Listbox aparte: ver option_add) ----
    st.configure(COMBO, fieldbackground=NEGRO, background=BORDE, foreground=TEXT,
                 arrowcolor=PRIMARY, bordercolor=BORDE, lightcolor=BORDE,
                 darkcolor=BORDE, padding=3)
    st.map(COMBO,
           fieldbackground=[("readonly", NEGRO), ("focus", NEGRO)],
           foreground=[("readonly", TEXT)],
           selectbackground=[("readonly", NEGRO)],
           selectforeground=[("readonly", TEXT)],
           bordercolor=[("focus", PRIMARY)],
           arrowcolor=[("active", NEGRO)])

    # ---- Checkbutton (ttk; los que se quieran 100% custom usan tk clásico) ----
    st.configure(CHECK, background=CONTAINER, foreground=TEXT, font=base,
                 focuscolor=CONTAINER, indicatorcolor=NEGRO,
                 indicatorbackground=NEGRO, indicatorforeground=PRIMARY)
    st.map(CHECK,
           foreground=[("active", BLANCO), ("disabled", MUTED)],
           background=[("active", CONTAINER)],
           indicatorbackground=[("selected", PRIMARY), ("!selected", NEGRO)],
           indicatorcolor=[("selected", PRIMARY), ("!selected", NEGRO)])

    # ---- LabelFrame (sección con leyenda verde) ----
    st.configure(SECCION, background=CONTAINER, bordercolor=BORDE,
                 lightcolor=BORDE, darkcolor=BORDE, borderwidth=1)
    st.configure("TLabelframe.Label", background=CONTAINER, foreground=PRIMARY,
                 font=bold)

    # ---- Notebook (pestañas) ----
    st.configure(NOTA, background=BG, bordercolor=BORDE, tabmargins=(2, 2, 2, 0))
    st.configure("TNotebook.Tab", background=CONTAINER, foreground=MUTED,
                 bordercolor=BORDE, padding=(7, 4), font=base)
    st.map("TNotebook.Tab",
           background=[("selected", BORDE), ("active", BORDE)],
           foreground=[("selected", PRIMARY), ("active", BLANCO)])

    # ---- Pestañas-botón de la barra de navegación (menú de 2 niveles) ----
    # Look de tab retro: inactiva CONTAINER/gris (hover→blanco), activa BORDE/verde.
    # Categoría (nivel 1) más marcada (texto claro, negrita, hover verde). '←' como
    # botón de navegación (gris, hover verde). Deshabilitada muy atenuada.
    st.configure(PESTANA, background=CONTAINER, foreground=MUTED, font=base,
                 bordercolor=BORDE, focuscolor=PRIMARY, relief="flat",
                 padding=(12, 5))
    st.map(PESTANA,
           background=[("active", BORDE), ("pressed", BORDE)],
           foreground=[("active", BLANCO), ("disabled", BORDE)])

    st.configure(PESTANA_ACT, background=BORDE, foreground=PRIMARY, font=bold,
                 bordercolor=PRIMARY, focuscolor=PRIMARY, relief="flat",
                 padding=(12, 5))
    st.map(PESTANA_ACT,
           background=[("active", BORDE), ("pressed", BORDE)],
           foreground=[("active", PRIMARY), ("disabled", MUTED)])

    st.configure(PESTANA_CAT, background=CONTAINER, foreground=TEXT, font=bold,
                 bordercolor=BORDE, focuscolor=PRIMARY, relief="flat",
                 padding=(14, 6))
    st.map(PESTANA_CAT,
           background=[("active", BORDE), ("pressed", BORDE)],
           foreground=[("active", PRIMARY), ("disabled", BORDE)])

    st.configure(PESTANA_VOLVER, background=CONTAINER, foreground=MUTED, font=bold,
                 bordercolor=BORDE, focuscolor=PRIMARY, relief="flat",
                 padding=(12, 5))
    st.map(PESTANA_VOLVER,
           background=[("active", BORDE), ("pressed", BORDE)],
           foreground=[("active", PRIMARY), ("disabled", BORDE)])

    # ---- Progressbar ----
    st.configure(BARRA, troughcolor=NEGRO, background=PRIMARY, bordercolor=BORDE,
                 lightcolor=PRIMARY, darkcolor=PRIMARY)

    # ---- Scrollbar ----
    st.configure("Vertical.TScrollbar", background=BORDE, troughcolor=CONTAINER,
                 bordercolor=BORDE, arrowcolor=MUTED)
    st.configure("Horizontal.TScrollbar", background=BORDE, troughcolor=CONTAINER,
                 bordercolor=BORDE, arrowcolor=MUTED)
    st.map("Vertical.TScrollbar", background=[("active", PRIMARY)])
    st.map("Horizontal.TScrollbar", background=[("active", PRIMARY)])

    # ---- Separator ----
    st.configure("TSeparator", background=BORDE)

    # ---- PanedWindow (divisor navegador/monitor) ----
    st.configure("TPanedwindow", background=BG)
    st.configure("Sash", sashthickness=7, gripcount=0, background=BORDE)
    st.map("Sash", background=[("active", PRIMARY)])

    # ---- Desplegable del Combobox (Listbox clásico interno) ----
    for opt, val in (("*TCombobox*Listbox.background", NEGRO),
                     ("*TCombobox*Listbox.foreground", TEXT),
                     ("*TCombobox*Listbox.selectBackground", PRIMARY),
                     ("*TCombobox*Listbox.selectForeground", NEGRO)):
        root.option_add(opt, val)

    return st


# ==========================================================================
# Helpers para widgets tk CLÁSICos (Text, Entry, Radiobutton, Checkbutton,
# Label) que no se estilan por ttk.Style.
# ==========================================================================
def estilo_text(w: tk.Text) -> None:
    """Consola/registro: fondo negro, texto claro, cursor y selección del tema."""
    w.configure(bg=NEGRO, fg=TEXT, insertbackground=TEXT,
                selectbackground=PRIMARY, selectforeground=NEGRO,
                highlightthickness=1, highlightbackground=BORDE,
                highlightcolor=BORDE, borderwidth=0, font=FUENTES["peque"])


def tags_consola(w: tk.Text) -> None:
    """Etiquetas de color para las líneas del registro."""
    w.tag_configure("sistema", foreground=MUTED)
    w.tag_configure("exito", foreground=SUCCESS)
    w.tag_configure("aviso", foreground=DANGER)
    w.tag_configure("normal", foreground=TEXT)


def estilo_enlace(w: tk.Label, fondo: str = NEGRO) -> None:
    """Etiqueta clásica con aspecto de enlace: verde, subrayado, cursor de mano y
    realce (verde lima) al pasar el ratón. La acción de abrir la URL la conecta la
    GUI con un bind a <Button-1>."""
    w.configure(bg=fondo, fg=PRIMARY, font=FUENTES["enlace"], cursor="hand2")
    w.bind("<Enter>", lambda _e: w.configure(fg=SUCCESS))
    w.bind("<Leave>", lambda _e: w.configure(fg=PRIMARY))


def estilo_tarjeta_menu(w: tk.Frame, resaltada: bool = False) -> None:
    """Tarjeta clicable de la portada (una por categoría): fondo de panel y borde
    que pasa a verde al pasar el ratón (`resaltada`)."""
    w.configure(bg=CONTAINER, highlightthickness=1, bd=0,
                highlightbackground=(PRIMARY if resaltada else BORDE),
                highlightcolor=(PRIMARY if resaltada else BORDE))


def estilo_caja_aviso(w: tk.Frame) -> None:
    """Caja de aviso (Eliminar): borde y relleno rojizos alrededor del texto."""
    w.configure(bg=PELIGRO_FONDO, highlightbackground=DANGER,
                highlightcolor=DANGER, highlightthickness=1, bd=0)


def estilo_zona_soltar(w: tk.Label, activa: bool = False) -> None:
    """Zona de 'arrastrar y soltar' bajo la lista de rutas: recuadro tenue con
    texto apagado; al pasar una carpeta por encima (`activa`) se ilumina en verde
    para dejar claro que se puede soltar ahí."""
    w.configure(bg=CONTAINER, fg=(PRIMARY if activa else MUTED),
                font=FUENTES["peque"], anchor="center", padx=6, pady=8,
                highlightthickness=1, bd=0,
                highlightbackground=(PRIMARY if activa else BORDE),
                highlightcolor=(PRIMARY if activa else BORDE))


def estilo_tooltip(w: tk.Label) -> None:
    """Etiqueta interior de un tooltip: fondo negro, texto claro y borde tenue."""
    w.configure(bg=NEGRO, fg=TEXT, font=FUENTES["peque"], justify="left",
                padx=6, pady=3, borderwidth=0, highlightthickness=1,
                highlightbackground=BORDE, highlightcolor=BORDE)


def estilo_radio(w: tk.Radiobutton) -> None:
    w.configure(bg=CONTAINER, fg=TEXT, activebackground=CONTAINER,
                activeforeground=BLANCO, selectcolor=PRIMARY,
                disabledforeground=MUTED, highlightthickness=0,
                font=FUENTES["base"])


def estilo_radio_seg(w: tk.Radiobutton) -> None:
    """Radio en modo 'botón' (indicatoron=0) para el selector de Hilos: el
    indicador circular nativo se ve casi igual seleccionado o no sobre fondo
    oscuro (parecían todos marcados). Aquí el propio botón se ilumina, y App
    repinta el color de fondo/texto según la selección (`_pintar_hilos`)."""
    w.configure(indicatoron=0, bd=1, relief="solid", highlightthickness=0,
                padx=8, pady=2, cursor="hand2",
                bg=CONTAINER, fg=TEXT, selectcolor=CONTAINER,
                activebackground=BORDE, activeforeground=BLANCO,
                disabledforeground=MUTED, font=FUENTES["base"])


def pintar_radio_seg(w: tk.Radiobutton, seleccionado: bool,
                     atenuado: bool = False) -> None:
    """Colorea un radio segmentado según su estado. Seleccionado = fondo verde
    con texto oscuro (inequívoco); no seleccionado = fondo del panel; atenuado
    (hardware) = texto apagado. Se llama en cada cambio de la selección."""
    if seleccionado:
        w.configure(bg=PRIMARY, fg=CONTAINER, selectcolor=PRIMARY,
                    activebackground=PRIMARY, activeforeground=CONTAINER,
                    highlightbackground=PRIMARY)
    else:
        w.configure(bg=CONTAINER, fg=(MUTED if atenuado else TEXT),
                    selectcolor=CONTAINER, activebackground=BORDE,
                    activeforeground=BLANCO, highlightbackground=BORDE)


def estilo_check(w: tk.Checkbutton) -> None:
    w.configure(bg=CONTAINER, fg=TEXT, activebackground=CONTAINER,
                activeforeground=BLANCO, selectcolor=PRIMARY,
                disabledforeground=MUTED, highlightthickness=0,
                font=FUENTES["base"])


_LABEL_TONO = {
    "normal": (TEXT, "base"),
    "muted": (MUTED, "peque"),
    "head": (PRIMARY, "bold"),
    "exito": (SUCCESS, "bold"),
    "danger": (DANGER, "bold"),
}


def estilo_label(w: tk.Label, tono: str = "normal", fondo: str = CONTAINER) -> None:
    fg, f = _LABEL_TONO.get(tono, _LABEL_TONO["normal"])
    w.configure(bg=fondo, fg=fg, font=FUENTES[f], justify="left", anchor="w")


# ==========================================================================
# Galería de previsualización (acceptance test visual de la Fase 1)
# ==========================================================================
def _galeria() -> None:
    root = tk.Tk()
    root.title("tema.py — galería")
    root.geometry("560x620")
    configurar(root)

    cont = ttk.Frame(root, style=TARJETA, padding=12)
    cont.pack(fill="both", expand=True, padx=10, pady=10)

    ttk.Label(cont, text="CARPETAS EN ZIP", style=LBL_TITULO).pack(anchor="w")
    ttk.Label(cont, text="Galería del tema retro-modern",
              style=LBL_MUTED).pack(anchor="w", pady=(0, 10))

    # Botones
    fbtn = ttk.Frame(cont, style=TARJETA)
    fbtn.pack(fill="x", pady=4)
    ttk.Button(fbtn, text="COMPRIMIR", style=ACCION).pack(side="left", padx=(0, 6))
    ttk.Button(fbtn, text="ELIMINAR", style=PELIGRO_BTN).pack(side="left", padx=6)
    ttk.Button(fbtn, text="Pausar", style=FANTASMA).pack(side="left", padx=6)
    ttk.Button(fbtn, text="Examinar...", style=BTN).pack(side="left", padx=6)

    # Entry + Combobox
    ttk.Label(cont, text="Ruta:", style=LBL_TITULO).pack(anchor="w", pady=(10, 0))
    ttk.Entry(cont).pack(fill="x", pady=2)
    fcombo = ttk.Frame(cont, style=TARJETA)
    fcombo.pack(fill="x", pady=4)
    ttk.Label(fcombo, text="Nivel:", style=LBL_TITULO).pack(side="left", padx=(0, 6))
    cb = ttk.Combobox(fcombo, state="readonly", width=18,
                      values=["Rápido (1)", "Equilibrado (5)", "Máximo (9)"])
    cb.current(0)
    cb.pack(side="left")

    # Sección con checks ttk
    sec = ttk.Labelframe(cont, text="Opciones", style=SECCION, padding=8)
    sec.pack(fill="x", pady=8)
    ttk.Checkbutton(sec, text="Verificar ZIP al reanudar").pack(anchor="w")
    ttk.Checkbutton(sec, text="Borrar ZIP intermedios").pack(anchor="w")

    # Radios clásicos (hilos)
    frad = ttk.Frame(cont, style=TARJETA)
    frad.pack(fill="x", pady=4)
    ttk.Label(frad, text="Hilos:", style=LBL_TITULO).pack(side="left", padx=(0, 8))
    v = tk.StringVar(value="Auto")
    for val in ("Auto", "1", "2", "4"):
        rb = tk.Radiobutton(frad, text=val, value=val, variable=v)
        estilo_radio(rb)
        rb.pack(side="left", padx=(0, 8))

    # Progressbar
    pb = ttk.Progressbar(cont, style=BARRA, maximum=100, value=45)
    pb.pack(fill="x", pady=8)

    # Consola (Text clásico) con tags
    ttk.Label(cont, text="Consola:", style=LBL_TITULO).pack(anchor="w")
    txt = tk.Text(cont, height=6, wrap="word")
    estilo_text(txt)
    tags_consola(txt)
    txt.pack(fill="both", expand=True, pady=2)
    txt.insert("end", "[SISTEMA] Iniciando aplicación...\n", "sistema")
    txt.insert("end", "[SISTEMA] Interfaz gráfica lista.\n", "sistema")
    txt.insert("end", "> Esperando órdenes.\n", "exito")
    txt.insert("end", "[!] Ejemplo de aviso.\n", "aviso")
    txt.configure(state="disabled")

    ttk.Label(cont, text=f"Fuente: {FUENTES.get('familia', '?')}   ·   Listo.",
              style=LBL_EXITO).pack(anchor="w", pady=(6, 0))

    root.mainloop()


if __name__ == "__main__":
    _galeria()
