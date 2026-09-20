# -*- coding: utf-8 -*-
"""componentes — piezas de interfaz reutilizables por la GUI global y por las
pestañas de tarea. No conocen ninguna tarea concreta.

- MarcoDesplazable: área con scroll vertical (Canvas + barra + rueda del ratón).
  Estaba TRIPLICADA (opciones de la pestaña, portada y Ayuda); aquí es una sola
  pieza. Se rellena su `.interior`.
- fila_texto: fila «etiqueta + Entry» (los campos de texto de varias pestañas).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from gui import tema


def pasos_rueda(event) -> int:
    """Unidades para `yview_scroll` a partir de un evento de rueda, NORMALIZADO entre
    plataformas (negativo = hacia arriba, positivo = hacia abajo):
      - Windows: `event.delta` en múltiplos de 120.
      - macOS: `event.delta` en pasos pequeños (no se divide por 120, o daría 0).
      - Linux/X11: la rueda llega como `<Button-4>` (arriba) / `<Button-5>` (abajo),
        sin `delta`; se detecta por `event.num`.
    Devuelve 0 si el evento no aporta desplazamiento."""
    num = getattr(event, "num", None)
    if num == 4:                       # X11: rueda arriba
        return -1
    if num == 5:                       # X11: rueda abajo
        return 1
    delta = getattr(event, "delta", 0)
    if not delta:
        return 0
    if abs(delta) >= 120:              # Windows: múltiplos de 120
        return int(-delta / 120)
    return -1 if delta > 0 else 1      # macOS: pasos pequeños


# Secuencias de rueda a enlazar para cubrir las tres plataformas (Windows/macOS usan
# <MouseWheel>; X11/Linux, <Button-4>/<Button-5>).
SECUENCIAS_RUEDA = ("<MouseWheel>", "<Button-4>", "<Button-5>")


def abrir_en_explorador(ruta: str) -> bool:
    """Abre en el explorador de archivos del sistema la carpeta de `ruta` (la propia
    si es un directorio; la contenedora si es un archivo). Silencioso y robusto: no
    lanza nunca; devuelve True si pudo lanzar el comando, False si no."""
    if not ruta:
        return False
    try:
        p = os.path.abspath(ruta)
        carpeta = p if os.path.isdir(p) else os.path.dirname(p)
        if not carpeta:
            return False
        if sys.platform.startswith("win"):
            os.startfile(carpeta)                      # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", carpeta], check=False)
        else:
            subprocess.run(["xdg-open", carpeta], check=False)
        return True
    except Exception:  # noqa: BLE001 — abrir el explorador es una comodidad
        return False


class MarcoDesplazable(ttk.Frame):
    """Contenedor con scroll vertical: un Canvas con un frame interior y una barra
    que (por defecto) solo aparece cuando el contenido no cabe. Se puebla el frame
    `self.interior`. `on_reconfigure` se llama tras recalcular la región (para
    ajustes que dependen del ancho, p. ej. el wraplength de las ayudas)."""

    def __init__(self, master: tk.Misc, *, padding: int = 0, margen: int = 0,
                 auto_ocultar: bool = True, on_reconfigure=None) -> None:
        super().__init__(master, style=tema.TARJETA)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._margen = margen
        self._auto_ocultar = auto_ocultar
        self._on_reconfigure = on_reconfigure
        self._id_reconfig: "str | None" = None    # debounce del on_reconfigure
        self._wheel_binds: "list[tuple[str, str]]" = []   # (secuencia, funcid) activos

        self.lienzo = tk.Canvas(self, bg=tema.CONTAINER, highlightthickness=0, bd=0)
        self.lienzo.grid(row=0, column=0, sticky="nsew")
        self._barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview,
                                    style="Vertical.TScrollbar")
        self._barra.grid(row=0, column=1, sticky="ns")
        self.lienzo.configure(yscrollcommand=self._barra.set)

        self.interior = ttk.Frame(self.lienzo, style=tema.TARJETA, padding=padding)
        self.interior.columnconfigure(0, weight=1)
        self._ventana = self.lienzo.create_window((0, 0), window=self.interior,
                                                  anchor="nw")
        # el interior sigue el ancho del lienzo; su alto define la región desplazable
        self.lienzo.bind("<Configure>", self._al_configurar_lienzo)
        self.interior.bind("<Configure>", lambda _e: self._reajustar())
        # Rueda del ratón mientras el puntero está sobre el área. Se engancha al
        # Toplevel (que está en los bindtags de todos los hijos, así que la rueda
        # funciona aunque el puntero esté sobre un widget interior) con add="+" y
        # se guarda el funcid para soltarlo selectivamente al salir, sin tocar el
        # binding global "all" que compartirían las demás áreas desplazables.
        self.lienzo.bind("<Enter>", self._activar_rueda)
        self.lienzo.bind("<Leave>", self._desactivar_rueda)
        self.bind("<Destroy>", self._al_destruir)

    def _al_configurar_lienzo(self, e) -> None:
        self.lienzo.itemconfigure(self._ventana, width=e.width)
        self._reajustar()

    def _reajustar(self) -> None:
        self.lienzo.configure(scrollregion=self.lienzo.bbox("all"))
        if self._auto_ocultar:
            if self.interior.winfo_reqheight() > self.lienzo.winfo_height() + self._margen:
                self._barra.grid()
            else:
                self._barra.grid_remove()
                self.lienzo.yview_moveto(0)
        # El on_reconfigure (recalcular wraplength de muchas labels) se debouncea:
        # en un arrastre de redimensionado los <Configure> llegan en ráfaga.
        if self._on_reconfigure is not None:
            if self._id_reconfig is not None:
                self.after_cancel(self._id_reconfig)
            self._id_reconfig = self.after(80, self._disparar_reconfigure)

    def _disparar_reconfigure(self) -> None:
        self._id_reconfig = None
        if self._on_reconfigure is not None and self.winfo_exists():
            self._on_reconfigure()

    def _activar_rueda(self, _e=None) -> None:
        if not self._wheel_binds:
            top = self.winfo_toplevel()
            for sec in SECUENCIAS_RUEDA:
                self._wheel_binds.append((sec, top.bind(sec, self._rueda, add="+")))

    def _desactivar_rueda(self, _e=None) -> None:
        if self._wheel_binds:
            top = self.winfo_toplevel()
            for sec, fid in self._wheel_binds:
                try:
                    top.unbind(sec, fid)
                except Exception:  # noqa: BLE001
                    pass
            self._wheel_binds = []

    def _al_destruir(self, e) -> None:
        # Solo el evento propio del marco (no el de un hijo): suelta la rueda y el
        # after pendiente para no dejar callbacks colgados.
        if e.widget is self:
            self._desactivar_rueda()
            if self._id_reconfig is not None:
                try:
                    self.after_cancel(self._id_reconfig)
                except Exception:  # noqa: BLE001
                    pass
                self._id_reconfig = None

    def _rueda(self, event) -> None:
        if self.interior.winfo_reqheight() > self.lienzo.winfo_height():
            pasos = pasos_rueda(event)
            if pasos:
                self.lienzo.yview_scroll(pasos, "units")


class Tooltip:
    """Ayuda emergente sobre un widget: aparece tras un breve retardo al pasar el
    ratón y se oculta al salir, pulsar o destruirse el widget. Ligera: crea un
    Toplevel sin bordes solo mientras se muestra. El texto se puede cambiar en
    caliente con `actualizar` (p. ej. una ruta que va cambiando)."""

    def __init__(self, widget: tk.Widget, texto: str = "", *,
                 retardo: int = 500) -> None:
        self.widget = widget
        self.texto = texto
        self.retardo = retardo
        self._id: "str | None" = None
        self._tip: "tk.Toplevel | None" = None
        widget.bind("<Enter>", self._programar, add="+")
        widget.bind("<Leave>", self._ocultar, add="+")
        widget.bind("<ButtonPress>", self._ocultar, add="+")
        widget.bind("<Destroy>", self._ocultar, add="+")

    def actualizar(self, texto: str) -> None:
        self.texto = texto
        if self._tip is not None:            # visible: se rehará al siguiente hover
            self._ocultar()

    def _programar(self, _e=None) -> None:
        self._cancelar()
        if self.texto:
            self._id = self.widget.after(self.retardo, self._mostrar)

    def _mostrar(self) -> None:
        self._id = None
        if self._tip is not None or not self.texto:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self._tip = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(tw, text=self.texto, wraplength=320)
            tema.estilo_tooltip(lbl)
            lbl.pack()
        except tk.TclError:
            self._tip = None

    def _ocultar(self, _e=None) -> None:
        self._cancelar()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None

    def _cancelar(self) -> None:
        if self._id is not None:
            try:
                self.widget.after_cancel(self._id)
            except tk.TclError:
                pass
            self._id = None


class DialogoReanudar:
    """Modal propio «Reanudar tarea» con botones ETIQUETADOS (en vez del
    Sí/No/Cancelar nativo, que obligaba a explicar el mapeo en el texto). Devuelve,
    con el mismo contrato que antes: False = continuar donde se quedó, True = empezar
    de cero, None = cancelar (cerrar la ventana o Esc también cancelan).

    El constructor solo crea los widgets (no bloquea): `mostrar()` hace el modal
    (transient + grab + wait_window). Así se puede probar sin bloquear la suite."""

    def __init__(self, parent: tk.Misc, mensaje: str) -> None:
        self.parent = parent
        self.resultado: "bool | None" = None
        self.win = win = tk.Toplevel(parent)
        win.withdraw()                       # oculto hasta mostrar (sin parpadeo)
        win.title("Reanudar tarea")
        win.configure(bg=tema.CONTAINER)
        win.resizable(False, False)

        marco = ttk.Frame(win, style=tema.TARJETA, padding=16)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text="Reanudar tarea", style=tema.LBL_TITULO).pack(anchor="w")
        ttk.Label(marco, text=mensaje, style=tema.LBL, wraplength=380,
                  justify="left").pack(anchor="w", pady=(8, 16))
        fila = ttk.Frame(marco, style=tema.TARJETA)
        fila.pack(anchor="e")
        # Empaquetados a la derecha en orden inverso -> L→R: Continuar · Cero · Cancelar.
        self._b_cancelar = ttk.Button(fila, text="Cancelar", style=tema.FANTASMA,
                                      command=lambda: self._elegir(None))
        self._b_cancelar.pack(side="right", padx=(6, 0))
        self._b_cero = ttk.Button(fila, text="Empezar de cero", style=tema.BTN,
                                  command=lambda: self._elegir(True))
        self._b_cero.pack(side="right", padx=(6, 0))
        self._b_continuar = ttk.Button(fila, text="Continuar", style=tema.ACCION,
                                       command=lambda: self._elegir(False))
        self._b_continuar.pack(side="right", padx=(6, 0))

        win.protocol("WM_DELETE_WINDOW", lambda: self._elegir(None))
        win.bind("<Escape>", lambda _e: self._elegir(None))
        win.bind("<Return>", lambda _e: self._elegir(False))   # Enter = Continuar

    def _elegir(self, valor: "bool | None") -> None:
        self.resultado = valor
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def mostrar(self) -> "bool | None":
        win = self.win
        try:
            win.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass
        win.deiconify()
        win.update_idletasks()
        # Centrado sobre la ventana principal.
        try:
            top = self.parent.winfo_toplevel()
            x = top.winfo_rootx() + (top.winfo_width() - win.winfo_width()) // 2
            y = top.winfo_rooty() + (top.winfo_height() - win.winfo_height()) // 3
            win.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        self._b_continuar.focus_set()
        try:
            win.grab_set()
            self.parent.wait_window(win)
        except tk.TclError:
            pass
        return self.resultado


def dialogo_reanudar(parent: tk.Misc, mensaje: str) -> "bool | None":
    """Atajo: muestra el modal de reanudación y devuelve su resultado
    (False = continuar, True = empezar de cero, None = cancelar)."""
    return DialogoReanudar(parent, mensaje).mostrar()


def fila_texto(marco: tk.Misc, etiqueta: str, var: tk.StringVar, *,
               width: int = 24) -> "tuple[ttk.Frame, ttk.Entry]":
    """Fila «etiqueta + Entry» dentro de `marco`. Devuelve (fila, entry) para que
    quien la use la coloque y registre el Entry como bloqueable."""
    fila = ttk.Frame(marco, style=tema.TARJETA)
    ttk.Label(fila, text=etiqueta, style=tema.LBL_TITULO).pack(side="left")
    entry = ttk.Entry(fila, textvariable=var, width=width)
    entry.pack(side="left", padx=(6, 0))
    return fila, entry
