#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
tasks/descomprimir/motor.py — Proceso inverso de Comprimir.

A partir de un ZIP anidado rehace el árbol de carpetas original, trabajando
del nivel superior al inferior: extrae el ZIP principal, y cada .zip que
aparece dentro se convierte en su carpeta correspondiente, y así hacia abajo.

Un .zip solo se convierte en carpeta si lleva la marca que escribe
motor_comprimir.py (en el comentario del ZIP), así que los .zip que formaban
parte de tus datos se quedan como archivos. Con `expandir_todos` se expande
cualquier .zip, útil para archivos hechos con versiones anteriores.

Es pausable y reanudable: cada carpeta se extrae en un temporal y solo se
renombra al terminar, y el .zip de origen se borra después. Si se corta a
medias, al relanzarlo se detectan los .zip que quedan pendientes y sigue.

Uso directo por consola:
    python -m tasks.descomprimir.motor ARCHIVO.zip [-d DESTINO] [opciones]
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
import zipfile
from core import paralelo
from core import recursos
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

MB = 1024 * 1024

# Lo genérico se importa del núcleo; solo leer_marca (dominio ZIP) viene del
# motor de compresión.
from core.cli import correr_cli
from core.formato import PASO_REGISTRO, duracion, humano
from core.opciones import OpcionesBase
from core.resultado import Resultado
from core.control import Control
from tasks.formatos.formato_zip import leer_marca

SUFIJO_PARCIAL = ".__parcial__"
SUFIJO_RENOMBRE = ".subcarpeta"
PAUSE_NAME = "PAUSA"


@dataclass
class Opciones(OpcionesBase):
    # detallado/politica + recorrido de FS se heredan de OpcionesBase.
    verificar: bool = False          # comprobar CRC antes de extraer
    sobrescribir: bool = False       # borrar la carpeta destino si ya existe
    expandir_todos: bool = False     # expandir .zip aunque no lleven la marca
    max_zips: int = 0                # parar tras N zips (0 = sin límite)
    conservar_zips: bool = False     # no borrar los .zip ya expandidos


def ejecutar(entradas: dict, opts: Opciones, *, log: Callable[[str], None] = print,
             progreso=None, pausar=None, cancelar=None, confirmar=None) -> Resultado:
    """Contrato uniforme para la GUI (B). `entradas` = {"origen": <zip>,
    "destino": <carpeta>}; mapea a procesar()."""
    z, destino = entradas["origen"], entradas["destino"]
    log(f"Origen : {z}")
    log(f"Destino: {destino}")
    return procesar(z, destino, opts, log=log, progreso=progreso,
                    pausar=pausar, cancelar=cancelar, confirmar=confirmar)


# --------------------------------------------------------------------------
# Ayudas
# --------------------------------------------------------------------------

def es_contenedor(zip_path: Path, opts: Opciones) -> tuple[bool, str]:
    """(¿representa una carpeta?, nombre de la carpeta)."""
    marca = leer_marca(zip_path)
    if marca:
        return True, str(marca.get("carpeta") or zip_path.stem)
    if opts.expandir_todos and zipfile.is_zipfile(zip_path):
        nombre = zip_path.stem
        if nombre.endswith(SUFIJO_RENOMBRE):
            nombre = nombre[: -len(SUFIJO_RENOMBRE)]
        return True, nombre
    return False, ""


def zips_pendientes(carpeta: Path, opts: Opciones) -> list[Path]:
    """Todos los .zip del árbol que aún deben convertirse en carpetas."""
    encontrados: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(carpeta):
        for nombre in filenames:
            if not nombre.lower().endswith(".zip"):
                continue
            ruta = Path(dirpath) / nombre
            if es_contenedor(ruta, opts)[0]:
                encontrados.append(ruta)
    # De arriba abajo: primero los más cercanos a la raíz.
    encontrados.sort(key=lambda p: (len(p.parts), str(p)))
    return encontrados


