#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
bench.py — Banco de pruebas y prueba de ida y vuelta (round-trip) de kakoli.

FASE 0 del roadmap de rendimiento: la línea base medible.

Sirve para dos cosas:
  1) ROUND-TRIP: comprimir una carpeta -> descomprimir el ZIP -> comprobar que
     el árbol reconstruido es idéntico al original (nombres y contenido byte a
     byte; las fechas se comprueban con tolerancia porque el formato ZIP guarda
     la hora con resolución de 2 segundos). Es la red de seguridad: cada mejora
     de rendimiento debe seguir pasando el round-trip al 100 %.
  2) BENCHMARK: generar un árbol sintético con la forma que se quiera (ancho,
     profundo, con archivos ya comprimidos, con "polvo" de carpetas diminutas)
     y cronometrar comprimir + descomprimir, imprimiendo tiempo, MB/s, tamaño
     del ZIP y pico de memoria del proceso. Así se puede decir "antes X, ahora Y".

No optimizar a ciegas: primero se mide aquí.

Ejemplos:
    python bench.py                      # escenario rápido de humo
    python bench.py --escenario ancho    # árbol ancho (escala con Fase 4)
    python bench.py --todos              # todos los escenarios de referencia
    python bench.py --escenario mixto --verboso
    python bench.py --carpetas 500 --ancho 8 --profundidad 3 --nivel 5
    python bench.py --perfil moderno     # etiqueta + hilos (paralelo: Fase 4)
    python bench.py --conservar          # no borrar los archivos temporales
"""

from __future__ import annotations

import argparse
import hashlib
import os
import random
import shutil
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path

from tasks.aplanar import motor as maplan
from tasks.combinar import motor as mcombi
from tasks.comprimir import motor as mc
from tasks.desaplanar import motor as mdesaplan
from tasks.descombinar import motor as mdescombi
from tasks.descomprimir import motor as md
from core import recursos
from core.formato import duracion, humano

try:  # que los acentos no rompan en consolas Windows en cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


# ==========================================================================
# Pico de memoria del proceso (sin dependencias externas)
# ==========================================================================

def pico_memoria_bytes() -> int:
    """Pico de memoria residente del proceso desde que arrancó, o 0 si no se sabe."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD),
                            ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]

            # K32GetProcessMemoryInfo (kernel32) es el que funciona sin líos en
            # 64 bits; psapi.GetProcessMemoryInfo queda de reserva.
            fn = getattr(ctypes.windll.kernel32, "K32GetProcessMemoryInfo", None)
            if fn is None:
                fn = ctypes.windll.psapi.GetProcessMemoryInfo
            fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            fn.restype = wintypes.BOOL
            c = PMC()
            c.cb = ctypes.sizeof(PMC)
            h = ctypes.windll.kernel32.GetCurrentProcess()
            if fn(h, ctypes.byref(c), c.cb):
                return int(c.PeakWorkingSetSize)
        except Exception:
            return 0
        return 0
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux devuelve KiB; macOS devuelve bytes.
        return ru if sys.platform == "darwin" else ru * 1024
    except Exception:
        return 0


# ==========================================================================
# Escenarios y generación del árbol sintético
# ==========================================================================

@dataclass(frozen=True)
class Escenario:
    nombre: str
    ancho: int                  # subcarpetas por carpeta
    profundidad: int            # niveles máximos de anidamiento
    archivos_por_carpeta: int
    tam_min: int                # bytes por archivo (mínimo)
    tam_max: int                # bytes por archivo (máximo)
    frac_precomprimida: float   # 0..1 fracción de archivos ya comprimidos
    objetivo_carpetas: int      # tope de carpetas a crear
    descripcion: str = ""


