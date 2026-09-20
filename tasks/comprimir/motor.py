#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
tasks/comprimir/motor.py — Comprime un árbol de carpetas en ZIPs anidados.

Resultado: una carpeta nueva, al mismo nivel que la original, con <carpeta>.zip.
Al descomprimirlo aparecen los archivos sueltos de la carpeta más un .zip por
cada subdirectorio, y así recursivamente.

Cada ZIP generado lleva una "marca" en el comentario del propio archivo ZIP
(metadato, no un archivo dentro) que identifica que representa una carpeta y
guarda su nombre original. motor_descomprimir.py la usa para rehacer el árbol
sin confundir un .zip de datos del usuario con un .zip de carpeta.

Lo genérico vive en el núcleo: `Resultado`/`Cancelado` en `core.resultado`,
`humano`/`duracion`/`ahora` en `core.formato`, `OpcionesBase` en `core.opciones`,
`correr_cli` en `core.cli`. La marca del formato ZIP (`MARCA_FORMATO`/`leer_marca`),
compartida con Descomprimir, en `tasks.formatos.formato_zip`.

RENDIMIENTO
  - Nivel de compresión 1 por defecto: ~8 veces más rápido que el 6 a cambio
    de un 15% más de tamaño. El nivel 9 llega a ser 50 veces más lento.
  - El estado se escribe en un registro por líneas (JSONL) al que solo se
    añade: el coste por carpeta es constante en vez de crecer con el trabajo.
  - Los archivos ya comprimidos (.jpg, .mp4, .zip...) se guardan sin recomprimir.

PARALELISMO (Mejora 6, ya activo — Fase 4)
  procesar() comprime las carpetas hermanas EN PARALELO cuando la máquina lo
  permite: el Planificador entrega las carpetas cuyos hijos ya están listos y el
  Ejecutor de paralelo.py reparte el trabajo entre varios hilos. El nº de hilos
  lo decide recursos.calcular_hilos según CPU/RAM/disco (perfil COMÚN a los
  motores); con 1 hilo se usa el camino secuencial de siempre. Estado,
  Comprimidor.errores y los callbacks log/progreso ya son seguros entre hilos.

MODO COMPACTO (Mejora 5, ya activo)
  - Agrupar subárboles pequeños en un solo ZIP (menos coste por archivo):
      Opciones.agrupar_mb / agrupar_archivos / profundidad_max
        (aplicar_modo_compacto() fija el preset recomendado),
      seleccionar_agrupados()  -> decide qué carpetas se agrupan,
      Comprimidor.crear_agrupado() -> empaqueta el subárbol completo en un ZIP.

Uso directo por consola:
    python -m tasks.comprimir.motor CARPETA [opciones]