def _destino_seguro(base_str: str, nombre_interno: str) -> Path:
    """Ruta de salida segura, evitando el 'zip slip'. `base_str` es la carpeta
    destino YA resuelta (una sola vez por ZIP). #7 (optimización): se evita el
    resolve() por cada entrada (era un realpath/syscall por archivo); basta con
    normalizar y comprobar que sigue dentro de `base_str`. Como el extractor
    nunca crea enlaces simbólicos, no hay redirección posible a mitad."""
    limpio = nombre_interno.replace("\\", "/")
    if limpio.startswith("/") or ".." in limpio.split("/"):
        raise ValueError(f"entrada con ruta no permitida: {nombre_interno}")
    # En Windows, ':' es letra de unidad o flujo ADS (archivo:flujo); ningún
    # nombre legítimo lo lleva. En POSIX ':' sí es válido en nombres.
    if os.name == "nt" and ":" in limpio:
        raise ValueError(f"entrada con ruta no permitida: {nombre_interno}")
    destino = os.path.normpath(os.path.join(base_str, limpio))
    if destino != base_str and not destino.startswith(base_str + os.sep):
        raise ValueError(f"entrada con ruta no permitida: {nombre_interno}")
    return Path(destino)


def _buffer_copia(perf: "recursos.PerfilSistema") -> int:
    """Tamaño del buffer de copia según la RAM libre (Fase 6): más grande si
    sobra memoria, más pequeño si escasea. Entre 256 KB y 4 MB."""
    disp = perf.ram_disponible
    if disp <= 0:
        return 1 * MB
    if disp < 512 * MB:
        return 256 * 1024
    if disp < 2 * 1024 * MB:
        return 1 * MB
    if disp < 8 * 1024 * MB:
        return 2 * MB
    return 4 * MB


def extraer_zip(zip_path: Path, destino: Path, opts: Opciones,
                log: Callable[[str], None], buffer: int = MB) -> tuple[int, int]:
    """Extrae un ZIP en una carpeta nueva. Devuelve (archivos, bytes)."""
    parcial = destino.with_name(destino.name + SUFIJO_PARCIAL)
    if parcial.exists():
        shutil.rmtree(parcial)
    parcial.mkdir(parents=True)
    base_str = str(parcial.resolve())   # #7: se resuelve UNA vez por ZIP
    archivos = total = 0

    try:
        with zipfile.ZipFile(zip_path) as zf:
            if opts.verificar and zf.testzip() is not None:
                raise zipfile.BadZipFile("CRC incorrecto")
            for info in zf.infolist():
                # La comprobación anti-zip-slip también para las entradas de
                # directorio (antes solo se aplicaba a los archivos).
                salida = _destino_seguro(base_str, info.filename)
                if info.is_dir():
                    salida.mkdir(parents=True, exist_ok=True)
                    continue
                salida.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as origen, open(salida, "wb") as dst:
                    shutil.copyfileobj(origen, dst, buffer)
                try:
                    t = datetime(*info.date_time).timestamp()
                    os.utime(salida, (t, t))
                except (ValueError, OSError):
                    pass
                archivos += 1
                total += info.file_size
        if destino.exists():
            shutil.rmtree(destino)
        os.replace(parcial, destino)
    except BaseException:
        shutil.rmtree(parcial, ignore_errors=True)
        raise

    return archivos, total


# --------------------------------------------------------------------------
# Motor
# --------------------------------------------------------------------------

def rutas_validadas(zip_path: Path, destino: Path | None) -> tuple[Path, Path]:
    """Devuelve (zip, carpeta_destino) absolutos. Lanza ValueError si no cuadra."""
    z = Path(zip_path).expanduser().resolve()
    if not z.is_file():
        raise ValueError(f"'{zip_path}' no es un archivo.")
    if not zipfile.is_zipfile(z):
        raise ValueError(f"'{z.name}' no parece un archivo ZIP.")
    dst = Path(destino).expanduser().resolve() if destino else z.parent
    if dst.exists() and not dst.is_dir():
        raise ValueError(f"'{dst}' existe y no es una carpeta.")
    return z, dst