ESCENARIOS: dict[str, Escenario] = {
    # Humo rápido: comprueba correctness en segundos.
    "rapido": Escenario("rapido", ancho=3, profundidad=2, archivos_por_carpeta=4,
                        tam_min=1_000, tam_max=20_000, frac_precomprimida=0.2,
                        objetivo_carpetas=15,
                        descripcion="humo rápido (correctness en segundos)"),
    # Ancho: muchas hermanas -> es donde la Fase 4 (paralelo) escalará.
    "ancho": Escenario("ancho", ancho=12, profundidad=2, archivos_por_carpeta=6,
                       tam_min=2_000, tam_max=40_000, frac_precomprimida=0.2,
                       objetivo_carpetas=120,
                       descripcion="árbol ancho y poco profundo (escala con paralelo)"),
    # Profundo y estrecho: caso peor para el paralelo (cadena de 1 hijo).
    "profundo": Escenario("profundo", ancho=1, profundidad=20,
                          archivos_por_carpeta=5, tam_min=2_000, tam_max=40_000,
                          frac_precomprimida=0.2, objetivo_carpetas=20,
                          descripcion="cadena profunda y estrecha (paralelo ~1x)"),
    # Mixto: mitad de archivos ya comprimidos (.jpg/.mp4/.zip): manda la E/S.
    "mixto": Escenario("mixto", ancho=4, profundidad=4, archivos_por_carpeta=6,
                       tam_min=1_000, tam_max=80_000, frac_precomprimida=0.5,
                       objetivo_carpetas=80,
                       descripcion="mezcla comprimible / ya-comprimido"),
    # Polvo: montones de carpetas diminutas -> es lo que ataca la Fase 5.
    "polvo": Escenario("polvo", ancho=6, profundidad=4, archivos_por_carpeta=1,
                       tam_min=200, tam_max=2_000, frac_precomprimida=0.1,
                       objetivo_carpetas=300,
                       descripcion="miles de carpetas minúsculas (agrupado, Fase 5)"),
}

# Escenarios que corre --todos, de más ligero a más pesado.
ORDEN_TODOS = ["rapido", "ancho", "profundo", "mixto", "polvo"]

COMPRIMIBLE_EXTS = (".txt", ".log", ".csv", ".json", ".xml", ".html")
PRECOMPRIMIDA_EXTS = (".jpg", ".mp4", ".zip", ".png", ".mp3")

_PALABRAS = ("lorem ipsum dolor sit amet consectetur adipiscing elit sed do "
             "eiusmod tempor incididunt ut labore et dolore magna aliqua enim "
             "ad minim veniam quis nostrud exercitation ullamco laboris").split()


def _texto_comprimible(rng: random.Random, tam: int) -> bytes:
    """Texto repetitivo: DEFLATE lo reduce de verdad (archivo 'comprimible')."""
    trozos: list[bytes] = []
    total = 0
    while total < tam:
        linea = (" ".join(rng.choice(_PALABRAS) for _ in range(12)) + "\n")
        b = linea.encode("utf-8")
        trozos.append(b)
        total += len(b)
    return b"".join(trozos)[:tam]


def _rellenar(carpeta: Path, esc: Escenario, rng: random.Random) -> None:
    for i in range(esc.archivos_por_carpeta):
        tam = rng.randint(esc.tam_min, esc.tam_max)
        if rng.random() < esc.frac_precomprimida:
            # Bytes aleatorios: incompresibles, como .jpg/.mp4/.zip reales.
            ext = rng.choice(PRECOMPRIMIDA_EXTS)
            datos = rng.randbytes(tam)
        else:
            ext = rng.choice(COMPRIMIBLE_EXTS)
            datos = _texto_comprimible(rng, tam)
        (carpeta / f"archivo_{i:03d}{ext}").write_bytes(datos)


def generar_arbol(raiz: Path, esc: Escenario, semilla: int = 12345) -> tuple[int, int, int]:
    """
    Crea el árbol sintético. Devuelve (carpetas, archivos, bytes_totales).

    Cada carpeta se rellena al crearla. Se añade una carpeta vacía a propósito
    para que el round-trip verifique que las carpetas vacías se recuperan.
    """
    rng = random.Random(semilla)
    if raiz.exists():
        shutil.rmtree(raiz)
    raiz.mkdir(parents=True)
    _rellenar(raiz, esc, rng)
    carpetas = 1
    cola: deque[tuple[Path, int]] = deque([(raiz, 0)])
    while cola and carpetas < esc.objetivo_carpetas:
        d, prof = cola.popleft()
        if prof >= esc.profundidad:
            continue
        for i in range(esc.ancho):
            if carpetas >= esc.objetivo_carpetas:
                break
            sub = d / f"n{prof + 1}_{i:02d}"
            sub.mkdir()
            _rellenar(sub, esc, rng)
            carpetas += 1
            cola.append((sub, prof + 1))

    # Carpeta vacía deliberada (caso frágil del round-trip).
    (raiz / "carpeta_vacia").mkdir()
    carpetas += 1

    archivos = bytes_tot = 0
    for dirpath, _dn, filenames in os.walk(raiz):
        for f in filenames:
            archivos += 1
            bytes_tot += (Path(dirpath) / f).stat().st_size
    return carpetas, archivos, bytes_tot


