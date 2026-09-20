#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""comprimidor — creación de los ZIP de Comprimir (parte del paquete).

`Comprimidor` escribe un ZIP por carpeta (o uno agrupado por subárbol en el modo
compacto), embebe los ZIP hijos y pone la marca del formato. Comprueba `cancelar()`
dentro del bucle de archivos: aborta la carpeta en curso lanzando `Cancelado` y su
`.part` se descarta."""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.formato import ahora
from core.resultado import Cancelado
from tasks.comprimir.explorar import RAIZ, InfoDir, ruta_abs
from tasks.formatos.formato_zip import MARCA_FORMATO

if TYPE_CHECKING:
    from tasks.comprimir.motor import Opciones

PARTS_NAME = "_partes"

# Extensiones que ya vienen comprimidas: se guardan sin recomprimir (más rápido).
PRECOMPRIMIDAS = frozenset({
    ".zip", ".7z", ".rar", ".gz", ".tgz", ".bz2", ".xz", ".zst", ".lz4",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".heic",
    ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac",
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v",
    ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".epub", ".jar", ".apk",
})


class Comprimidor:
    def __init__(self, raiz: Path, salida: Path, opts: Opciones,
                 log: Callable[[str], None] = print,
                 agrupados: set[Path] | None = None) -> None:
        self.raiz = raiz
        self.salida = salida
        self.partes = salida / PARTS_NAME
        self.opts = opts
        self.log = log
        self.agrupados = agrupados or set()
        self.errores: list[str] = []

    def destino(self, rel: Path) -> Path:
        if rel == RAIZ:
            return self.salida / f"{self.raiz.name}.zip"
        return self.partes / rel.parent / f"{rel.name}.zip"

    def crear(self, rel: Path, info: InfoDir,
              cancelar: "Callable[[], bool] | None" = None) -> tuple[Path, int, int]:
        cancelar = cancelar or (lambda: False)
        if rel in self.agrupados:
            return self.crear_agrupado(rel, info, cancelar)

        destino = self.destino(rel)
        destino.parent.mkdir(parents=True, exist_ok=True)
        parcial = destino.with_name(destino.name + ".part")
        parcial.unlink(missing_ok=True)
        origen = ruta_abs(self.raiz, rel)
        nombre_carpeta = self.raiz.name if rel == RAIZ else rel.name
        usados: set[str] = set()
        renombradas: dict[str, str] = {}
        entradas = 0

        try:
            with zipfile.ZipFile(parcial, "w", allowZip64=True,
                                 strict_timestamps=False) as zf:
                for nombre in info.archivos:
                    if cancelar():                # aborta la carpeta en curso;
                        raise Cancelado()         # el .part se borra en el except
                    comp = (zipfile.ZIP_STORED
                            if os.path.splitext(nombre)[1].lower() in PRECOMPRIMIDAS
                            else zipfile.ZIP_DEFLATED)
                    try:
                        zf.write(os.path.join(origen, nombre), nombre,
                                 compress_type=comp, compresslevel=self.opts.nivel)
                    except (OSError, ValueError) as e:
                        msg = f"{(rel / nombre).as_posix()}: {e}"
                        self.errores.append(msg)
                        self.log(f"[!] No se pudo añadir {msg}")
                        if self.opts.estricto:
                            raise
                        continue
                    usados.add(nombre)
                    entradas += 1

                for sub in info.subdirs:
                    hijo = self.destino(rel / sub)
                    if not hijo.exists():
                        raise FileNotFoundError(
                            f"falta el ZIP intermedio {hijo} (subdirectorio {sub})")
                    arc = f"{sub}.zip"
                    if arc in usados:
                        arc = f"{sub}.subcarpeta.zip"
                        renombradas[arc] = sub
                        self.log(f"[!] En {rel.as_posix()} ya existe un archivo "
                                 f"'{sub}.zip'; la subcarpeta se guarda como '{arc}'.")
                    zf.write(hijo, arc, compress_type=zipfile.ZIP_STORED)
                    usados.add(arc)
                    entradas += 1

                zf.comment = self.marca(nombre_carpeta, len(info.subdirs), renombradas)
        except BaseException:
            parcial.unlink(missing_ok=True)
            raise

        os.replace(parcial, destino)
        return destino, destino.stat().st_size, entradas

    def crear_agrupado(self, rel: Path, info: InfoDir,
                       cancelar: "Callable[[], bool] | None" = None
                       ) -> tuple[Path, int, int]:
        """
        MEJORA 5. Empaqueta TODO el subárbol de `rel` en un ÚNICO ZIP (modo
        compacto): cada archivo entra con su ruta relativa como nombre de entrada
        ('sub/otra/archivo.txt') y las carpetas vacías se preservan con una
        entrada de directorio ('sub/vacia/'). Lleva la marca agrupado=True.

        Se escribe en un .part y se renombra al final, igual que crear(), así que
        el ZIP resultante ocupa la misma ruta que un ZIP normal de esa carpeta y
        el padre lo embebe como sub-zip (ZIP_STORED) sin enterarse de que dentro
        va un subárbol entero. El descompresor tampoco necesita cambios: rehace
        las carpetas intermedias a partir de las rutas de las entradas.

        Ventaja: menos ZIP diminutos -> menos coste por archivo, que es lo que más
        duele en discos lentos y equipos antiguos.
        """
        cancelar = cancelar or (lambda: False)
        destino = self.destino(rel)
        destino.parent.mkdir(parents=True, exist_ok=True)
        parcial = destino.with_name(destino.name + ".part")
        parcial.unlink(missing_ok=True)
        origen = ruta_abs(self.raiz, rel)
        nombre_carpeta = self.raiz.name if rel == RAIZ else rel.name
        entradas = 0

        try:
            with zipfile.ZipFile(parcial, "w", allowZip64=True,
                                 strict_timestamps=False) as zf:
                for dirpath, dirnames, filenames in os.walk(
                        origen, followlinks=self.opts.seguir_enlaces):
                    if cancelar():                # aborta el subárbol en curso;
                        raise Cancelado()         # el .part se borra en el except
                    # Mismas reglas que la exploración normal (explorar()).
                    if not self.opts.seguir_enlaces:
                        dirnames[:] = [d for d in dirnames
                                       if not os.path.islink(os.path.join(dirpath, d))]
                    if self.opts.omitir_ocultos:
                        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                        filenames = [f for f in filenames if not f.startswith(".")]
                    dirnames.sort()
                    filenames.sort()
                    rel_dir = Path(dirpath).relative_to(origen)

                    # Carpeta vacía -> entrada de directorio para preservarla.
                    if not filenames and not dirnames and rel_dir != RAIZ:
                        zf.writestr(rel_dir.as_posix() + "/", b"")
                        entradas += 1

                    for nombre in filenames:
                        ruta = os.path.join(dirpath, nombre)
                        # Coherente con explorar(): sin seguir enlaces, se omiten
                        # los archivos que sean enlace simbólico.
                        if not self.opts.seguir_enlaces and os.path.islink(ruta):
                            continue
                        arc = (rel_dir / nombre).as_posix()
                        comp = (zipfile.ZIP_STORED
                                if os.path.splitext(nombre)[1].lower() in PRECOMPRIMIDAS
                                else zipfile.ZIP_DEFLATED)
                        try:
                            zf.write(ruta, arc, compress_type=comp,
                                     compresslevel=self.opts.nivel)
                        except (OSError, ValueError) as e:
                            msg = f"{(rel / rel_dir / nombre).as_posix()}: {e}"
                            self.errores.append(msg)
                            self.log(f"[!] No se pudo añadir {msg}")
                            if self.opts.estricto:
                                raise
                            continue
                        entradas += 1

                zf.comment = self.marca(nombre_carpeta, 0, {}, agrupado=True)
        except BaseException:
            parcial.unlink(missing_ok=True)
            raise

        os.replace(parcial, destino)
        return destino, destino.stat().st_size, entradas

    @staticmethod
    def marca(nombre: str, n_sub: int, renombradas: dict[str, str],
              agrupado: bool = False) -> bytes:
        marca = {
            "formato": MARCA_FORMATO,
            "carpeta": nombre,
            "subcarpetas": n_sub,
            "renombradas": renombradas,
            "creado": ahora(),
        }
        if agrupado:
            marca["agrupado"] = True
        crudo = json.dumps(marca, ensure_ascii=False).encode("utf-8")
        if len(crudo) > 60000:      # el comentario ZIP admite 65535 bytes
            marca.pop("renombradas")
            crudo = json.dumps(marca, ensure_ascii=False).encode("utf-8")
        return crudo

    def limpiar_hijos(self, rel: Path, info: InfoDir) -> None:
        """Borra los ZIP intermedios ya incluidos en el ZIP del padre."""
        for sub in info.subdirs:
            self.destino(rel / sub).unlink(missing_ok=True)
        carpeta = self.partes if rel == RAIZ else self.partes / rel
        try:
            if carpeta.exists() and not any(carpeta.iterdir()):
                carpeta.rmdir()
        except OSError:
            pass