class _PlanDescomp:
    """
    Plan para el Ejecutor (Fase 6). A diferencia del Planificador de comprimir,
    aquí las unidades APARECEN sobre la marcha: al extraer un contenedor surgen
    sus .zip hijos, que son independientes entre sí y se pueden extraer ya.

    `restantes` cuenta las unidades añadidas y aún no terminadas (listas +
    en vuelo), así que solo llega a 0 cuando de verdad no queda nada.
    """

    def __init__(self, iniciales) -> None:
        self._lock = threading.Lock()
        self._listas = deque(iniciales)
        self.restantes = len(self._listas)

    def agregar(self, items) -> None:
        if not items:
            return
        with self._lock:
            self._listas.extend(items)
            self.restantes += len(items)

    def siguiente(self):
        with self._lock:
            return self._listas.popleft() if self._listas else None

    def terminada(self, item) -> None:
        with self._lock:
            self.restantes -= 1

    def pendientes(self) -> int:
        with self._lock:
            return len(self._listas)


def _expandir_uno(z: Path, objetivo: Path, opts: Opciones, buffer: int,
                  log: Callable[[str], None]):
    """Extrae un contenedor. Devuelve (rel, archivos, bytes, nuevos) o None si
    resultó no ser un contenedor. `nuevos` = .zip hijos que han aparecido."""
    es_cont, nombre = es_contenedor(z, opts)
    if not es_cont:
        return None
    carpeta = z.parent / nombre
    rel = carpeta.relative_to(objetivo.parent)
    n, b = extraer_zip(z, carpeta, opts, log, buffer)
    if not opts.conservar_zips:
        z.unlink(missing_ok=True)   # solo tras cerrar el temporal (os.replace ya pasó)
    nuevos = [p for p in sorted(carpeta.iterdir())
              if p.is_file() and es_contenedor(p, opts)[0]]
    return rel, n, b, nuevos