# ==========================================================================
# Firma del árbol y comparación (round-trip)
# ==========================================================================

def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def firmar_arbol(base: Path) -> dict[str, tuple]:
    """
    Recorre `base` y devuelve {ruta_relativa: firma}.
      - archivos:  ('f', tamaño, sha256, mtime)
      - carpetas:  ('d',)  (se guardan todas para comparar la estructura exacta)
    """
    reg: dict[str, tuple] = {}
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        filenames.sort()
        rel_dir = Path(dirpath).relative_to(base)
        if rel_dir != Path("."):
            reg[rel_dir.as_posix() + "/"] = ("d",)
        for nombre in filenames:
            p = Path(dirpath) / nombre
            rel = (rel_dir / nombre).as_posix() if rel_dir != Path(".") else nombre
            st = p.stat()
            reg[rel] = ("f", st.st_size, _sha256(p), st.st_mtime)
    return reg


@dataclass
class Diferencias:
    faltan: list[str]      # están en el original y no en el reconstruido
    sobran: list[str]      # están en el reconstruido y no en el original
    contenido: list[str]   # mismo nombre, distinto tamaño o contenido
    fechas: list[str]      # solo la fecha difiere (más de la tolerancia)

    @property
    def ok(self) -> bool:
        # El round-trip pasa si coinciden nombres y contenido. Las fechas son
        # un aviso (el ZIP redondea a 2 s), no un fallo.
        return not (self.faltan or self.sobran or self.contenido)


def comparar_arboles(original: Path, reconstruido: Path,
                     tolerancia_fecha: float = 2.0) -> Diferencias:
    a = firmar_arbol(original)
    b = firmar_arbol(reconstruido)
    faltan = sorted(set(a) - set(b))
    sobran = sorted(set(b) - set(a))
    contenido: list[str] = []
    fechas: list[str] = []
    for clave in sorted(a.keys() & b.keys()):
        va, vb = a[clave], b[clave]
        if va[0] != vb[0]:                       # carpeta vs archivo
            contenido.append(clave)
            continue
        if va[0] == "f":
            if va[1] != vb[1] or va[2] != vb[2]:  # tamaño o sha256
                contenido.append(clave)
            elif abs(va[3] - vb[3]) > tolerancia_fecha:
                fechas.append(clave)
    return Diferencias(faltan, sobran, contenido, fechas)


# ==========================================================================
# Cronometrado de una vuelta completa
# ==========================================================================

@dataclass
class Medida:
    escenario: str
    ok: bool
    carpetas: int
    archivos: int
    bytes_entrada: int
    bytes_zip: int
    seg_comprimir: float
    seg_descomprimir: float
    dif: Diferencias
    error: str = ""

    @property
    def ratio(self) -> float:
        return self.bytes_zip / self.bytes_entrada if self.bytes_entrada else 0.0

    @property
    def mbps_comprimir(self) -> float:
        mb = self.bytes_entrada / (1024 * 1024)
        return mb / self.seg_comprimir if self.seg_comprimir > 0 else 0.0

    @property
    def mbps_descomprimir(self) -> float:
        mb = self.bytes_entrada / (1024 * 1024)
        return mb / self.seg_descomprimir if self.seg_descomprimir > 0 else 0.0


def _logger(prefijo: str, verboso: bool):
    if verboso:
        return lambda linea: print(f"    {prefijo} {linea}")
    return lambda _linea: None


