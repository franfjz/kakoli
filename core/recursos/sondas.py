#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""sondas — retrato técnico de la máquina donde corre kakoli (subpaquete recursos).

MÓDULO PURO de MEDICIÓN: sondas de CPU/RAM/disco/energía (biblioteca estándar
primero, psutil opcional; multiplataforma con caída elegante), el `PerfilSistema` y
el modo ligero (`bajar_prioridad`). No DECIDE nada de rendimiento: de eso se encarga
`core.recursos.politica`.

Regla de oro: cada sonda degrada a None/"desconocido"/0 sin lanzar excepción, y
"sé poco" siempre se traduce en "voy conservador".

Uso directo (imprime el perfil de esta máquina):
    python -m core.recursos [ruta]
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass


MB = 1024 * 1024


# ==========================================================================
# CPU
# ==========================================================================

def cpu_utilizables() -> int:
    """Núcleos realmente disponibles para ESTE proceso.
    En Linux respeta la afinidad y los límites de cgroups (contenedores)."""
    try:
        return max(1, len(os.sched_getaffinity(0)))   # Linux
    except AttributeError:
        return max(1, os.cpu_count() or 1)             # Windows / macOS


def cpu_logicos() -> int:
    """Hilos lógicos totales de la máquina."""
    return max(1, os.cpu_count() or 1)


def cpu_fisicos() -> int | None:
    """Núcleos físicos (sin contar hyperthreads/SMT). None si no se puede saber.

    Importa porque comprimir es CPU-bound: dos hilos en el MISMO núcleo físico
    rinden bastante menos que en dos núcleos distintos, así que el tope de hilos
    se calibra mejor con los físicos."""
    try:
        import psutil
        n = psutil.cpu_count(logical=False)
        if n:
            return int(n)
    except Exception:
        pass
    # Windows: contar relaciones RelationProcessorCore (sin dependencias).
    if os.name == "nt":
        try:
            n = _cpu_fisicos_windows()
            if n:
                return n
        except Exception:
            pass
        return None
    # Linux: pares (physical id, core id) únicos en /proc/cpuinfo.
    try:
        fisicos: set[tuple[str, str]] = set()
        paquete = core = None
        with open("/proc/cpuinfo", encoding="ascii", errors="ignore") as fh:
            for linea in fh:
                if linea.startswith("physical id"):
                    paquete = linea.split(":")[1].strip()
                elif linea.startswith("core id"):
                    core = linea.split(":")[1].strip()
                elif not linea.strip():
                    if paquete is not None and core is not None:
                        fisicos.add((paquete, core))
                    paquete = core = None
        if fisicos:
            return len(fisicos)
    except OSError:
        pass
    return None


def _cpu_fisicos_windows() -> int | None:
    """Núcleos físicos en Windows vía GetLogicalProcessorInformationEx.
    Cuenta las estructuras con relación RelationProcessorCore (una por núcleo
    físico). Devuelve None si la API falla."""
    import ctypes
    from ctypes import wintypes

    RELATION_PROCESSOR_CORE = 0
    fn = ctypes.windll.kernel32.GetLogicalProcessorInformationEx
    fn.argtypes = [ctypes.c_int, ctypes.c_void_p,
                   ctypes.POINTER(wintypes.DWORD)]
    fn.restype = wintypes.BOOL

    longitud = wintypes.DWORD(0)
    # 1ª llamada: buffer NULL -> falla y rellena la longitud necesaria.
    fn(RELATION_PROCESSOR_CORE, None, ctypes.byref(longitud))
    if longitud.value == 0:
        return None
    buf = (ctypes.c_byte * longitud.value)()
    if not fn(RELATION_PROCESSOR_CORE, buf, ctypes.byref(longitud)):
        return None

    # El buffer es una secuencia de registros de tamaño variable; cada uno
    # empieza por Relationship (DWORD) y Size (DWORD). Se avanza con Size.
    crudo = bytes(buf)
    nucleos = 0
    offset = 0
    total = longitud.value
    while offset + 8 <= total:
        relacion = int.from_bytes(crudo[offset:offset + 4], "little")
        tam = int.from_bytes(crudo[offset + 4:offset + 8], "little")
        if tam <= 0:
            break
        if relacion == RELATION_PROCESSOR_CORE:
            nucleos += 1
        offset += tam
    return nucleos or None


