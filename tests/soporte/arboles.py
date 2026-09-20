# -*- coding: utf-8 -*-
"""arboles — utilidades para crear, firmar y comparar árboles de directorios en
los tests de motores y de pares (round-trip). Solo biblioteca estándar.

Deterministas (semilla fija) para que un round-trip sea reproducible. En la Fase 1
se ampliarán/alinearán con los escenarios de `bench.py` (rapido/ancho/profundo/
mixto/polvo); aquí queda la base mínima que ya permite verificar identidad.
"""
from __future__ import annotations

import hashlib
import os
import random
from pathlib import Path


def crear_arbol(base: Path, *, semilla: int = 12345, dirs: int = 4,
                archivos_por_dir: int = 3, profundidad: int = 2,
                vacios: bool = True) -> Path:
    """Crea un árbol de directorios determinista bajo `base` (que se crea).
    Devuelve `base`. Con `vacios`, añade una subcarpeta vacía (caso límite del
    round-trip). El contenido es texto comprimible con algo de ruido."""
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    rng = random.Random(semilla)

    def _rellenar(carpeta: Path, nivel: int) -> None:
        for i in range(archivos_por_dir):
            datos = _texto(rng, 200 + rng.randint(0, 800))
            (carpeta / f"a{nivel}_{i}.txt").write_bytes(datos)
        if nivel < profundidad:
            for d in range(dirs):
                sub = carpeta / f"n{nivel}_{d}"
                sub.mkdir(exist_ok=True)
                _rellenar(sub, nivel + 1)

    _rellenar(base, 0)
    if vacios:
        (base / "vacia").mkdir(exist_ok=True)
    return base


def _texto(rng: random.Random, tam: int) -> bytes:
    palabras = [b"kakoli", b"zip", b"arbol", b"dato", b"prueba", b"nivel"]
    trozos, total = [], 0
    while total < tam:
        p = rng.choice(palabras) + b" "
        trozos.append(p)
        total += len(p)
    return b"".join(trozos)[:tam]


def firmar(base: Path) -> dict[str, tuple[int, str]]:
    """Firma del árbol: ruta relativa (posix) -> (tamaño, sha256) de cada archivo,
    y (-1, "") por cada carpeta (incluidas las vacías, que el round-trip debe
    preservar). Sin mtime: el ZIP redondea a 2 s (lo validan los tests de par con
    tolerancia)."""
    base = Path(base)
    firma: dict[str, tuple[int, str]] = {}
    for dirpath, dirnames, filenames in os.walk(base):
        d = Path(dirpath)
        for nombre in dirnames:
            rel = (d / nombre).relative_to(base).as_posix()
            firma[rel + "/"] = (-1, "")
        for nombre in filenames:
            ruta = d / nombre
            rel = ruta.relative_to(base).as_posix()
            firma[rel] = (ruta.stat().st_size, _sha256(ruta))
    return firma


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 16), b""):
            h.update(bloque)
    return h.hexdigest()


def comparar(a: Path, b: Path) -> list[str]:
    """Diferencias entre dos árboles por su firma. Lista vacía = idénticos."""
    fa, fb = firmar(a), firmar(b)
    difs: list[str] = []
    for rel in sorted(set(fa) - set(fb)):
        difs.append(f"solo en A: {rel}")
    for rel in sorted(set(fb) - set(fa)):
        difs.append(f"solo en B: {rel}")
    for rel in sorted(set(fa) & set(fb)):
        if fa[rel] != fb[rel]:
            difs.append(f"difiere: {rel} ({fa[rel]} != {fb[rel]})")
    return difs
