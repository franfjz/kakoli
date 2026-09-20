# -*- coding: utf-8 -*-
"""cache_arbol — caché en disco del recorrido del árbol de carpetas, común a
cualquier tarea REANUDABLE (núcleo, SIN Tkinter).

La primera vez que una tarea recorre el disco puede tardar mucho (millones de
entradas, más aún en un HDD). Si luego se PAUSA/CANCELA y se REANUDA, volver a
recorrerlo entero es puro desperdicio: el árbol no ha cambiado. `CacheArbol`
guarda el resultado del recorrido en un JSON y lo recupera al reanudar,
validándolo con una FIRMA: las opciones que cambian LO QUE PRODUCE el recorrido
(`seguir_enlaces`, `omitir_ocultos`, filtros de la tarea, las carpetas de
origen...). Si la firma no casa (o el fichero es ilegible), se ignora y se vuelve
a explorar.

Es el gemelo "instantánea" de `core.reanudable` (progreso incremental en JSONL):
uno recuerda QUÉ hay que hacer (el árbol de trabajo), el otro QUÉ ya se hizo (el
progreso). Ambos viven en la carpeta de salida y se descartan con `--reiniciar`.

Uso típico en un motor (el mecanismo a adoptar en tareas futuras):

    from core.cache_arbol import CacheArbol

    cache = CacheArbol(salida / "_arbol.json", firma=_firma_arbol(opts))
    items = cache.obtener(
        explorar=lambda: list(mi_walk(origen, opts)),   # el recorrido caro
        reiniciar=opts.reiniciar, log=log)

Cuando el árbol NO es una estructura JSON nativa (listas/dicts de str/num/bool),
se pasan `serializar`/`deserializar` para convertirlo a/desde JSON (lo hace
Comprimir con su árbol de `InfoDir`)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from core.json_util import cargar_json, guardar_json

# Formato de la envoltura en disco (rompe con instantáneas previas sin firma:
# kakoli está en desarrollo). Sube de versión si cambia la estructura {firma,payload}.
FORMATO = "kakoli-arbol/1"


def _identidad(x: Any) -> Any:
    return x


class CacheArbol:
    """Instantánea del recorrido del árbol, validada por una firma.

    - `ruta`  : dónde se guarda el JSON (junto al progreso, en la salida).
    - `firma` : opciones que afectan a LO QUE PRODUCE el recorrido; si cambian,
                la caché guardada no vale y se vuelve a explorar.
    """

    def __init__(self, ruta: "Path | str", firma: "dict | None" = None) -> None:
        self.ruta = Path(ruta)
        self.firma = dict(firma or {})

    # ---------------- E/S ----------------
    def borrar(self) -> None:
        """Descarta la caché (p. ej. con `--reiniciar`)."""
        self.ruta.unlink(missing_ok=True)

    def cargar(self, deserializar: Callable[[Any], Any] = _identidad):
        """Devuelve el árbol cacheado, o None si no existe, no casa el formato/la
        firma, o es ilegible (fichero a medias, JSON corrupto, `payload` inesperado).
        Ante None, quien llama vuelve a explorar el disco."""
        datos = cargar_json(self.ruta)
        if (not isinstance(datos, dict)
                or datos.get("formato") != FORMATO
                or datos.get("firma") != self.firma
                or "payload" not in datos):
            return None
        try:
            return deserializar(datos["payload"])
        except (KeyError, TypeError, ValueError):
            return None

    def guardar(self, payload: Any) -> None:
        """Guarda `payload` (ya JSON-serializable) con la firma y el formato, de
        forma atómica (`core.json_util.guardar_json`)."""
        guardar_json(self.ruta, {"formato": FORMATO, "firma": self.firma,
                                 "payload": payload})

    # ---------------- load-or-explore ----------------
    def obtener(self, explorar: Callable[[], Any], *,
                serializar: Callable[[Any], Any] = _identidad,
                deserializar: Callable[[Any], Any] = _identidad,
                reiniciar: bool = False,
                log: Callable[[str], None] = print) -> Any:
        """Devuelve el árbol: de la caché si es válida, o llamando a `explorar()` y
        cacheando el resultado. `reiniciar` descarta la caché previa y fuerza el
        recorrido. Cachear es una optimización: si el guardado falla (disco lleno,
        permisos), se sigue con el árbol recién explorado en memoria."""
        if reiniciar:
            self.borrar()
        else:
            cache = self.cargar(deserializar)
            if cache is not None:
                log("Árbol de carpetas cargado desde caché (sin volver a explorar el disco).")
                return cache
        arbol = explorar()
        try:
            self.guardar(serializar(arbol))
        except OSError:
            pass
        return arbol
