# -*- coding: utf-8 -*-
"""Guardián de fronteras de dependencia (trinquete) — analiza por AST (sin importar)
las dependencias entre los módulos del proyecto y las contrasta con las reglas de la
arquitectura (docs/ARQUITECTURA.md), clasificando cada módulo por su ROL.

Reglas por rol de origen (destinos permitidos):
    core       -> core (y stdlib; NUNCA tkinter, gui, tareas)
    gui        -> core, gui
    manifiesto -> core, tarea, pestana, motor          (el REGISTRO cablea las tareas)
    tarea      -> core, tarea, pestana, motor          (el descriptor de una tarea)
    formato    -> core                                 (tasks/formatos/*)
    motor      -> core, formato                         (nunca OTRA tarea)
    pestana    -> core, gui, formato, SU PROPIO motor
    entrada    -> cualquiera (raíz de composición, kakoli.py)

Además: los módulos DE UNA MISMA tarea (`tasks.<t>.*`) pueden importarse entre sí
(paquete vertical: motor + sus ayudantes explorar/comprimidor/estado/… + pestana);
lo que NO se permite es importar módulos de OTRA tarea.

La línea base es VACÍA y estricta: cualquier violación falla el test.
"""
from __future__ import annotations

import ast
import os

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Línea base VACÍA: la arquitectura no admite ninguna violación de frontera.
BASELINE: set[tuple[str, str]] = set()

_ROLES_PERMITIDOS = {
    "core": {"core"},
    "gui": {"core", "gui"},
    "manifiesto": {"core", "tarea", "pestana", "motor"},
    "tarea": {"core", "tarea", "pestana", "motor"},
    "formato": {"core"},
    "motor": {"core", "formato"},
    # 'pestana' se trata aparte (su propio motor).
    "entrada": {"core", "gui", "manifiesto", "tarea", "formato", "motor",
                "pestana", "entrada"},
}


def rol_de(mod: str) -> "str | None":
    """Rol arquitectónico de un módulo por su nombre, o None si no es del proyecto."""
    if mod == "kakoli":
        return "entrada"
    if mod == "tasks":
        return "manifiesto"
    if mod.startswith("core."):
        return "core"
    if mod.startswith("gui."):
        return "gui"
    if mod.startswith("tasks.formatos"):
        return "formato"
    if mod.startswith("tasks."):
        partes = mod.split(".")
        if len(partes) == 2:            # tasks.<t> (paquete/descriptor)
            return "tarea"
        sub = partes[2]
        if sub == "pestana":
            return "pestana"
        # motor.py y sus AYUDANTES de motor (explorar, comprimidor, estado,
        # planificador, ayuda…) forman el lado 'motor' de la tarea.
        return "motor"
    return None


def _motor_propio(pestana: str) -> str:
    """Motor de la misma tarea que una pestaña: tasks.<t>.pestana -> tasks.<t>.motor."""
    return f"tasks.{pestana.split('.')[1]}.motor"


def _misma_tarea(origen: str, destino: str) -> bool:
    """¿Origen y destino son módulos de la MISMA tarea (`tasks.<t>.*`)? Los submódulos
    de una tarea forman un paquete vertical y pueden importarse entre sí."""
    a, b = origen.split("."), destino.split(".")
    return (len(a) >= 3 and len(b) >= 3 and a[0] == "tasks" and b[0] == "tasks"
            and a[1] not in ("formatos",) and a[1] == b[1])


def _modulo_de(path: str) -> str:
    rel = os.path.relpath(path, _RAIZ).replace("\\", "/")
    if rel == "kakoli.py":
        return "kakoli"
    mod = rel[:-3].replace("/", ".")
    return mod[:-9] if mod.endswith(".__init__") else mod   # tasks/__init__ -> tasks


def _analizar(path: str, mod: str) -> tuple[set[str], bool]:
    """(módulos del proyecto importados, ¿importa tkinter?)."""
    with open(path, encoding="utf-8") as f:
        arbol = ast.parse(f.read(), path)
    pkg = mod.rsplit(".", 1)[0] if "." in mod else ""
    targets: set[str] = set()
    usa_tk = False

    def anota(cand: str) -> None:
        if rol_de(cand) is not None:
            targets.add(cand)

    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "tkinter" or a.name.startswith("tkinter."):
                    usa_tk = True
                anota(a.name)
        elif isinstance(n, ast.ImportFrom):
            base = (f"{pkg}.{n.module}" if n.module else pkg) if n.level else (n.module or "")
            if base == "tkinter" or base.startswith("tkinter."):
                usa_tk = True
            for a in n.names:
                cand = f"{base}.{a.name}"
                if rol_de(cand) is not None:
                    targets.add(cand)
                else:
                    anota(base)
    return targets, usa_tk


def _recorrer():
    """Genera (modulo, path) de cada .py de producción clasificable por rol."""
    for base, _dirs, files in os.walk(_RAIZ):
        if any(x in base for x in (os.sep + ".git", ".venv", "__pycache__",
                                   os.sep + "tests", os.sep + "docs", "dist", "build")):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(base, f)
            mod = _modulo_de(path)
            if rol_de(mod) is not None:
                yield mod, path


def _violaciones() -> set[tuple[str, str]]:
    viol: set[tuple[str, str]] = set()
    for mod, path in _recorrer():
        rol = rol_de(mod)
        targets, _tk = _analizar(path, mod)
        for dst in targets:
            rdst = rol_de(dst)
            if rol == "pestana":
                ok = (rdst in ("core", "gui", "formato")
                      or dst == _motor_propio(mod) or _misma_tarea(mod, dst))
            else:
                ok = rdst in _ROLES_PERMITIDOS.get(rol, set()) or _misma_tarea(mod, dst)
            if not ok:
                viol.add((mod, dst))
    return viol


def test_sin_violaciones_nuevas():
    nuevas = _violaciones() - BASELINE
    assert not nuevas, f"Violaciones de frontera NUEVAS: {sorted(nuevas)}"


def test_baseline_no_tiene_sobrantes():
    sobrantes = BASELINE - _violaciones()
    assert not sobrantes, f"Actualiza BASELINE, ya no existen: {sorted(sobrantes)}"


def test_core_no_importa_tkinter():
    culpables = []
    for mod, path in _recorrer():
        if rol_de(mod) != "core":
            continue
        if _analizar(path, mod)[1]:
            culpables.append(mod)
    assert culpables == [], f"core importa tkinter: {culpables}"


def test_manifiesto_construye_registro_sin_mutar_clases():
    """El manifiesto (tasks) arma un Registro válido y no muta clases (no existe
    produce_hacia). El handoff se casa por tipo de artefacto en el Registro."""
    from tasks import REGISTRO
    from core.registro import Registro
    from tasks.comprimir.pestana import PestanaComprimir

    assert isinstance(REGISTRO, Registro)
    assert not hasattr(PestanaComprimir, "produce_hacia")
    assert REGISTRO.consumidor_de("zip_anidado").nombre == "Descomprimir"
