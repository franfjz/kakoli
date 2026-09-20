# -*- coding: utf-8 -*-
"""marco_ventana — chrome propio de la ventana (sin barra de título nativa).

Encapsula la parte específica de Windows para quitar la barra de título del
sistema y reimplementar a mano lo que esta daba: presencia en la barra de tareas,
minimizar, arrastrar la ventana y redimensionarla. Todo va detrás de `es_windows()`
y de try/except: fuera de Windows (o si algo falla) la app conserva su barra
nativa y sigue funcionando.

Las piezas de alto nivel (maximizar/restaurar, botones, integración con el panel)
viven en `gui/app.py`; aquí solo están los primitivos de ventana."""
from __future__ import annotations

import os
import sys
import tkinter as tk

_GWL_EXSTYLE = -20
_WS_EX_APPWINDOW = 0x00040000
_WS_EX_TOOLWINDOW = 0x00000080
_SW_MINIMIZE = 6

# WM_SETICON / LoadImageW (icono nítido de la barra de tareas).
_WM_SETICON = 0x0080
_ICON_SMALL = 0
_ICON_BIG = 1
_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x0010
_SM_CXICON, _SM_CYICON = 11, 12        # tamaño del icono GRANDE (barra de tareas/Alt-Tab)
_SM_CXSMICON, _SM_CYSMICON = 49, 50    # tamaño del icono pequeño (esquina)


def es_windows() -> bool:
    return sys.platform.startswith("win")


def _user32():
    """user32 con los tipos de retorno/argumentos fijados (HWND es un puntero: sin
    esto ctypes lo truncaría a 32 bits en Python de 64 bits)."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.GetParent.restype = wintypes.HWND
    u.GetParent.argtypes = [wintypes.HWND]
    u.GetWindowLongW.restype = ctypes.c_long
    u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.SetWindowLongW.restype = ctypes.c_long
    u.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    return u


def _hwnd(root: tk.Misc):
    """HWND real de la ventana (el padre del id de Tk)."""
    return _user32().GetParent(root.winfo_id())


def sin_barra_titulo(root: tk.Misc) -> bool:
    """Quita la barra de título nativa (solo Windows) y mantiene la ventana en la
    barra de tareas. Devuelve True si se aplicó."""
    if not es_windows():
        return False
    try:
        root.overrideredirect(True)
        root.update_idletasks()
        # La presencia en la barra de tareas se re-asegura tras el override.
        root.after(10, lambda: _activar_barra_tareas(root))
        return True
    except Exception:  # noqa: BLE001 — si falla, se conserva la barra nativa
        return False


def _activar_barra_tareas(root: tk.Misc) -> None:
    """Marca la ventana como 'de aplicación' (WS_EX_APPWINDOW) para que, aun sin
    barra de título, siga apareciendo en la barra de tareas y en Alt-Tab."""
    try:
        u = _user32()
        hwnd = u.GetParent(root.winfo_id())
        estilo = u.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        estilo = (estilo & ~_WS_EX_TOOLWINDOW) | _WS_EX_APPWINDOW
        u.SetWindowLongW(hwnd, _GWL_EXSTYLE, estilo)
        root.withdraw()
        root.after(10, root.deiconify)
    except Exception:  # noqa: BLE001
        pass


def fijar_icono(root: tk.Misc, ico: "str | None") -> bool:
    """Asocia el `.ico` al HWND real como icono PEQUEÑO y GRANDE (WM_SETICON).

    Con la barra de título propia (`overrideredirect` + el baile de WS_EX_APPWINDOW),
    Tk fija bien el icono pequeño pero NO el GRANDE que usa la barra de tareas y
    Alt-Tab, así que Windows escalaba el pequeño y se veía borroso —más aún en
    pantallas HiDPI—. Aquí se cargan los tamaños que pide el sistema (`GetSystemMetrics`,
    ya en píxeles reales al ser el proceso DPI-aware) directamente del `.ico`, que
    incluye 16→256, de modo que el icono sale nítido. Solo Windows; silencioso."""
    if not es_windows() or not ico or not os.path.exists(ico):
        return False
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        u.LoadImageW.restype = wintypes.HANDLE
        u.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT]
        u.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                   wintypes.WPARAM, wintypes.LPARAM]
        hwnd = _hwnd(root)
        pares = ((u.GetSystemMetrics(_SM_CXICON), u.GetSystemMetrics(_SM_CYICON),
                  _ICON_BIG),
                 (u.GetSystemMetrics(_SM_CXSMICON), u.GetSystemMetrics(_SM_CYSMICON),
                  _ICON_SMALL))
        hecho = False
        for cx, cy, cual in pares:
            h_icon = u.LoadImageW(None, ico, _IMAGE_ICON, cx, cy, _LR_LOADFROMFILE)
            if h_icon:
                u.SendMessageW(hwnd, _WM_SETICON, cual, h_icon)
                hecho = True
        return hecho
    except Exception:  # noqa: BLE001
        return False


def minimizar(root: tk.Misc) -> None:
    """Minimiza la ventana. Con `overrideredirect`, `iconify()` no funciona en
    Windows: se usa ShowWindow sobre el HWND real."""
    if not es_windows():
        try:
            root.iconify()
        except tk.TclError:
            pass
        return
    try:
        _user32().ShowWindow(_hwnd(root), _SW_MINIMIZE)
    except Exception:  # noqa: BLE001
        pass


def hacer_arrastrable(widget: tk.Widget, root: tk.Misc, *, al_empezar=None) -> None:
    """Permite mover la ventana arrastrando `widget` (la franja de controles hace
    de asa, ya que no hay barra de título). `al_empezar` se llama al pulsar (p. ej.
    restaurar la ventana si estaba maximizada)."""
    estado: dict = {}

    def _ini(e):
        if al_empezar is not None:
            al_empezar()
        estado["dx"] = e.x_root - root.winfo_x()
        estado["dy"] = e.y_root - root.winfo_y()

    def _mov(e):
        if "dx" not in estado:
            return
        root.geometry(f"+{e.x_root - estado['dx']}+{e.y_root - estado['dy']}")

    widget.bind("<Button-1>", _ini, add="+")
    widget.bind("<B1-Motion>", _mov, add="+")


def agregar_tirador_redim(root: tk.Misc, contenedor: tk.Misc, color: str):
    """Coloca un pequeño tirador en la esquina inferior derecha para redimensionar
    la ventana (sin bordes nativos). Respeta el tamaño mínimo del root."""
    grip = tk.Frame(contenedor, width=14, height=14, bg=color,
                    cursor="bottom_right_corner")
    grip.place(relx=1.0, rely=1.0, anchor="se")

    def _redim(e):
        try:
            mw, mh = root.wm_minsize()
        except tk.TclError:
            mw, mh = 1, 1
        w = max(mw, e.x_root - root.winfo_x())
        h = max(mh, e.y_root - root.winfo_y())
        root.geometry(f"{w}x{h}")
    grip.bind("<B1-Motion>", _redim)
    return grip