def _tiempos_cpu() -> tuple[int, int, int] | None:
    """(total, ocupado, propio) de CPU en unidades homogéneas, acumulados.
    total = capacidad total; ocupado = no-idle; propio = de ESTE proceso.
    Con dos muestras se calcula el % de uso (total y externo). None si no se
    puede medir. Sin dependencias: GetSystemTimes/GetProcessTimes en Windows,
    /proc/stat y /proc/self/stat en Linux."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class FT(ctypes.Structure):
                _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

            def val(ft: "FT") -> int:
                return (ft.high << 32) | ft.low

            k = ctypes.windll.kernel32
            pFT = ctypes.POINTER(FT)
            k.GetSystemTimes.argtypes = [pFT, pFT, pFT]
            k.GetProcessTimes.argtypes = [wintypes.HANDLE, pFT, pFT, pFT, pFT]
            idle, kernel, usuario = FT(), FT(), FT()
            if not k.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel),
                                    ctypes.byref(usuario)):
                return None
            total = val(kernel) + val(usuario)     # kernel ya incluye idle
            ocupado = total - val(idle)
            # Pseudo-handle del proceso actual = (HANDLE)-1 (evita truncar en 64b).
            actual = ctypes.c_void_p(-1)
            cre, fin, pk, pu = FT(), FT(), FT(), FT()
            if not k.GetProcessTimes(actual, ctypes.byref(cre), ctypes.byref(fin),
                                     ctypes.byref(pk), ctypes.byref(pu)):
                return None
            return total, ocupado, val(pk) + val(pu)
        except Exception:
            return None
    try:  # Linux
        with open("/proc/stat", encoding="ascii") as fh:
            campos = [int(x) for x in fh.readline().split()[1:]]
        total = sum(campos)
        idle = campos[3] + (campos[4] if len(campos) > 4 else 0)  # idle + iowait
        ocupado = total - idle
        with open("/proc/self/stat", encoding="ascii") as fh:
            crudo = fh.read()
        # comm puede llevar espacios/paréntesis: se corta tras el último ')'.
        resto = crudo[crudo.rfind(")") + 2:].split()
        propio = int(resto[11]) + int(resto[12])   # utime + stime
        return total, ocupado, propio
    except (OSError, ValueError, IndexError):
        return None


def muestra_carga(cpu: int, intervalo: float = 0.1) -> tuple[float | None,
                                                             float | None]:
    """Mide de una vez (carga_total_por_núcleo, carga_externa_0a1). La total es
    para el log y sale de loadavg en Linux; la externa (CPU de OTROS procesos)
    es la que dirige las decisiones. En Windows ambas salen del MISMO par de
    muestras, así que el perfil solo paga un intervalo, no dos."""
    total = None
    try:
        la1, _, _ = os.getloadavg()                    # Linux / macOS
        total = la1 / max(1, cpu)
    except (AttributeError, OSError):
        pass
    a = _tiempos_cpu()
    if a is None:
        return total, None
    time.sleep(intervalo)
    b = _tiempos_cpu()
    if b is None:
        return total, None
    d_total = b[0] - a[0]
    if d_total <= 0:
        return total, None
    if total is None:                                  # Windows: %CPU como total
        total = max(0.0, min(1.0, (b[1] - a[1]) / d_total))
    externo = max(0.0, min(1.0, (b[1] - a[1] - (b[2] - a[2])) / d_total))
    return total, externo


def medidor_carga_externa():
    """Devuelve un callable que, en cada llamada, da la fracción de CPU (0..1)
    usada por OTROS procesos desde la llamada anterior (excluye el nuestro), o
    None si no se puede medir. Es la señal correcta para el throttling: "¿el
    equipo se está ocupando con otras cosas?". La 1ª llamada devuelve None
    (aún no hay intervalo). Mantiene el estado entre llamadas (sin dormir)."""
    prev = _tiempos_cpu()

    def medir() -> float | None:
        nonlocal prev
        actual = _tiempos_cpu()
        if prev is None or actual is None:
            prev = actual
            return None
        d_total = actual[0] - prev[0]
        d_ocupado = actual[1] - prev[1]
        d_propio = actual[2] - prev[2]
        prev = actual
        if d_total <= 0:
            return None
        return max(0.0, min(1.0, (d_ocupado - d_propio) / d_total))

    return medir


# ==========================================================================
# RAM
# ==========================================================================

def _ram_psutil() -> tuple[int, int] | None:
    try:
        import psutil
    except Exception:
        return None
    vm = psutil.virtual_memory()
    return vm.total, vm.available


def _ram_linux() -> tuple[int, int] | None:
    try:
        total = disp = 0
        with open("/proc/meminfo", "r", encoding="ascii", errors="ignore") as fh:
            for linea in fh:
                campo, _, resto = linea.partition(":")
                if campo == "MemTotal":
                    total = int(resto.split()[0]) * 1024
                elif campo == "MemAvailable":
                    disp = int(resto.split()[0]) * 1024
                if total and disp:
                    break
        return (total, disp) if total else None
    except (OSError, ValueError):
        return None


def _ram_windows() -> tuple[int, int] | None:
    try:
        import ctypes

        class M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = M()
        st.dwLength = ctypes.sizeof(M)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return None
        return st.ullTotalPhys, st.ullAvailPhys
    except Exception:
        return None


def _ram_posix_total() -> tuple[int, int] | None:
    # Último recurso (p.ej. macOS sin psutil): solo total fiable;
    # estimamos "disponible" de forma prudente como la mitad del total.
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return total, total // 2
    except (AttributeError, ValueError, OSError):
        return None


def ram_total_y_disponible() -> tuple[int, int, str]:
    """(total, disponible, origen). Si nada funciona -> (0, 0, 'desconocido')."""
    for nombre, fn in (("psutil", _ram_psutil),
                       ("meminfo", _ram_linux),
                       ("winapi", _ram_windows),
                       ("estimado", _ram_posix_total)):
        r = fn()
        if r and r[0] > 0:
            return r[0], r[1], nombre
    return 0, 0, "desconocido"


def swap_total_y_usado() -> tuple[int, int]:
    """(total, usado) de swap/pagefile en bytes; (0, 0) si no se sabe.
    Si `usado` > 0 el equipo ya está paginando: está corto de RAM y hay que
    caer a secuencial pase lo que pase."""
    try:
        import psutil
        s = psutil.swap_memory()
        return int(s.total), int(s.used)
    except Exception:
        pass
    try:  # Linux: /proc/meminfo
        total = libre = None
        with open("/proc/meminfo", encoding="ascii", errors="ignore") as fh:
            for linea in fh:
                if linea.startswith("SwapTotal"):
                    total = int(linea.split()[1]) * 1024
                elif linea.startswith("SwapFree"):
                    libre = int(linea.split()[1]) * 1024
        if total is not None and libre is not None:
            return total, total - libre
    except (OSError, ValueError):
        pass
    return 0, 0


# ==========================================================================
# Disco (best-effort)
# ==========================================================================

def es_disco_lento(ruta: str) -> bool | None:
    """True=HDD, False=SSD, None=no se sabe. Fiable en Linux y en Windows."""
    if os.name == "nt":
        try:
            return _es_disco_lento_windows(ruta)
        except Exception:
            return None
    try:
        # Linux: /sys/block/<dev>/queue/rotational (1 = HDD)
        st = os.stat(ruta)
        mayor = os.major(st.st_dev)
        for base in os.listdir("/sys/block"):
            p = f"/sys/block/{base}/dev"
            if os.path.exists(p):
                with open(p) as fh:
                    if fh.read().split(":")[0] == str(mayor):
                        rot = f"/sys/block/{base}/queue/rotational"
                        with open(rot) as r:
                            return r.read().strip() == "1"
    except Exception:
        pass
    return None   # macOS: no fiable sin dependencias; se ignora.


def _es_disco_lento_windows(ruta: str) -> bool | None:
    """HDD vs SSD en Windows: pregunta al dispositivo si tiene 'seek penalty'
    (IOCTL_STORAGE_QUERY_PROPERTY / StorageDeviceSeekPenaltyProperty). True=HDD
    (rotacional), False=SSD, None si no se puede saber (p.ej. unidad de red)."""
    import ctypes
    from ctypes import wintypes

    letra = os.path.splitdrive(os.path.abspath(ruta))[0]   # p.ej. "C:"
    if not letra or len(letra) != 2 or letra[1] != ":":
        return None                                        # UNC, red, etc.
    dispositivo = "\\\\.\\" + letra                        # \\.\C:

    FILE_SHARE_RW = 0x00000001 | 0x00000002
    OPEN_EXISTING = 3
    INVALID = ctypes.c_void_p(-1).value

    CreateFileW = ctypes.windll.kernel32.CreateFileW
    CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                            wintypes.HANDLE]
    CreateFileW.restype = wintypes.HANDLE
    # Acceso 0: basta con abrir el volumen para consultar propiedades.
    h = CreateFileW(dispositivo, 0, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID:
        return None

    try:
        class STORAGE_PROPERTY_QUERY(ctypes.Structure):
            _fields_ = [("PropertyId", wintypes.DWORD),
                        ("QueryType", wintypes.DWORD),
                        ("AdditionalParameters", ctypes.c_byte * 1)]

        class DEVICE_SEEK_PENALTY_DESCRIPTOR(ctypes.Structure):
            _fields_ = [("Version", wintypes.DWORD),
                        ("Size", wintypes.DWORD),
                        ("IncursSeekPenalty", ctypes.c_byte)]

        IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
        STORAGE_DEVICE_SEEK_PENALTY = 7
        PROPERTY_STANDARD_QUERY = 0

        consulta = STORAGE_PROPERTY_QUERY()
        consulta.PropertyId = STORAGE_DEVICE_SEEK_PENALTY
        consulta.QueryType = PROPERTY_STANDARD_QUERY
        salida = DEVICE_SEEK_PENALTY_DESCRIPTOR()
        devuelto = wintypes.DWORD(0)

        DeviceIoControl = ctypes.windll.kernel32.DeviceIoControl
        DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                    ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.DWORD),
                                    ctypes.c_void_p]
        DeviceIoControl.restype = wintypes.BOOL
        ok = DeviceIoControl(h, IOCTL_STORAGE_QUERY_PROPERTY,
                             ctypes.byref(consulta), ctypes.sizeof(consulta),
                             ctypes.byref(salida), ctypes.sizeof(salida),
                             ctypes.byref(devuelto), None)
        if not ok:
            return None
        return bool(salida.IncursSeekPenalty)
    finally:
        ctypes.windll.kernel32.CloseHandle(h)


def espacio_libre(ruta: str) -> int:
    """Bytes libres en el volumen de `ruta` (0 si no se puede consultar)."""
    try:
        return shutil.disk_usage(ruta).free
    except OSError:
        return 0


def mismo_volumen(a: str, b: str) -> bool | None:
    """¿`a` y `b` en el mismo dispositivo? En HDD, leer del origen y escribir el
    ZIP en el MISMO disco a la vez castiga (saltos de cabezal)."""
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return None


def tipo_unidad(ruta: str) -> str:
    """'local' | 'red' | 'extraible' | 'desconocido'. Una unidad de red o un USB
    piden menos hilos y buffers distintos."""
    try:
        if os.name == "nt":
            import ctypes
            raiz = os.path.splitdrive(os.path.abspath(ruta))[0] + "\\"
            t = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(raiz))
            # 2=extraible 3=fijo 4=red 5=CD 6=RAMdisk
            return {2: "extraible", 3: "local", 4: "red",
                    5: "extraible", 6: "local"}.get(t, "desconocido")
        # POSIX: el punto de montaje más específico que contiene la ruta.
        objetivo = os.path.abspath(ruta)
        mejor_punto = mejor_fs = ""
        with open("/proc/mounts", encoding="utf-8", errors="ignore") as fh:
            for linea in fh:
                partes = linea.split()
                if len(partes) < 3:
                    continue
                punto, fstipo = partes[1], partes[2]
                if objetivo.startswith(punto) and len(punto) >= len(mejor_punto):
                    mejor_punto, mejor_fs = punto, fstipo
        if mejor_fs in ("nfs", "nfs4", "cifs", "smbfs", "smb3", "fuse.sshfs"):
            return "red"
        return "local" if mejor_fs else "desconocido"
    except Exception:
        return "desconocido"


# ==========================================================================
# Energía y arquitectura
# ==========================================================================

def estado_energia() -> str:
    """'enchufado' | 'bateria' | 'desconocido'. Con batería conviene ser más
    suave (menos hilos, prioridad baja) para no fundirla ni calentar."""
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return "enchufado"          # sin batería -> sobremesa/enchufado
        return "enchufado" if b.power_plugged else "bateria"
    except Exception:
        pass
    try:
        if os.name == "nt":
            import ctypes

            class SPS(ctypes.Structure):
                _fields_ = [("ACLineStatus", ctypes.c_ubyte),
                            ("BatteryFlag", ctypes.c_ubyte),
                            ("BatteryLifePercent", ctypes.c_ubyte),
                            ("SystemStatusFlag", ctypes.c_ubyte),
                            ("BatteryLifeTime", ctypes.c_ulong),
                            ("BatteryFullLifeTime", ctypes.c_ulong)]

            sps = SPS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                if sps.ACLineStatus == 1:
                    return "enchufado"
                if sps.ACLineStatus == 0:
                    return "bateria"
    except Exception:
        pass
    return "desconocido"


def proceso_64bit() -> bool:
    """False si el intérprete es de 32 bits (espacio de direcciones ~2-4 GB)."""
    return sys.maxsize > 2 ** 32


# ==========================================================================
# Modo ligero (buen ciudadano del sistema)
# ==========================================================================

_prioridad_bajada = False


def bajar_prioridad() -> None:
    """Que el equipo siga usable mientras trabajamos. Idempotente: en POSIX
    os.nice() acumula, así que solo se baja una vez por proceso."""
    global _prioridad_bajada
    if _prioridad_bajada:
        return
    try:
        if os.name == "posix":
            os.nice(10)                                   # Linux/macOS
        else:
            import ctypes
            BELOW_NORMAL = 0x00004000
            h = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetPriorityClass(h, BELOW_NORMAL)
        _prioridad_bajada = True
    except Exception:
        pass


# ==========================================================================
# Perfil
# ==========================================================================

@dataclass(frozen=True)
class PerfilSistema:
    cpu: int                     # núcleos usables por ESTE proceso
    cpu_logicos: int
    cpu_fisicos: int | None
    ram_total: int
    ram_disponible: int
    origen_ram: str
    swap_total: int
    swap_usado: int
    disco_lento: bool | None
    disco_libre: int
    mismo_volumen: bool | None   # origen vs destino (None si no aplica)
    tipo_unidad: str             # local | red | extraible | desconocido
    carga: float | None          # carga total por núcleo (None si no se sabe)
    energia: str                 # enchufado | bateria | desconocido
    proceso_64bit: bool
    carga_externa: float | None = None  # CPU 0..1 de OTROS procesos (decisiones)


def perfil(ruta_trabajo: str = ".",
           ruta_origen: str | None = None) -> PerfilSistema:
    """Retrato técnico de la máquina. `ruta_trabajo` = donde se escribe (la
    salida); `ruta_origen` = de dónde se lee, para saber si comparten disco."""
    cpu = cpu_utilizables()
    total, disp, origen = ram_total_y_disponible()
    sw_total, sw_usado = swap_total_y_usado()
    mismo = (mismo_volumen(ruta_origen, ruta_trabajo)
             if ruta_origen else None)
    carga, carga_ext = muestra_carga(cpu)   # total (log) + externa (decisiones)
    return PerfilSistema(
        cpu=cpu,
        cpu_logicos=cpu_logicos(),
        cpu_fisicos=cpu_fisicos(),
        ram_total=total,
        ram_disponible=disp,
        origen_ram=origen,
        swap_total=sw_total,
        swap_usado=sw_usado,
        disco_lento=es_disco_lento(ruta_trabajo),
        disco_libre=espacio_libre(ruta_trabajo),
        mismo_volumen=mismo,
        tipo_unidad=tipo_unidad(ruta_trabajo),
        carga=carga,
        carga_externa=carga_ext,
        energia=estado_energia(),
        proceso_64bit=proceso_64bit(),
    )


def resumen(p: "PerfilSistema") -> str:
    """Una línea legible del perfil, para el log de arranque (transparencia)."""
    def gb(n: int) -> str:
        return f"{n / (1024 ** 3):.1f} GB"

    disco = ("HDD" if p.disco_lento else
             "SSD" if p.disco_lento is False else "disco ?")
    partes = [f"{p.cpu} núcleos usables"]
    if p.cpu_fisicos:
        partes.append(f"{p.cpu_fisicos} físicos")
    partes.append(f"{gb(p.ram_disponible)} libres de {gb(p.ram_total)}")
    if p.swap_usado:
        partes.append(f"swap en uso {gb(p.swap_usado)}")
    partes.append(f"{disco}/{p.tipo_unidad}")
    if p.carga is not None:
        partes.append(f"carga {p.carga:.2f}")
    if p.energia == "bateria":
        partes.append("batería")
    return ", ".join(partes)


# ==========================================================================
# Política de hilos y auto-cálculo (Fase 2) — COMÚN a todas las tareas
# ==========================================================================


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ruta = (argv or sys.argv[1:] or ["."])[0]
    p = perfil(ruta, ruta)
    print(f"Perfil de la máquina (ruta analizada: {os.path.abspath(ruta)}):")
    print(f"  CPU            : {p.cpu} usables / {p.cpu_logicos} lógicos"
          + (f" / {p.cpu_fisicos} físicos" if p.cpu_fisicos else " / físicos ?"))
    print(f"  RAM            : {p.ram_disponible / (1024**3):.2f} GB libres de "
          f"{p.ram_total / (1024**3):.2f} GB (origen: {p.origen_ram})")
    print(f"  Swap           : {p.swap_usado / (1024**3):.2f} GB usados de "
          f"{p.swap_total / (1024**3):.2f} GB")
    disco = ("HDD" if p.disco_lento else
             "SSD" if p.disco_lento is False else "desconocido")
    print(f"  Disco          : {disco}, {p.disco_libre / (1024**3):.1f} GB libres, "
          f"unidad {p.tipo_unidad}, mismo volumen origen/destino: {p.mismo_volumen}")
    ce = f"{p.carga_externa:.2f}" if p.carga_externa is not None else "desconocida"
    print(f"  Carga total    : {p.carga if p.carga is not None else 'desconocida'}")
    print(f"  Carga externa  : {ce}  (otros procesos; dirige las decisiones)")
    print(f"  Energía        : {p.energia}")
    print(f"  Proceso        : {'64' if p.proceso_64bit else '32'}-bit")
    print()
    print(f"resumen(): {resumen(p)}")
    return 0