def correr_round_trip(esc: Escenario, workdir: Path, *, nivel: int, hilos: int,
                      semilla: int, verboso: bool, compacto: bool = False) -> Medida:
    origen_padre = workdir / "origen"
    raiz = origen_padre / esc.nombre        # el nombre de la carpeta = nombre del ZIP
    salida = workdir / "zips"
    destino = workdir / "reconstruido"
    for d in (salida, destino):
        if d.exists():
            shutil.rmtree(d)

    print(f"  Generando árbol '{esc.nombre}' ({esc.descripcion})...")
    carpetas, archivos, bytes_entrada = generar_arbol(raiz, esc, semilla)
    print(f"    {carpetas} carpetas, {archivos} archivos, {humano(bytes_entrada)}")

    # --- Comprimir ---
    # `hilos` se fuerza a través de la política común (0 = auto). La compresión
    # ya es paralela (Fase 4); `compacto` activa el agrupado (Fase 5).
    politica = recursos.PoliticaHilos(hilos=hilos, prioridad_baja=False)
    opts_c = mc.Opciones(nivel=nivel, limpiar=True, detallado=False,
                         politica=politica)
    if compacto:
        mc.aplicar_modo_compacto(opts_c)
    t0 = time.perf_counter()
    res_c = mc.procesar(raiz, salida, opts_c, log=_logger("[C]", verboso))
    seg_c = time.perf_counter() - t0
    if res_c.estado not in ("completado", "nada"):
        return Medida(esc.nombre, False, carpetas, archivos, bytes_entrada, 0,
                      seg_c, 0.0, Diferencias([], [], [], []),
                      error=f"comprimir devolvió '{res_c.estado}': {res_c.mensaje}")
    zip_final = salida / f"{esc.nombre}.zip"
    bytes_zip = zip_final.stat().st_size if zip_final.exists() else 0

    # --- Descomprimir (misma política de hilos que comprimir, Fase 6) ---
    opts_d = md.Opciones(detallado=False, politica=politica)
    t0 = time.perf_counter()
    res_d = md.procesar(zip_final, destino, opts_d, log=_logger("[D]", verboso))
    seg_d = time.perf_counter() - t0
    if res_d.estado not in ("completado", "nada"):
        return Medida(esc.nombre, False, carpetas, archivos, bytes_entrada,
                      bytes_zip, seg_c, seg_d, Diferencias([], [], [], []),
                      error=f"descomprimir devolvió '{res_d.estado}': {res_d.mensaje}")

    # --- Comparar (round-trip) ---
    reconstruido = destino / esc.nombre
    dif = comparar_arboles(raiz, reconstruido)
    return Medida(esc.nombre, dif.ok, carpetas, archivos, bytes_entrada,
                  bytes_zip, seg_c, seg_d, dif)


# ==========================================================================
# Round-trip de COMBINACIÓN (combinar dos árboles -> descombinar -> comparar)
# ==========================================================================

def _firma_archivos(base: Path) -> dict[str, tuple]:
    """Como firmar_arbol pero SOLO archivos (la combinación no rastrea carpetas
    vacías; su garantía es a nivel de archivo)."""
    return {k: v for k, v in firmar_arbol(base).items() if not k.endswith("/")}