def procesar(zip_origen: Path, destino: Path, opts: Opciones, *,
             log: Callable[[str], None] = print,
             progreso: Callable[[int, int, float, str], None] | None = None,
             pausar: Callable[[], bool] | None = None,
             cancelar: Callable[[], bool] | None = None,
             confirmar: Callable[[str, bool], bool] | None = None) -> Resultado:
    """
    Rehace el árbol de carpetas a partir de un ZIP anidado.
    Misma interfaz de callbacks que motor_comprimir.procesar.
    """
    t0 = time.monotonic()
    pausar = pausar or (lambda: False)
    cancelar = cancelar or (lambda: False)

    marca = leer_marca(zip_origen)
    if not marca and not opts.expandir_todos:
        log("[!] El ZIP no lleva la marca de 'carpeta comprimida'. Se extraerá el "
            "primer nivel; para expandir también los .zip internos, activa "
            "'expandir todos'.")
    nombre_raiz = str(marca.get("carpeta")) if marca else zip_origen.stem
    objetivo = destino / nombre_raiz
    log(f"Carpeta a reconstruir: {objetivo}")

    destino.mkdir(parents=True, exist_ok=True)
    # Fase 2/6: perfil COMÚN de la máquina + modo ligero; de ahí salen el tamaño
    # de buffer y el nº de hilos para la descompresión.
    perf = recursos.preparar(destino, opts.politica,
                             ruta_origen=zip_origen.parent, log=log)
    buffer = _buffer_copia(perf)
    n_hilos = recursos.calcular_hilos(perf, opts.politica, unidades=0)
    libre = shutil.disk_usage(destino).free
    try:
        with zipfile.ZipFile(zip_origen) as zf:
            estimado = sum(i.file_size for i in zf.infolist())
    except (OSError, zipfile.BadZipFile) as e:
        return Resultado("error", mensaje=f"No se puede leer el ZIP: {e}")
    log(f"Espacio libre: {humano(libre)} (el primer nivel ocupa {humano(estimado)}; "
        f"el total real será mayor)")
    log("Descompresión "
        + (f"en paralelo con {n_hilos} hilos" if n_hilos > 1 else "secuencial")
        + f"; buffer de copia {humano(buffer)}.")

    expandidos = 0
    archivos_tot = bytes_tot = 0
    semilla: list[Path] = []
    ctrl = Control(pausar=pausar, cancelar=cancelar, pausa_ruta=destino / PAUSE_NAME,
                   limite=opts.max_zips, contador=lambda: expandidos,
                   nombre_unidad="ZIP")

    try:
        if objetivo.exists():
            pendientes = zips_pendientes(objetivo, opts)
            if pendientes:
                log(f"Reanudando: quedan {len(pendientes)} ZIP por expandir.")
                semilla.extend(pendientes)
            elif opts.sobrescribir:
                log("Borrando la carpeta destino anterior...")
                shutil.rmtree(objetivo)
            elif any(objetivo.iterdir()):
                msg = (f"La carpeta '{objetivo.name}' ya existe y parece completa. "
                       f"¿Borrarla y volver a extraer?")
                if confirmar and confirmar(msg, False):
                    shutil.rmtree(objetivo)
                else:
                    log("Nada que hacer: ya estaba descomprimido.")
                    return Resultado("nada", ruta_final=objetivo,
                                     segundos=time.monotonic() - t0)
            else:
                objetivo.rmdir()

        if not objetivo.exists():
            log(f"[1] {zip_origen.name} -> {objetivo.name}/")
            n, b = extraer_zip(zip_origen, objetivo, opts, log, buffer)
            archivos_tot += n
            bytes_tot += b
            expandidos += 1
            log(f"      {n} archivos, {humano(b)}")
            semilla.extend(p for p in sorted(objetivo.iterdir())
                           if p.is_file() and es_contenedor(p, opts)[0])

        if n_hilos <= 1:
            # ---- Camino SECUENCIAL de siempre ----
            cola: deque[Path] = deque(semilla)
            while cola:
                if ctrl.debe_parar():
                    break
                z = cola.popleft()
                res = _expandir_uno(z, objetivo, opts, buffer, log)
                if res is None:
                    continue
                rel, n, b, nuevos = res
                cola.extend(nuevos)
                archivos_tot += n
                bytes_tot += b
                expandidos += 1
                if progreso:
                    total = expandidos + len(cola)
                    progreso(expandidos, total, expandidos / max(1, total), str(rel))
                if opts.detallado:
                    log(f"[{expandidos}] {rel} — {n} archivos, {humano(b)}"
                        + (f", {len(nuevos)} subcarpetas por expandir" if nuevos else ""))
                elif expandidos % PASO_REGISTRO == 0:
                    log(f"[{expandidos}] {rel} — {archivos_tot} archivos, "
                        f"{humano(bytes_tot)}")
        else:
            # ---- Camino PARALELO (Fase 6): los .zip hijos son independientes ----
            # Cada worker extrae un contenedor y encola los hijos que aparezcan.
            # inflate y la E/S liberan el GIL, así que hay ganancia real.
            plan = _PlanDescomp(semilla)
            estado_lock = threading.Lock()

            def trabajo(z):
                nonlocal expandidos, archivos_tot, bytes_tot
                res = _expandir_uno(z, objetivo, opts, buffer, log)
                if res is None:
                    return
                rel, n, b, nuevos = res
                plan.agregar(nuevos)
                with estado_lock:
                    expandidos += 1
                    archivos_tot += n
                    bytes_tot += b
                    hechos, arch_ahora, bytes_ahora = expandidos, archivos_tot, bytes_tot
                if opts.detallado:
                    log(f"[{hechos}] {rel} — {n} archivos, {humano(b)}"
                        + (f", {len(nuevos)} subcarpetas por expandir" if nuevos else ""))
                elif hechos % PASO_REGISTRO == 0:
                    log(f"[{hechos}] {rel} — {arch_ahora} archivos, {humano(bytes_ahora)}")
                if progreso:
                    total = hechos + plan.pendientes() + 1
                    progreso(hechos, total, hechos / total, str(rel))

            ejec = paralelo.Ejecutor(n_hilos)
            # Fase 8: ceder CPU si el equipo se ocupa con otras cosas.
            limite = (recursos.regulador_carga(perf.cpu, n_hilos)
                      if opts.politica.throttling else None)
            ctrl.desde_ejecutor(ejec.ejecutar(plan, trabajo, ctrl.debe_pausar,
                                              limite_activos=limite, cancelar=cancelar))

    except KeyboardInterrupt:
        rest = len(zips_pendientes(objetivo, opts)) if objetivo.exists() else 0
        return Resultado("pausado", expandidos, rest, expandidos + rest,
                         [], objetivo, "Proceso cortado; la carpeta a medias se ha "
                         "descartado.", time.monotonic() - t0)
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        rest = len(zips_pendientes(objetivo, opts)) if objetivo.exists() else 0
        return Resultado("error", expandidos, rest, expandidos + rest,
                         [], objetivo, str(e), time.monotonic() - t0)

    seg = time.monotonic() - t0
    log(f"{expandidos} ZIP expandidos, {archivos_tot} archivos, "
        f"{humano(bytes_tot)} en {duracion(seg)}.")

    # Solo se considera "pausado" si de verdad queda trabajo: si el límite
    # (max_zips) coincidió justo con el final, no queda nada -> completado.
    restantes = len(zips_pendientes(objetivo, opts)) if ctrl.motivo else 0
    if restantes:
        log(ctrl.motivo or "Proceso detenido.")
        log(f"Quedan {restantes} ZIP. Vuelve a lanzarlo para continuar.")
        return Resultado(ctrl.estado, expandidos, restantes, expandidos + restantes,
                         [], objetivo, ctrl.motivo, seg)

    if progreso:
        progreso(expandidos, expandidos, 1.0, objetivo.name)
    log(f"Completado. Carpeta: {objetivo}")
    return Resultado("completado", expandidos, 0, expandidos, [], objetivo, "", seg)


