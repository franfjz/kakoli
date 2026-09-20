# -*- coding: utf-8 -*-
"""dnd — soporte OPCIONAL de "arrastrar y soltar" carpetas desde el explorador.

Aísla la dependencia externa `tkinterdnd2` (envoltorio de la extensión nativa
`tkdnd`): si no está instalada, `soporta_dnd()` devuelve False y el resto de la
GUI simplemente no dibuja la zona de soltar (degradación elegante). El parser de
rutas NO depende de la librería (solo del intérprete Tk), así que es testeable
sin `tkinterdnd2` instalado.

Contrato con el resto de `gui/`:
- `soporta_dnd()`            -> ¿está disponible la librería?
- `parsear_rutas(root, data)` -> list[str]  (rutas del evento <<Drop>>)
- `solo_directorios(rutas)  -> list[str]     (filtra a directorios existentes)
- `registrar_zona(widget, on_drop, on_enter=, on_leave=) -> bool`
"""
from __future__ import annotations

import os
import tkinter as tk

try:                                   # dependencia opcional: aislada aquí
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DISPONIBLE = True
except Exception:                      # noqa: BLE001 — sin la lib, se degrada
    DND_FILES = None
    TkinterDnD = None
    _DISPONIBLE = False


def soporta_dnd() -> bool:
    """True si `tkinterdnd2` está disponible (no garantiza aún que tkdnd cargue)."""
    return _DISPONIBLE


def parsear_rutas(root: tk.Misc, data: str) -> "list[str]":
    """Convierte el `event.data` de un <<Drop>> (una lista Tcl, con las rutas que
    llevan espacios entre llaves) en una lista de rutas. Usa `tk.splitlist`, que
    entiende ese formato; no depende de tkinterdnd2, así que es testeable."""
    if not data:
        return []
    try:
        partes = root.tk.splitlist(data)
    except tk.TclError:
        partes = data.split()
    return [p for p in (s.strip() for s in partes) if p]


def solo_directorios(rutas: "list[str]") -> "list[str]":
    """Deja solo las rutas que son directorios existentes (se sueltan carpetas;
    los archivos sueltos se ignoran)."""
    return [r for r in rutas if os.path.isdir(r)]


def _asegurar_root(root: tk.Misc) -> bool:
    """Carga la extensión tkdnd en el intérprete del root (una sola vez). Devuelve
    True si quedó cargada. Silencioso: si falla (binario ausente, plataforma no
    soportada), devuelve False y quien llame no dibuja la zona."""
    if not _DISPONIBLE:
        return False
    top = root.winfo_toplevel()
    if getattr(top, "_tkdnd_cargado", False):
        return True
    try:
        TkinterDnD._require(top)
        top._tkdnd_cargado = True
        return True
    except Exception:                  # noqa: BLE001 — degradación elegante
        top._tkdnd_cargado = False
        return False


def registrar_zona(widget: tk.Widget, on_drop, *, on_enter=None,
                   on_leave=None) -> bool:
    """Registra `widget` como destino de soltado de ficheros y engancha los
    callbacks. `on_drop` recibe el evento (con `.data`). Devuelve True si quedó
    registrado; False si el soporte no está disponible o falla (sin romper la UI)."""
    if not _asegurar_root(widget):
        return False
    try:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", on_drop)
        if on_enter is not None:
            widget.dnd_bind("<<DropEnter>>", on_enter)
        if on_leave is not None:
            widget.dnd_bind("<<DropLeave>>", on_leave)
        return True
    except Exception:                  # noqa: BLE001 — degradación elegante
        return False