"""

from __future__ import annotations

import logging
import shutil
import sys
import threading
import time
import zipfile
from core import paralelo
from core import recursos
from core.cli import correr_cli
from core.formato import PASO_REGISTRO, ahora, duracion, humano
from core.opciones import OpcionesBase
from core.resultado import Cancelado, Resultado
from core.control import Control
from core.reanudable import RegistroReanudable
from core.cache_arbol import CacheArbol
from tasks.comprimir.explorar import (RAIZ, InfoDir, explorar, seleccionar_agrupados,
                                      serializar_arbol, deserializar_arbol)
from tasks.comprimir.comprimidor import Comprimidor
from dataclasses import dataclass
from heapq import heappop, heappush
from pathlib import Path
from typing import Callable

ESTADO_NOMBRE = "_estado_zip.jsonl"
ARBOL_NOMBRE = "_arbol_zip.json"
PAUSE_NAME = "PAUSA"


# Presets de compresión que muestra la interfaz.
PRESETS = (("Rápido (1) — recomendado", 1),
           ("Equilibrado (5)", 5),
           ("Máximo (9) — muy lento", 9))

# Preset del "modo compacto" (Mejora 5): agrupa subárboles pequeños en un solo
# ZIP para pagar menos coste por archivo. profundidad_max = 0 (sin límite de
# anidamiento). La Fase 8 podrá afinar estos umbrales por perfil de máquina.
COMPACTO_AGRUPAR_MB = 8.0
COMPACTO_AGRUPAR_ARCHIVOS = 300
COMPACTO_PROFUNDIDAD_MAX = 0


def aplicar_modo_compacto(opts: "Opciones") -> None:
    """Activa el agrupado de subárboles pequeños con el preset recomendado."""
    opts.agrupar_mb = COMPACTO_AGRUPAR_MB
    opts.agrupar_archivos = COMPACTO_AGRUPAR_ARCHIVOS
    opts.profundidad_max = COMPACTO_PROFUNDIDAD_MAX


# ==========================================================================
# Utilidades compartidas: lo genérico vive en el núcleo (core.resultado/formato/
# opciones/cli); la marca del formato ZIP anidado (MARCA_FORMATO/leer_marca) vive en
# formato_zip.py (compartida con Descomprimir). Aquí queda lo específico del ZIP:
# Estado, Planificador, Comprimidor…
# ==========================================================================


# ==========================================================================
# Opciones
# ==========================================================================

@dataclass
class Opciones(OpcionesBase):
    # detallado, politica y las opciones de recorrido de FS (seguir_enlaces,
    # omitir_ocultos) se heredan de OpcionesBase.
    nivel: int = 1                  # 1 = rápido (por defecto), 5 equilibrado, 9 máximo
    max_dirs: int = 0
    preguntar_cada: int = 0
    verificar: bool = False
    limpiar: bool = False
    reiniciar: bool = False
    estricto: bool = False

    # --- Mejora 5: agrupar subárboles pequeños en un único ZIP ---
    agrupar_mb: float = 0.0         # 0 = desactivado
    agrupar_archivos: int = 0       # 0 = desactivado
    profundidad_max: int = 0        # 0 = sin límite de anidamiento


def ejecutar(entradas: dict, opts: Opciones, *, log: Callable[[str], None] = print,
             progreso=None, pausar=None, cancelar=None, confirmar=None) -> Resultado:
    """Contrato uniforme para la GUI (B del plan de escalabilidad).

    `entradas` = {"origen": <carpeta>, "destino": <salida>}; mapea a procesar()."""
    raiz, salida = entradas["origen"], entradas["destino"]
    log(f"Origen : {raiz}")
    log(f"Salida : {salida}")
    return procesar(raiz, salida, opts, log=log, progreso=progreso,
                    pausar=pausar, cancelar=cancelar, confirmar=confirmar)


def _firma_arbol(opts: Opciones) -> dict:
    """Opciones que cambian LO QUE PRODUCE el recorrido del disco: si cambian, la
    caché del árbol no vale (las demás opciones —nivel, agrupado…— no alteran el
    árbol de carpetas, solo cómo se comprime)."""
    return {"seguir_enlaces": opts.seguir_enlaces, "omitir_ocultos": opts.omitir_ocultos}


def info_reanudable(entradas: dict, opts: "Opciones | None" = None) -> "dict | None":
    """¿Hay una compresión A MEDIAS que se pueda reanudar? (para el modal de la GUI).
    Devuelve `{"fecha", "hechas"}` o None.

    Usa el helper COMÚN `RegistroReanudable.inspeccionar` sobre el estado
    `_estado_zip.jsonl`. El estado persiste tras terminar, así que la tarea está
    completa (nada que reanudar) cuando el ZIP final (`salida/<raíz>.zip`) ya existe."""
    try:
        raiz, salida = Path(entradas["origen"]), Path(entradas["destino"])
    except (KeyError, TypeError):
        return None
    estado_ruta = salida / ESTADO_NOMBRE
    zip_final = salida / f"{raiz.name}.zip"
    if not estado_ruta.exists() or zip_final.exists():
        return None                    # nada previo, o ya completado (existe el ZIP)
    return RegistroReanudable.inspeccionar(estado_ruta, "comprimir", raiz, {})


# ==========================================================================
# Estado: registro por líneas al que solo se añade (reanudación)
# ==========================================================================

class Estado(RegistroReanudable):
    """Registro de progreso de la compresión: el `RegistroReanudable` COMÚN del core
    (JSONL, O(1) por carpeta, seguro entre hilos, reanudable) MÁS la lógica de dominio
    del árbol de ZIPs. Una carpeta está `completado` si su ZIP —o el de un ancestro que
    la embebe— está registrado y sigue en disco. Cada carpeta guarda su ZIP, tamaño y
    nº de entradas por si hay que verificarlos al reanudar (`--verificar`)."""

    def __init__(self, ruta: Path, tarea: str, origen: "Path | str", firma: dict) -> None:
        super().__init__(ruta, tarea, origen, firma)
        self._cache_fs: dict[str, bool] = {}   # ¿el ZIP de esta carpeta sigue en disco?

    @classmethod
    def cargar_zip(cls, ruta: Path, raiz: Path, salida: Path,
                   log: Callable[[str], None] = print) -> "Estado":
        """Carga el estado de comprimir `raiz` en `salida`. La validez depende solo de
        la carpeta origen (raíz); el nivel de compresión y demás opciones no invalidan
        el progreso, así que la firma va vacía."""
        return cls.cargar(ruta, "comprimir", raiz, {}, log=log)

    def marcar(self, rel: Path, destino: Path, tam: int, entradas: int) -> None:
        """Marca una carpeta como comprimida guardando su ZIP/tamaño/entradas."""
        self.marca(rel.as_posix(), zip=str(destino), bytes=tam, entradas=entradas,
                   fin=ahora())
        self._cache_fs[rel.as_posix()] = True

    def _existe(self, clave: str) -> bool:
        """¿El ZIP de esta carpeta está registrado y sigue en disco? (un stat por
        carpeta, cacheado; evita miles de stat)."""
        ent = self.hechos.get(clave)
        if ent is None:
            return False
        v = self._cache_fs.get(clave)
        if v is None:
            v = Path(ent["zip"]).exists()
            self._cache_fs[clave] = v
        return v

    def completado(self, rel: Path) -> bool:
        """Hecho si está registrado (y el ZIP existe) o si ya lo está un ancestro."""
        if self._existe(rel.as_posix()):
            return True
        for padre in rel.parents:
            if self._existe(padre.as_posix()):
                return True
        return rel != RAIZ and self._existe(RAIZ.as_posix())


# ==========================================================================
# Planificador: entrega carpetas listas (hijos ya comprimidos)
# ==========================================================================

class Planificador:
    """
    Devuelve carpetas cuyos hijos pendientes ya están todos comprimidos,
    respetando el orden original (hijos antes que padres).

    MEJORA 6: tal cual está, varios hilos pueden llamar a siguiente() y a
    terminada() a la vez; el cerrojo interno protege las estructuras. Para
    paralelizar solo hay que lanzar N trabajadores que hagan
    `rel = plan.siguiente()` -> comprimir -> `plan.terminada(rel)`.
    """

    def __init__(self, infos: dict[Path, InfoDir], pendientes: list[Path]) -> None:
        self._cerrojo = threading.Lock()
        self._indice = {rel: i for i, rel in enumerate(pendientes)}
        conjunto = set(pendientes)
        self._faltan: dict[Path, int] = {}
        self._listas: list[tuple[int, str, Path]] = []
        self.restantes = len(pendientes)

        for rel in pendientes:
            info = infos.get(rel)
            hijos = 0
            if info is not None:
                hijos = sum(1 for s in info.subdirs if (rel / s) in conjunto)
            self._faltan[rel] = hijos
            if hijos == 0:
                heappush(self._listas, (self._indice[rel], rel.as_posix(), rel))

    def siguiente(self) -> Path | None:
        with self._cerrojo:
            if not self._listas:
                return None
            return heappop(self._listas)[2]

    def terminada(self, rel: Path) -> None:
        with self._cerrojo:
            self.restantes -= 1
            padre = RAIZ if len(rel.parts) <= 1 else rel.parent
            if rel == RAIZ or padre not in self._faltan:
                return
            self._faltan[padre] -= 1
            if self._faltan[padre] == 0:
                heappush(self._listas, (self._indice[padre], padre.as_posix(), padre))

    def hay_listas(self) -> bool:
        with self._cerrojo:
            return bool(self._listas)


# ==========================================================================
# Motor
# ==========================================================================

def rutas_validadas(carpeta: Path, salida: Path | None) -> tuple[Path, Path]:
    """Devuelve (raiz, salida) absolutas. Lanza ValueError si algo no cuadra."""
    raiz = Path(carpeta).expanduser().resolve()
    if not raiz.is_dir():
        raise ValueError(f"'{carpeta}' no es una carpeta.")
    if raiz.parent == raiz:
        raise ValueError("No se puede comprimir la raíz del sistema de archivos.")
    sal = (Path(salida).expanduser().resolve() if salida
           else raiz.parent / f"{raiz.name}_zips")
    if sal == raiz or raiz in sal.parents:
        raise ValueError("La carpeta de salida no puede estar dentro de la carpeta origen.")
    if sal.exists() and not sal.is_dir():
        raise ValueError(f"'{sal}' existe y no es una carpeta.")
    return raiz, sal


def procesar(raiz: Path, salida: Path, opts: Opciones, *,
             log: Callable[[str], None] = print,
             progreso: Callable[[int, int, float, str], None] | None = None,
             pausar: Callable[[], bool] | None = None,
             cancelar: Callable[[], bool] | None = None,
             confirmar: Callable[[str, bool], bool] | None = None) -> Resultado:
    """
    Comprime todo el árbol. Es reanudable: llamarla otra vez continúa donde se dejó.

    log       : recibe líneas de texto (los avisos empiezan por "[!]").
    progreso  : (hechas, pendientes_totales, fraccion 0..1, etiqueta).
    pausar    : si devuelve True, se para de forma ordenada AL TERMINAR la carpeta en curso.
    cancelar  : si devuelve True, se ABORTA la carpeta en curso (su ZIP a medias se
                descarta) y el progreso queda en la última carpeta completada.
    confirmar : (pregunta, valor_por_defecto) -> bool. None = no preguntar nada.
    """
    t0 = time.monotonic()
    pausar = pausar or (lambda: False)
    cancelar = cancelar or (lambda: False)

    salida.mkdir(parents=True, exist_ok=True)
    estado_ruta = salida / ESTADO_NOMBRE
    if opts.reiniciar:
        estado_ruta.unlink(missing_ok=True)

    # Reanudar (tras pausa/cancelación) carga el árbol ya explorado la primera vez
    # en vez de volver a recorrer el disco entero. La caché común lo valida por firma
    # (las opciones de recorrido) y `--reiniciar` la descarta.
    cache = CacheArbol(salida / ARBOL_NOMBRE, _firma_arbol(opts))

    def _explorar():
        log("Explorando el árbol de carpetas...")
        return explorar(raiz, opts.seguir_enlaces, opts.omitir_ocultos, log)

    infos, orden = cache.obtener(_explorar, serializar=serializar_arbol,
                                 deserializar=deserializar_arbol,
                                 reiniciar=opts.reiniciar, log=log)
    total_dirs = len(orden)
    total_bytes = sum(i.bytes for i in infos.values())
    total_files = sum(len(i.archivos) for i in infos.values())
    log(f"  {total_dirs} carpetas, {total_files} archivos, {humano(total_bytes)}")

    estado = Estado.cargar_zip(estado_ruta, raiz, salida, log)

    libre = shutil.disk_usage(salida).free
    necesario = total_bytes if opts.limpiar else int(total_bytes * 2.1)
    log(f"Espacio libre: {humano(libre)} (estimado necesario: ~{humano(necesario)})")
    if libre < necesario:
        aviso = "El espacio libre puede no bastar."
        if confirmar:
            if not confirmar(f"{aviso} ¿Continuar?", False):
                estado.cerrar()
                return Resultado("cancelado", total=total_dirs, mensaje=aviso)
        else:
            log(f"[!] {aviso}")

    # Mejora 5: si el agrupado está activo, las carpetas de dentro no se tratan aparte.
    agrupados = seleccionar_agrupados(infos, orden, opts)
    if agrupados:
        log(f"{len(agrupados)} subárboles se empaquetarán agrupados.")
        orden = [r for r in orden if not any(p in agrupados for p in r.parents)]

    pendientes = [r for r in orden if not estado.completado(r)]
    hechas_antes = len(orden) - len(pendientes)
    if hechas_antes:
        log(f"Reanudando: {hechas_antes} carpetas ya comprimidas, "
            f"quedan {len(pendientes)}.")
        if opts.verificar:
            log("Verificando ZIP existentes...")
            for clave, ent in list(estado.hechos.items()):
                z = Path(ent["zip"])
                if not z.exists():
                    continue
                try:
                    with zipfile.ZipFile(z) as zf:
                        if zf.testzip() is not None:
                            raise zipfile.BadZipFile("CRC incorrecto")
                except (zipfile.BadZipFile, OSError) as e:
                    log(f"[!] {z.name} dañado ({e}); se rehará.")
                    z.unlink(missing_ok=True)
                    estado.hechos.pop(clave, None)
                    estado._cache_fs.pop(clave, None)
            pendientes = [r for r in orden if not estado.completado(r)]

    zip_final = salida / f"{raiz.name}.zip"
    if not pendientes:
        estado.cerrar()
        log("Nada que hacer: el proceso ya estaba completo.")
        return Resultado("nada", total=total_dirs, ruta_final=zip_final,
                         segundos=time.monotonic() - t0)

    if confirmar and not confirmar(f"¿Comprimir {len(pendientes)} carpetas?", True):
        estado.cerrar()
        return Resultado("cancelado", total=total_dirs)

    # Fase 2: se mide la máquina con el perfil COMÚN de recursos y se aplica el
    # modo ligero. Fase 4: con n>1 se comprimen las carpetas hermanas en paralelo.
    perf = recursos.preparar(salida, opts.politica, ruta_origen=raiz, log=log)
    n_hilos = recursos.calcular_hilos(perf, opts.politica, unidades=len(pendientes))
    log(f"Compresión {'en paralelo con ' + str(n_hilos) + ' hilos' if n_hilos > 1 else 'secuencial (1 hilo)'}.")

    comp = Comprimidor(raiz, salida, opts, log, agrupados)
    plan = Planificador(infos, pendientes)
    pausa_ruta = salida / PAUSE_NAME
    bytes_pend = sum(infos[r].bytes for r in pendientes) or 1
    bytes_hechos = 0
    procesadas = 0
    total_pend = len(pendientes)
    ctrl = Control(pausar=pausar, cancelar=cancelar, pausa_ruta=pausa_ruta,
                   limite=opts.max_dirs, contador=lambda: procesadas,
                   nombre_unidad="carpetas")

    try:
        if n_hilos <= 1:
            # ---- Camino SECUENCIAL de siempre (equipos modestos, cero overhead) ----
            while True:
                if ctrl.debe_parar():          # cancelar / pausar / PAUSA / límite
                    break
                if (confirmar and opts.preguntar_cada and procesadas
                        and procesadas % opts.preguntar_cada == 0):
                    if not confirmar("¿Continuar con el proceso?", True):
                        ctrl.motivo = "Pausado a petición del usuario."
                        break

                rel = plan.siguiente()
                if rel is None:
                    break

                info = infos[rel]
                etiqueta = raiz.name if rel == RAIZ else rel.as_posix()
                if opts.detallado:
                    log(f"[{procesadas + 1}/{total_pend}] {etiqueta} "
                        f"({len(info.archivos)} arch., {len(info.subdirs)} subcarpetas, "
                        f"{humano(info.bytes)})")

                # cancelar aborta la carpeta EN CURSO (su .part se descarta y no se
                # marca): el progreso queda en la carpeta anterior completada.
                try:
                    destino, tam, entradas = comp.crear(rel, info, cancelar)
                except Cancelado:
                    ctrl.cancelado = True
                    ctrl.motivo = "Cancelado a petición del usuario."
                    break
                estado.marcar(rel, destino, tam, entradas)
                plan.terminada(rel)
                if opts.limpiar:
                    comp.limpiar_hijos(rel, info)

                bytes_hechos += info.bytes
                procesadas += 1
                if opts.detallado:
                    log(f"      -> {destino.name} ({humano(tam)}, {entradas} entradas)")
                elif procesadas % PASO_REGISTRO == 0:
                    log(f"[{procesadas}/{total_pend}] {etiqueta} "
                        f"— {humano(bytes_hechos)} procesados")
                if progreso:
                    progreso(procesadas, total_pend, bytes_hechos / bytes_pend, etiqueta)
        else:
            # ---- Camino PARALELO (Fase 4): carpetas hermanas a la vez ----
            # El Planificador entrega las carpetas cuyos hijos ya están listos;
            # el Ejecutor reparte, espera dependencias, pausa/cancela y propaga
            # el primer error. estado.marcar, comp.errores y los callbacks
            # log/progreso ya son seguros entre hilos. NO se llama a
            # plan.terminada() aquí: lo hace el Ejecutor al acabar cada unidad.
            if confirmar and opts.preguntar_cada:
                log("[!] 'Preguntar cada N' se ignora en modo paralelo.")
            estado_lock = threading.Lock()

            def trabajo(rel):
                nonlocal procesadas, bytes_hechos
                info = infos[rel]
                etiqueta = raiz.name if rel == RAIZ else rel.as_posix()
                # crear ve cancelar() y, si se pide, lanza Cancelado (el Ejecutor lo
                # trata como parada limpia y para a TODOS los hilos); el .part se borra.
                destino, tam, entradas = comp.crear(rel, info, cancelar)  # zlib libera el GIL
                estado.marcar(rel, destino, tam, entradas)       # ya es thread-safe
                if opts.limpiar:
                    comp.limpiar_hijos(rel, info)
                with estado_lock:
                    procesadas += 1
                    bytes_hechos += info.bytes
                    hechas, bytes_ahora = procesadas, bytes_hechos
                if opts.detallado:
                    log(f"[{hechas}/{total_pend}] {etiqueta} -> {destino.name} "
                        f"({humano(tam)}, {entradas} entradas)")
                elif hechas % PASO_REGISTRO == 0:
                    log(f"[{hechas}/{total_pend}] {etiqueta} "
                        f"— {humano(bytes_ahora)} procesados")
                if progreso:
                    progreso(hechas, total_pend, bytes_ahora / bytes_pend, etiqueta)

            ejec = paralelo.Ejecutor(n_hilos)
            # Fase 8: si el equipo se ocupa con otras cosas, ceder CPU.
            limite = (recursos.regulador_carga(perf.cpu, n_hilos)
                      if opts.politica.throttling else None)
            ctrl.desde_ejecutor(ejec.ejecutar(plan, trabajo, ctrl.debe_pausar,
                                              limite_activos=limite, cancelar=cancelar))

    except KeyboardInterrupt:
        estado.anotar_errores(comp.errores)
        estado.cerrar()
        return Resultado("pausado", procesadas, total_pend - procesadas,
                         total_dirs, comp.errores, None,
                         "Proceso cortado; el ZIP a medias se ha borrado.",
                         time.monotonic() - t0)
    except Exception as e:  # noqa: BLE001
        # El mensaje del Resultado solo lleva el texto; el traceback completo va al
        # log de depuración (silencioso por defecto: sin handler no se ve), para poder
        # diagnosticar sin ensuciar la consola del usuario.
        logging.getLogger(__name__).debug("procesar() falló", exc_info=True)
        estado.anotar_errores(comp.errores)
        estado.cerrar()
        return Resultado("error", procesadas, total_pend - procesadas,
                         total_dirs, comp.errores, None, str(e),
                         time.monotonic() - t0)

    estado.anotar_errores(comp.errores)
    restantes = [r for r in orden if not estado.completado(r)]
    estado.cerrar()
    seg = time.monotonic() - t0
    log(f"{procesadas} carpetas comprimidas en {duracion(seg)}.")
    if comp.errores:
        log(f"[!] {len(comp.errores)} archivos no se pudieron añadir "
            f"(detalle en {estado_ruta}).")

    if restantes:
        log(ctrl.motivo or "Proceso detenido.")
        log(f"Quedan {len(restantes)} carpetas. Vuelve a lanzarlo para continuar.")
        return Resultado(ctrl.estado, procesadas, len(restantes), total_dirs,
                         comp.errores, None, ctrl.motivo, seg)

    try:
        with zipfile.ZipFile(zip_final) as zf:
            n = len(zf.namelist())
        log(f"Completado. ZIP final: {zip_final}")
        log(f"  {humano(zip_final.stat().st_size)}, {n} entradas de primer nivel.")
    except (OSError, zipfile.BadZipFile) as e:
        return Resultado("error", procesadas, 0, total_dirs, comp.errores, None,
                         f"El ZIP final no se pudo verificar: {e}", seg)

    return Resultado("completado", procesadas, 0, total_dirs, comp.errores,
                     zip_final, "", seg)


# ==========================================================================
# Consola
# ==========================================================================

def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Comprime una carpeta en ZIPs anidados (un .zip por subcarpeta), "
                    "de forma incremental y reanudable.")
    p.add_argument("carpeta", type=Path)
    p.add_argument("-s", "--salida", type=Path, default=None,
                   help="carpeta de salida (def.: <carpeta>_zips, al mismo nivel)")
    p.add_argument("-n", "--nivel", type=int, default=1, choices=range(0, 10),
                   metavar="0-9",
                   help="compresión: 1 rápido (def.), 5 equilibrado, 9 máximo y lento")
    p.add_argument("-y", "--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--simular", action="store_true", help="solo mostrar el plan")
    p.add_argument("--resumido", action="store_true",
                   help="una línea de registro cada 50 carpetas en vez de una por carpeta")
    p.add_argument("--max-dirs", type=int, default=0, metavar="N")
    p.add_argument("--preguntar-cada", type=int, default=0, metavar="N")
    p.add_argument("--verificar", action="store_true")
    p.add_argument("--limpiar", action="store_true")
    p.add_argument("--reiniciar", action="store_true")
    p.add_argument("--seguir-enlaces", action="store_true")
    p.add_argument("--omitir-ocultos", action="store_true")
    p.add_argument("--estricto", action="store_true")
    p.add_argument("--compacto", action="store_true",
                   help="modo compacto: agrupa los subárboles pequeños en un solo "
                        "ZIP (menos archivos; más rápido en discos lentos)")
    args = p.parse_args(argv)

    try:
        raiz, salida = rutas_validadas(args.carpeta, args.salida)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    opts = Opciones(nivel=args.nivel, max_dirs=args.max_dirs,
                    preguntar_cada=args.preguntar_cada, verificar=args.verificar,
                    limpiar=args.limpiar, reiniciar=args.reiniciar,
                    seguir_enlaces=args.seguir_enlaces,
                    omitir_ocultos=args.omitir_ocultos, estricto=args.estricto,
                    detallado=not args.resumido)
    if args.compacto:
        aplicar_modo_compacto(opts)

    if args.simular:
        print(f"Origen : {raiz}")
        print(f"Salida : {salida}")
        infos, orden = explorar(raiz, opts.seguir_enlaces, opts.omitir_ocultos)
        print(f"  {len(orden)} carpetas, "
              f"{sum(len(i.archivos) for i in infos.values())} archivos, "
              f"{humano(sum(i.bytes for i in infos.values()))}")
        print("\nPlan (los hijos se comprimen antes que sus padres):")
        for rel in orden:
            etiqueta = raiz.name if rel == RAIZ else rel.as_posix()
            i = infos[rel]
            print(f"  {etiqueta:<50} {'(ZIP final)' if rel == RAIZ else ''} "
                  f"{len(i.archivos)} arch. + {len(i.subdirs)} subzip")
        print("\nSimulación: no se ha escrito nada.")
        return 0

    # Ejecución real: el arnés común instala Ctrl+C, llama a ejecutar() (que
    # registra Origen/Salida) y traduce el Resultado al código de salida.
    aviso = f"(Para pausar: Ctrl+C, o crea el archivo {salida / PAUSE_NAME})\n"
    return correr_cli(ejecutar, {"origen": raiz, "destino": salida}, opts,
                      si=args.si, antes=aviso)


if __name__ == "__main__":
    sys.exit(main())