# --------------------------------------------------------------------------
# Consola
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Rehace el árbol de carpetas a partir de un ZIP anidado.")
    p.add_argument("archivo", type=Path, help="ZIP principal")
    p.add_argument("-d", "--destino", type=Path, default=None,
                   help="carpeta donde crear el resultado (def.: junto al ZIP)")
    p.add_argument("-y", "--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--verificar", action="store_true", help="comprobar CRC al extraer")
    p.add_argument("--sobrescribir", action="store_true",
                   help="borrar la carpeta destino si ya existe")
    p.add_argument("--expandir-todos", action="store_true",
                   help="expandir cualquier .zip, lleve marca o no")
    p.add_argument("--conservar-zips", action="store_true",
                   help="no borrar los .zip intermedios tras expandirlos")
    p.add_argument("--max-zips", type=int, default=0, metavar="N")
    p.add_argument("--resumido", action="store_true",
                   help="una línea de registro cada 50 ZIP en vez de una por ZIP")
    args = p.parse_args(argv)

    try:
        z, destino = rutas_validadas(args.archivo, args.destino)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    opts = Opciones(verificar=args.verificar, sobrescribir=args.sobrescribir,
                    expandir_todos=args.expandir_todos, max_zips=args.max_zips,
                    conservar_zips=args.conservar_zips,
                    detallado=not args.resumido)
    return correr_cli(ejecutar, {"origen": z, "destino": destino}, opts,
                      si=args.si)


if __name__ == "__main__":
    sys.exit(main())
