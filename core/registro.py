# -*- coding: utf-8 -*-
"""registro — contrato de tarea y registro de tareas (núcleo, SIN Tkinter).

La GUI (App) no conoce las tareas concretas: recibe un `Registro` construido por
la raíz de composición (kakoli.py, vía el manifiesto tasks/). Cada tarea se describe con
un `DescriptorTarea` que empaqueta su nombre, su FÁBRICA de interfaz (la clase de
pestaña, OPACA para el núcleo: aquí no se instancia ni se importa) y los tipos de
ARTEFACTO que produce/consume, con los que el registro casa el handoff entre
gemelas (p. ej. Comprimir produce "zip_anidado" y Descomprimir lo consume).

Sustituye al antiguo cableado por clases (`produce_hacia`) y a la mutación de
atributos de clase al importar el menú: aquí todo es dato inmutable y validado.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class FabricaPestana(Protocol):
    """Contrato MÍNIMO que la GUI (App) espera de la clase de pestaña de una tarea
    —la "fábrica de UI" del descriptor—. Es estructural (el núcleo NO importa
    Tkinter): solo enumera lo que App usa más allá de ser un widget. App la
    construye como `clase(master, contexto)` y luego, por cada pestaña, usa:

      - `nombre`: rótulo de la pestaña;
      - `procesar_cola()`: drenar los eventos del hilo de trabajo (bomba de la GUI);
      - `ocupada()`: ¿hay trabajo en marcha? (para el cierre y el bloqueo);
      - `pedir_cierre()`: pausar ordenadamente al cerrar la app;
      - `establecer_origen(ruta)`: recibir el origen en un handoff entre gemelas.

    El test de conformidad (tests/test_conformidad_tareas.py) verifica que la clase
    de cada descriptor cumple este contrato."""
    nombre: str

    def procesar_cola(self) -> None: ...
    def ocupada(self) -> bool: ...
    def pedir_cierre(self) -> None: ...
    def establecer_origen(self, ruta: str) -> None: ...


@dataclass(frozen=True)
class DescriptorTarea:
    """Descripción declarativa de una tarea para el registro. `clase` es la fábrica
    de interfaz (una clase de pestaña que cumple `FabricaPestana`), opaca para el
    núcleo: no se instancia aquí. `produce`/`consume` son tipos de artefacto
    (cadenas) para el handoff. `ayuda` son las secciones de Ayuda de la tarea (o
    None): la GUI las compone en orden."""
    id: str
    nombre: str
    clase: type                        # fábrica de UI (cumple FabricaPestana; opaca aquí)
    produce: str | None = None
    consume: str | None = None
    ayuda: object | None = None        # secciones de Ayuda [(título, [párrafos])]


@dataclass(frozen=True)
class Categoria:
    """Grupo de tareas relacionadas del menú de dos niveles (categoría → tareas).
    `descripcion` es la línea que se muestra en la tarjeta de la portada."""
    nombre: str
    descripcion: str
    tareas: tuple[DescriptorTarea, ...]


class Registro:
    """Conjunto ordenado de categorías con sus tareas. Valida la coherencia al
    construirse y ofrece las búsquedas que necesita la GUI (por clase, por artefacto
    consumido). No sabe de Tkinter ni instancia ninguna pestaña."""

    def __init__(self, categorias) -> None:
        self.categorias: tuple[Categoria, ...] = tuple(categorias)
        self._validar()
        descs = self.descriptores()
        self._por_clase = {d.clase: d for d in descs}
        self._por_id = {d.id: d for d in descs}
        # Índice del handoff, precomputado: artefacto CONSUMIDO -> tarea que lo consume.
        self._por_artefacto = {d.consume: d for d in descs if d.consume is not None}

    def _validar(self) -> None:
        if not self.categorias:
            raise ValueError("El registro no tiene categorías.")
        ids: set[str] = set()
        clases: set = set()
        consumidos: set[str] = set()
        for cat in self.categorias:
            if not cat.nombre:
                raise ValueError("Hay una categoría sin nombre.")
            if not cat.tareas:
                raise ValueError(f"La categoría '{cat.nombre}' no tiene tareas.")
            for d in cat.tareas:
                if not d.id:
                    raise ValueError(f"Tarea sin id en '{cat.nombre}'.")
                if d.id in ids:
                    raise ValueError(f"id de tarea duplicado: {d.id!r}")
                ids.add(d.id)
                if d.clase in clases:
                    raise ValueError(f"clase de tarea duplicada: {d.clase!r}")
                clases.add(d.clase)
                # Un artefacto lo consume UNA sola tarea (el handoff sería ambiguo).
                if d.consume is not None:
                    if d.consume in consumidos:
                        raise ValueError(
                            f"artefacto consumido por dos tareas: {d.consume!r}")
                    consumidos.add(d.consume)

    # ---------------- consultas ----------------
    def descriptores(self) -> "list[DescriptorTarea]":
        """Todas las tareas en orden de menú (lista plana)."""
        return [d for cat in self.categorias for d in cat.tareas]

    def descriptor_de(self, clase) -> "DescriptorTarea | None":
        return self._por_clase.get(clase)

    def descriptor_por_id(self, id_tarea: str) -> "DescriptorTarea | None":
        return self._por_id.get(id_tarea)

    def consumidor_de(self, artefacto: str) -> "DescriptorTarea | None":
        """Tarea que CONSUME `artefacto`, o None (índice precomputado; único por
        artefacto, garantizado en la validación)."""
        return self._por_artefacto.get(artefacto)