def correr_merge(esc: Escenario, workdir: Path, *, hilos: int, semilla: int,
                 verboso: bool) -> bool:
    """Combina dos árboles sintéticos en el principal y luego los descombina,
    comprobando que se reconstruyen byte a byte (round-trip). Devuelve True si OK."""
    A = workdir / "principal"       # basename 'principal' -> carpeta de salida
    B = workdir / "fuente"          # basename 'fuente'
    print(f"  Generando dos árboles '{esc.nombre}' (principal + fuente)...")
    cA, aA, bA = generar_arbol(A, esc, semilla)
    cB, aB, bB = generar_arbol(B, esc, semilla + 1)
    print(f"    principal: {aA} archivos · fuente: {aB} archivos "
          f"(rutas coincidentes -> conflictos por renombrado)")
    A_ref, B_ref = workdir / "A_ref", workdir / "B_ref"
    for d in (A_ref, B_ref):
        if d.exists():
            shutil.rmtree(d)
    shutil.copytree(A, A_ref)
    shutil.copytree(B, B_ref)

    politica = recursos.PoliticaHilos(hilos=hilos, prioridad_baja=False)
    p, fs = mcombi.rutas_validadas(A, [B])
    t0 = time.perf_counter()
    rc = mcombi.procesar(p, fs, mcombi.Opciones(conflicto="renombrar",
                         politica=politica), log=_logger("[M]", verboso))
    seg_c = time.perf_counter() - t0

    out = workdir / "out"
    if out.exists():
        shutil.rmtree(out)
    c, dst = mdescombi.rutas_validadas(A, out)
    t0 = time.perf_counter()
    rd = mdescombi.procesar(c, dst, mdescombi.Opciones(politica=politica),
                            log=_logger("[U]", verboso))
    seg_d = time.perf_counter() - t0

    okA = _firma_archivos(A_ref) == _firma_archivos(out / "principal")
    okB = _firma_archivos(B_ref) == _firma_archivos(out / "fuente")
    ok = (rc.estado in ("completado", "nada") and rd.estado in ("completado", "nada")
          and okA and okB)
    marca = "OK ✓" if ok else "FALLO ✗"
    print(f"  === Merge '{esc.nombre}': round-trip {marca} ===")
    print(f"    Combinar   : {duracion(seg_c)} ({seg_c:.2f} s) · "
          f"{rc.procesadas} archivos fundidos")
    print(f"    Descombinar: {duracion(seg_d)} ({seg_d:.2f} s) · "
          f"{rd.procesadas} archivos reconstruidos")
    if not ok:
        print(f"    [!] principal reconstruido == original: {okA}; "
              f"fuente reconstruida == original: {okB}")
    return ok


def correr_flatten(esc: Escenario, workdir: Path, *, hilos: int, semilla: int,
                   verboso: bool) -> bool:
    """Aplana un árbol sintético (modo ruta) y luego lo desaplana, comprobando que
    se reconstruye byte a byte a nivel de archivo (round-trip). Devuelve True si OK.
    Nota: el generador usa nombres con '_' (nunca '-'), así que el round-trip por
    nombres es exacto; las carpetas vacías no se rastrean (garantía por archivo)."""
    A = workdir / "arbol"
    print(f"  Generando árbol '{esc.nombre}'...")
    c, a, _ = generar_arbol(A, esc, semilla)
    print(f"    {a} archivos en {c} carpetas")
    A_ref = workdir / "A_ref"
    if A_ref.exists():
        shutil.rmtree(A_ref)
    shutil.copytree(A, A_ref)

    politica = recursos.PoliticaHilos(hilos=hilos, prioridad_baja=False)
    plano = workdir / "plano"
    if plano.exists():
        shutil.rmtree(plano)
    o, d = maplan.rutas_validadas(A, plano)
    t0 = time.perf_counter()
    ra = maplan.procesar(o, d, maplan.Opciones(modo_nombre="ruta", politica=politica),
                         log=_logger("[A]", verboso))
    seg_a = time.perf_counter() - t0

    out = workdir / "out"
    if out.exists():
        shutil.rmtree(out)
    o2, d2 = mdesaplan.rutas_validadas(plano, out)
    t0 = time.perf_counter()
    rd = mdesaplan.procesar(o2, d2, mdesaplan.Opciones(politica=politica),
                            log=_logger("[D]", verboso))
    seg_d = time.perf_counter() - t0

    ok_files = _firma_archivos(A_ref) == _firma_archivos(out)
    ok = (ra.estado in ("completado", "nada") and rd.estado in ("completado", "nada")
          and ok_files)
    marca = "OK ✓" if ok else "FALLO ✗"
    print(f"  === Flatten '{esc.nombre}': round-trip {marca} ===")
    print(f"    Aplanar   : {duracion(seg_a)} ({seg_a:.2f} s) · "
          f"{ra.procesadas} archivos aplanados")
    print(f"    Desaplanar: {duracion(seg_d)} ({seg_d:.2f} s) · "
          f"{rd.procesadas} archivos reconstruidos")
    if not ok:
        print(f"    [!] árbol reconstruido == original (solo archivos): {ok_files}")
    return ok


def _pausa_tras(k: int):
    """Callback de pausa determinista (secuencial): True a partir de la (k+1)-ésima."""
    estado = {"n": 0}

    def f() -> bool:
        estado["n"] += 1
        return estado["n"] > k
    return f


