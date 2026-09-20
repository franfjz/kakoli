# -*- coding: utf-8 -*-
"""reanudable — registro de progreso REANUDABLE, común a todas las tareas (núcleo,
SIN Tkinter).

Un único mecanismo para persistir "qué unidades ya se procesaron" y poder continuar
tras una PAUSA, una CANCELACIÓN o un cierre del programa. Vive en el `core` para que
lo use cualquier tarea actual y sea trivial adoptarlo en tareas futuras.

Diseño (el patrón probado en la compresión, generalizado):
  - Fichero JSONL (una línea JSON por evento) al que solo se AÑADE: el coste por
    unidad es CONSTANTE (no reescribe el fichero entero como una instantánea).
  - Primera línea = cabecera {formato, tarea, origen, firma, creado}. Al cargar se
    valida: si la tarea/origen/firma no casan (o el fichero es ilegible), se empieza
    de cero (y se borra el fichero incongruente).
  - Una línea `{"u": <unidad>, ...}` por unidad COMPLETADA (la tarea decide qué campos
    guarda además de la unidad). Líneas `{"error": ...}` y `{"descarta": ...,
    "motivo": ...}` para lo informativo.
  - Volcado por bloques (`PASO_REGISTRO`): un corte ABRUPTO (kill -9, apagón) rehace
    como mucho ese número de unidades. Las paradas ordenadas (pausa/cancelación/fin)
    vuelcan con `guardar()`/`cerrar()`/`completar()`.
  - Compactación: si el fichero acumula muchas líneas repetidas (reanudaciones
    sucesivas), se reescribe entero de forma ATÓMICA (`.part` + `os.replace`).

Seguro entre hilos: `marca`/`descarta`/`error` toman un cerrojo interno, así que
varios workers pueden anotar a la vez.

`firma` = las opciones que afectan al RESULTADO (p. ej. modo de nombre, separador,
conflicto). Si cambian, el progreso guardado no vale y se empieza de cero.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from core.formato import PASO_REGISTRO, ahora

# Formato de la cabecera (rompe con los formatos previos: kakoli está en desarrollo).
FORMATO = "kakoli-reanudable/2"


class RegistroReanudable:
    """Registro de progreso reanudable en JSONL, común a todas las tareas.

    Ciclo de vida típico de una tarea:
        reg = RegistroReanudable.cargar(ruta, tarea, origen, firma)
        ya  = reg.procesados()                 # unidades a saltar
        ...  reg.marca(unidad, **datos)  / reg.anota(unidad, salida)  # por unidad
        ...  reg.descarta(unidad, motivo) / reg.error(msg)
        # al pausar/cancelar/error:  reg.guardar()   (persiste y deja el fichero)
        # al terminar bien:          reg.completar(borrar=True)  (borra el fichero)
    """

    def __init__(self, ruta: "Path | str", tarea: str, origen: "Path | str",
                 firma: dict) -> None:
        self.ruta = Path(ruta)
        self.tarea = str(tarea)
        self.origen = str(origen)
        self.firma = dict(firma)
        self.creado = ahora()
        self.hechos: dict[str, dict] = {}      # unidad -> registro (dict con "u")
        self.errores: list[str] = []
        self.descartados: list[dict] = []
        self._fh = None
        self._sin_vaciar = 0
        self._cerrojo = threading.Lock()

    # ---------------- carga ----------------
    @classmethod
    def cargar(cls, ruta: "Path | str", tarea: str, origen: "Path | str",
               firma: dict, *, reiniciar: bool = False,
               log=print) -> "RegistroReanudable":
        """Registro para (ruta, tarea, origen, firma). Si `reiniciar`, o si el fichero
        guardado no corresponde (otra tarea/origen/opciones) o es ilegible, se empieza
        de cero (borrando el fichero incongruente)."""
        reg = cls(ruta, tarea, str(origen), firma)
        if reiniciar:
            reg._borrar_fichero()
            return reg
        cab, hechos, errores, descartados, lineas = cls._leer(reg.ruta)
        if cab is None:
            return reg                          # no existe o ilegible -> de cero
        if not reg._cabecera_valida(cab):
            log("[!] El progreso guardado no corresponde a esta tarea/opciones; "
                "se empieza de cero.")
            reg._borrar_fichero()
            return reg
        reg.creado = cab.get("creado", reg.creado)
        reg.hechos = hechos
        reg.errores = errores
        reg.descartados = descartados
        # Muchas líneas para pocas unidades (reanudaciones sucesivas) -> compactar.
        if reg.hechos and lineas > 2 * len(reg.hechos) and lineas > 200:
            reg._compactar(log)
        return reg

    @staticmethod
    def _leer(ruta: Path):
        """Lee el JSONL. Devuelve (cabecera|None, hechos, errores, descartados,
        n_lineas_de_cuerpo). cabecera None = no existe / ilegible / sin cabecera."""
        try:
            with open(ruta, encoding="utf-8") as fh:
                primera = fh.readline()
                try:
                    cab = json.loads(primera) if primera else None
                except json.JSONDecodeError:
                    cab = None
                if not isinstance(cab, dict):
                    return None, {}, [], [], 0
                hechos: dict[str, dict] = {}
                errores: list[str] = []
                descartados: list[dict] = []
                lineas = 0
                for linea in fh:
                    linea = linea.strip()
                    if not linea:
                        continue
                    lineas += 1
                    try:
                        d = json.loads(linea)
                    except json.JSONDecodeError:
                        continue                # línea a medias por un corte: se ignora
                    if "u" in d:
                        hechos[d["u"]] = d
                    elif "error" in d:
                        errores.append(d["error"])
                    elif "descarta" in d:
                        descartados.append(d)
                return cab, hechos, errores, descartados, lineas
        except OSError:
            return None, {}, [], [], 0

    def _cabecera_valida(self, cab: dict) -> bool:
        return (cab.get("formato") == FORMATO
                and cab.get("tarea") == self.tarea
                and cab.get("origen") == self.origen
                and cab.get("firma") == self.firma)

    def _borrar_fichero(self) -> None:
        try:
            self.ruta.unlink()
        except OSError:
            pass

    # ---------------- inspección (para el modal de la GUI) ----------------
    @classmethod
    def inspeccionar(cls, ruta: "Path | str", tarea: str, origen: "Path | str",
                     firma: dict) -> "dict | None":
        """Si hay progreso PENDIENTE para (tarea, origen, firma) devuelve
        `{"fecha", "hechas"}`; si no (no existe, no casa, o 0 hechas), None. Base del
        modal «Continuar / Empezar de cero» y COMÚN a todas las tareas reanudables."""
        ruta = Path(ruta)
        cab, hechos, _e, _d, _n = cls._leer(ruta)
        if cab is None:
            return None
        ref = cls(ruta, tarea, str(origen), firma)
        if not ref._cabecera_valida(cab) or not hechos:
            return None
        fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(ruta.stat().st_mtime))
        return {"fecha": fecha, "hechas": len(hechos)}

    # ---------------- consulta ----------------
    def procesados(self) -> "set[str]":
        return set(self.hechos)

    def hecho(self, unidad: str) -> bool:
        return unidad in self.hechos

    def entrada(self, unidad: str) -> "dict | None":
        return self.hechos.get(unidad)

    def salida_de(self, unidad: str) -> "str | None":
        ent = self.hechos.get(unidad)
        return ent.get("salida") if ent else None

    # ---------------- cabecera / escritura ----------------
    def _cabecera(self) -> dict:
        return {"formato": FORMATO, "tarea": self.tarea, "origen": self.origen,
                "firma": self.firma, "creado": self.creado}

    def _asegurar_fh(self):
        if self._fh is None:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            nuevo = not self.ruta.exists()
            self._fh = open(self.ruta, "a", encoding="utf-8")
            if nuevo:
                self._fh.write(json.dumps(self._cabecera(), ensure_ascii=False) + "\n")
        return self._fh

    def _anadir(self, dato: dict) -> None:
        fh = self._asegurar_fh()
        fh.write(json.dumps(dato, ensure_ascii=False) + "\n")
        self._sin_vaciar += 1
        if self._sin_vaciar >= PASO_REGISTRO:
            fh.flush()
            self._sin_vaciar = 0

    def marca(self, unidad: str, **datos) -> None:
        """Marca `unidad` como COMPLETADA, guardando los campos que pase la tarea
        (p. ej. `salida=`, o `zip=`/`bytes=`…). O(1): añade una línea."""
        ent = {"u": unidad, **datos}
        with self._cerrojo:
            self.hechos[unidad] = ent
            self._anadir(ent)

    def anota(self, unidad: str, salida: str) -> None:
        """Azúcar para tareas que solo guardan la SALIDA asignada a la unidad."""
        self.marca(unidad, salida=salida)

    def descarta(self, unidad: str, motivo: str) -> None:
        """Registra una unidad NO escrita (mantener/reemplazar-perdedor), informativo."""
        d = {"descarta": unidad, "motivo": motivo}
        with self._cerrojo:
            self.descartados.append(d)
            self._anadir(d)

    def error(self, msg: str) -> None:
        with self._cerrojo:
            if msg not in self.errores:
                self.errores.append(msg)
                self._anadir({"error": msg})

    def anotar_errores(self, errores) -> None:
        for e in errores:
            self.error(e)

    # ---------------- volcado / cierre ----------------
    def _volcar(self) -> None:
        """Reescribe el fichero ENTERO de forma atómica (solo al compactar/cerrar sin
        borrar): cabecera + una línea por unidad/descartado/error."""
        self._cerrar_fh()
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ruta.with_name(self.ruta.name + ".part")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(self._cabecera(), ensure_ascii=False) + "\n")
            for ent in self.hechos.values():
                fh.write(json.dumps(ent, ensure_ascii=False) + "\n")
            for d in self.descartados:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
            for e in self.errores:
                fh.write(json.dumps({"error": e}, ensure_ascii=False) + "\n")
        os.replace(tmp, self.ruta)

    def _compactar(self, log=print) -> None:
        self._volcar()
        log("Registro de progreso compactado.")

    def guardar(self) -> None:
        """Persiste el progreso y libera el fichero (parada ordenada: pausa/cancelación/
        error que conserva el avance). Deja el fichero para reanudar."""
        with self._cerrojo:
            if self._fh is not None:
                self._fh.flush()
                self._cerrar_fh()
            elif self.hechos or self.errores or self.descartados:
                self._volcar()

    def _cerrar_fh(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()              # close() vacía lo pendiente
            finally:
                self._fh = None
                self._sin_vaciar = 0

    def cerrar(self) -> None:
        """Cierra el fichero conservándolo (el avance queda persistido)."""
        with self._cerrojo:
            self._cerrar_fh()

    def completar(self, *, borrar: bool = True) -> None:
        """Cierra al terminar BIEN. Si `borrar` (def.), elimina el fichero (la salida
        queda limpia); si no, vuelca el estado final y lo conserva."""
        with self._cerrojo:
            if borrar:
                self._cerrar_fh()
                self._borrar_fichero()
            else:
                self._volcar()
