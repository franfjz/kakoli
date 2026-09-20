# -*- coding: utf-8 -*-
"""resultado — el tipo de resultado común a todos los motores y la señal de
cancelación (núcleo, sin Tkinter ni dominio).

Antes vivían en `core.comun`; se separaron aquí (Fase 6 de mejoras)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class EstadoResultado(str, Enum):
    """Estados posibles de un `Resultado`, como constantes con nombre en vez de
    literales sueltos. Hereda de `str`, así que un miembro es intercambiable con su
    cadena (`EstadoResultado.ERROR == "error"`): los motores pueden seguir
    construyendo `Resultado("error")` y las comparaciones antiguas siguen valiendo,
    pero el código nuevo usa las constantes y `Resultado` valida contra ellas."""
    COMPLETADO = "completado"
    PAUSADO = "pausado"
    NADA = "nada"
    CANCELADO = "cancelado"
    ERROR = "error"


ESTADOS_VALIDOS = frozenset(e.value for e in EstadoResultado)


@dataclass
class Resultado:
    """Resultado común a todos los motores. `estado` debe ser uno de
    `EstadoResultado` (se valida al construir: un typo salta en el acto)."""
    estado: str                     # uno de EstadoResultado (completado|pausado|nada|cancelado|error)
    procesadas: int = 0
    restantes: int = 0
    total: int = 0
    errores: list[str] = field(default_factory=list)
    ruta_final: Path | None = None
    mensaje: str = ""
    segundos: float = 0.0

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS_VALIDOS:
            raise ValueError(
                f"Resultado.estado inválido: {self.estado!r}. "
                f"Esperado uno de {sorted(ESTADOS_VALIDOS)}.")


class Cancelado(Exception):
    """El usuario CANCELÓ: hay que abortar la unidad en curso y DESCARTAR su fragmento
    a medias, dejando el progreso en la ÚLTIMA unidad completada (a diferencia de
    pausar, que espera a que la unidad termine). La lanza el trabajo de una unidad al
    ver `cancelar()`; el motor (secuencial) y el `Ejecutor` (paralelo) la tratan como
    PARADA LIMPIA, no como error. El `.part` de la unidad abortada se borra en el
    `except` del propio trabajo, así que el fragmento desaparece y la unidad no se
    marca como hecha en el registro reanudable."""