def correr_reanudar(esc: Escenario, workdir: Path, *, hilos: int, semilla: int,
                    verboso: bool) -> bool:
    """Prueba de REANUDACIÓN tras cerrar (roadmap_reanudar.md): aplana la mitad y
    'cierra' (motor descartado), reanuda hasta completar; luego desaplana la mitad,
    'cierra' y reanuda; y comprueba round-trip byte a byte a nivel de archivo.
    La 1ª pasada de cada tarea es secuencial (pausa determinista a la mitad); la
    reanudación usa los `hilos` pedidos."""
    A = workdir / "arbol"
    print(f"  Generando árbol '{esc.nombre}'...")
    _, archivos, _ = generar_arbol(A, esc, semilla)
    mitad = max(1, archivos // 2)
    A_ref = workdir / "A_ref"
    if A_ref.exists():
        shutil.rmtree(A_ref)
    shutil.copytree(A, A_ref)
    pol_seq = recursos.PoliticaHilos(hilos=1, prioridad_baja=False)
    pol = recursos.PoliticaHilos(hilos=hilos, prioridad_baja=False)

    # --- Aplanar: mitad + reanudar ---
    plano = workdir / "plano"
    if plano.exists():
        shutil.rmtree(plano)
    o, d = maplan.rutas_validadas(A, plano)
    ra1 = maplan.procesar(o, d, maplan.Opciones(modo_nombre="ruta", politica=pol_seq),
                          log=_logger("[a1]", verboso), pausar=_pausa_tras(mitad))
    ra2 = maplan.procesar(o, d, maplan.Opciones(modo_nombre="ruta", politica=pol),
                          log=_logger("[a2]", verboso))

    # --- Desaplanar: mitad + reanudar ---
    out = workdir / "out"
    if out.exists():
        shutil.rmtree(out)
    o2, d2 = mdesaplan.rutas_validadas(plano, out)
    rd1 = mdesaplan.procesar(o2, d2, mdesaplan.Opciones(politica=pol_seq),
                             log=_logger("[d1]", verboso), pausar=_pausa_tras(mitad))
    rd2 = mdesaplan.procesar(o2, d2, mdesaplan.Opciones(politica=pol),
                             log=_logger("[d2]", verboso))

    reanudo = ra1.estado == "pausado" and rd1.estado == "pausado"
    completo = (ra2.estado in ("completado", "nada")
                and rd2.estado in ("completado", "nada"))
    ok_files = _firma_archivos(A_ref) == _firma_archivos(out)
    ok = reanudo and completo and ok_files
    marca = "OK ✓" if ok else "FALLO ✗"
    print(f"  === Reanudar '{esc.nombre}': {marca} ===")
    print(f"    Aplanar   : pausó a {ra1.procesadas}/{archivos} → reanudó → "
          f"{'completado' if ra2.estado == 'completado' else ra2.estado}")
    print(f"    Desaplanar: pausó a {rd1.procesadas} → reanudó → "
          f"{'completado' if rd2.estado == 'completado' else rd2.estado}")
    if not ok:
        print(f"    [!] pausó ambas: {reanudo}; completó: {completo}; "
              f"round-trip: {ok_files}")
    return ok


# ==========================================================================
# Presentación
# ==========================================================================

def imprimir_medida(m: Medida) -> None:
    print()
    marca = "OK ✓" if m.ok else "FALLO ✗"
    print(f"  === Escenario '{m.escenario}': round-trip {marca} ===")
    if m.error:
        print(f"    ERROR: {m.error}")
        return
    print(f"    Entrada        : {humano(m.bytes_entrada)} "
          f"({m.archivos} archivos en {m.carpetas} carpetas)")
    print(f"    ZIP resultante : {humano(m.bytes_zip)}  "
          f"(ratio {m.ratio * 100:.1f} % del original)")
    print(f"    Comprimir      : {duracion(m.seg_comprimir)} "
          f"({m.seg_comprimir:.2f} s, {m.mbps_comprimir:.1f} MB/s)")
    print(f"    Descomprimir   : {duracion(m.seg_descomprimir)} "
          f"({m.seg_descomprimir:.2f} s, {m.mbps_descomprimir:.1f} MB/s)")
    if not m.ok:
        d = m.dif
        if d.faltan:
            print(f"    [!] Faltan {len(d.faltan)} entradas, p.ej.: {d.faltan[:5]}")
        if d.sobran:
            print(f"    [!] Sobran {len(d.sobran)} entradas, p.ej.: {d.sobran[:5]}")
        if d.contenido:
            print(f"    [!] Difieren {len(d.contenido)} en contenido, "
                  f"p.ej.: {d.contenido[:5]}")
    elif m.dif.fechas:
        print(f"    (nota: {len(m.dif.fechas)} fechas difieren más de 2 s; "
              f"no cuenta como fallo)")


def imprimir_resumen(medidas: list[Medida], perfil: str, hilos: int) -> None:
    print()
    print("=" * 74)
    print(f" RESUMEN  (perfil: {perfil}, hilos solicitados: "
          f"{hilos if hilos else 'auto'})")
    print("=" * 74)
    cab = f"  {'escenario':<12} {'round-trip':<11} {'comprimir':>12} " \
          f"{'descomprimir':>13} {'ratio':>7}"
    print(cab)
    print("  " + "-" * 70)
    for m in medidas:
        estado = "OK" if m.ok else "FALLO"
        if m.error:
            print(f"  {m.escenario:<12} {estado:<11} {'—':>12} {'—':>13} {'—':>7}")
            continue
        print(f"  {m.escenario:<12} {estado:<11} "
              f"{m.mbps_comprimir:>8.1f} MB/s "
              f"{m.mbps_descomprimir:>9.1f} MB/s "
              f"{m.ratio * 100:>5.1f} %")
    pico = pico_memoria_bytes()
    if pico:
        print("  " + "-" * 70)
        print(f"  Pico de memoria del proceso: {humano(pico)}")
    fallos = [m for m in medidas if not m.ok]
    print()
    if fallos:
        print(f"  RESULTADO: {len(fallos)}/{len(medidas)} escenarios FALLARON "
              f"el round-trip.")
    else:
        print(f"  RESULTADO: los {len(medidas)} escenarios pasaron el round-trip.")


# ==========================================================================
# Consola
# ==========================================================================

PERFILES = {
    # P_antiguo del roadmap: se simula forzando 1 hilo (secuencial).
    "antiguo": 1,
    # P_moderno: hilos=0 = automático (el paralelo real llega en la Fase 4).
    "moderno": 0,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Banco de pruebas y round-trip de kakoli (Fase 0 del roadmap).")
    p.add_argument("--escenario", choices=sorted(ESCENARIOS), default="rapido",
                   help="escenario a ejecutar (def.: rapido)")
    p.add_argument("--todos", action="store_true",
                   help="ejecuta todos los escenarios de referencia")
    p.add_argument("--perfil", choices=sorted(PERFILES), default=None,
                   help="antiguo (1 hilo) o moderno (auto)")
    p.add_argument("--compacto", action="store_true",
                   help="modo compacto (agrupar subárboles pequeños, Fase 5)")
    p.add_argument("--merge", action="store_true",
                   help="round-trip de COMBINACIÓN (combinar+descombinar) en vez de "
                        "comprimir")
    p.add_argument("--flatten", action="store_true",
                   help="round-trip de APLANADO (aplanar+desaplanar) en vez de "
                        "comprimir")
    p.add_argument("--reanudar", action="store_true",
                   help="prueba de REANUDACIÓN: aplana/desaplana la mitad, 'cierra' y "
                        "reanuda hasta completar; comprueba round-trip")
    p.add_argument("--hilos", type=int, default=None,
                   help="fuerza el nº de hilos (0 = auto). Prevalece sobre --perfil")
    p.add_argument("--nivel", type=int, default=1, choices=range(0, 10),
                   metavar="0-9", help="nivel de compresión (def.: 1)")
    p.add_argument("--semilla", type=int, default=12345,
                   help="semilla del generador (reproducibilidad)")
    # Overrides de la forma del árbol (se aplican sobre el escenario elegido).
    p.add_argument("--carpetas", type=int, default=None, metavar="N")
    p.add_argument("--ancho", type=int, default=None, metavar="N")
    p.add_argument("--profundidad", type=int, default=None, metavar="N")
    p.add_argument("--archivos", type=int, default=None, metavar="N",
                   help="archivos por carpeta")
    p.add_argument("--conservar", action="store_true",
                   help="no borrar los archivos temporales (para inspeccionar)")
    p.add_argument("--verboso", action="store_true",
                   help="muestra los mensajes de los motores")
    args = p.parse_args(argv)

    if args.hilos is not None:
        hilos = args.hilos
        perfil = args.perfil or "personalizado"
    elif args.perfil is not None:
        hilos = PERFILES[args.perfil]
        perfil = args.perfil
    else:
        hilos = 1               # secuencial: la línea base actual del proyecto
        perfil = "base"

    nombres = ORDEN_TODOS if args.todos else [args.escenario]
    escenarios = [ESCENARIOS[n] for n in nombres]

    # Overrides manuales (solo tienen sentido con un único escenario).
    if not args.todos:
        e = escenarios[0]
        cambios = {}
        if args.carpetas is not None:
            cambios["objetivo_carpetas"] = args.carpetas
        if args.ancho is not None:
            cambios["ancho"] = args.ancho
        if args.profundidad is not None:
            cambios["profundidad"] = args.profundidad
        if args.archivos is not None:
            cambios["archivos_por_carpeta"] = args.archivos
        if cambios:
            escenarios[0] = replace(e, **cambios)

    print("=" * 74)
    print(" bench.py — línea base medible (Fase 0)")
    print(f" perfil={perfil}  hilos={hilos if hilos else 'auto'}  "
          f"nivel={args.nivel}  semilla={args.semilla}")
    if hilos != 1:
        print(" (nota: la compresión ya es paralela (Fase 4); la descompresión")
        print("  sigue secuencial hasta la Fase 6)")
    print("=" * 74)

    base_tmp = Path(tempfile.mkdtemp(prefix="kakoli_bench_"))
    medidas: list[Medida] = []
    try:
        if args.merge:                       # round-trip de COMBINACIÓN
            oks = []
            for esc in escenarios:
                workdir = base_tmp / esc.nombre
                workdir.mkdir(parents=True, exist_ok=True)
                print()
                oks.append(correr_merge(esc, workdir, hilos=hilos,
                                        semilla=args.semilla, verboso=args.verboso))
            print()
            fallos = oks.count(False)
            print(f"  RESULTADO: {'todos' if not fallos else str(len(oks)-fallos)}"
                  f"/{len(oks)} escenarios de merge pasaron el round-trip.")
            return 0 if not fallos else 1
        if args.flatten:                     # round-trip de APLANADO
            oks = []
            for esc in escenarios:
                workdir = base_tmp / esc.nombre
                workdir.mkdir(parents=True, exist_ok=True)
                print()
                oks.append(correr_flatten(esc, workdir, hilos=hilos,
                                          semilla=args.semilla, verboso=args.verboso))
            print()
            fallos = oks.count(False)
            print(f"  RESULTADO: {'todos' if not fallos else str(len(oks)-fallos)}"
                  f"/{len(oks)} escenarios de aplanado pasaron el round-trip.")
            return 0 if not fallos else 1
        if args.reanudar:                    # prueba de REANUDACIÓN
            oks = []
            for esc in escenarios:
                workdir = base_tmp / esc.nombre
                workdir.mkdir(parents=True, exist_ok=True)
                print()
                oks.append(correr_reanudar(esc, workdir, hilos=hilos,
                                           semilla=args.semilla, verboso=args.verboso))
            print()
            fallos = oks.count(False)
            print(f"  RESULTADO: {'todos' if not fallos else str(len(oks)-fallos)}"
                  f"/{len(oks)} escenarios de reanudación pasaron.")
            return 0 if not fallos else 1
        for esc in escenarios:
            workdir = base_tmp / esc.nombre
            workdir.mkdir(parents=True, exist_ok=True)
            m = correr_round_trip(esc, workdir, nivel=args.nivel, hilos=hilos,
                                  semilla=args.semilla, verboso=args.verboso,
                                  compacto=args.compacto)
            medidas.append(m)
            imprimir_medida(m)
        imprimir_resumen(medidas, perfil, hilos)
    finally:
        if args.conservar:
            print(f"\n  Archivos temporales conservados en: {base_tmp}")
        else:
            shutil.rmtree(base_tmp, ignore_errors=True)

    return 0 if all(m.ok for m in medidas) else 1


if __name__ == "__main__":
    sys.exit(main())
