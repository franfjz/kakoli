# -*- coding: utf-8 -*-
"""pestana — la interfaz de la tarea Comprimir."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from tasks.comprimir import motor as mcomp
from gui.pestana_base import PestanaBase


class PestanaComprimir(PestanaBase):
    nombre = "Comprimir"
    MOTOR = mcomp
    produce = "zip_anidado"             # genera un .zip anidado (lo consume Descomprimir)
    etiqueta_origen = "Carpeta principal:"
    etiqueta_destino = "Carpeta de salida:"
    titulo_dialogo = "Elige la carpeta a comprimir"
    texto_inicio = "Comprimir"

    def _opciones(self) -> None:
        # Por defecto ACTIVADOS: borrar intermedios y verificar al reanudar.
        self.v_compacto = tk.BooleanVar(value=False)   # modo compacto (solo Comprimir)
        self.v_limpiar = tk.BooleanVar(value=True)
        self.v_verificar = tk.BooleanVar(value=True)
        self.v_ocultos = tk.BooleanVar(value=False)
        self.v_preset = tk.StringVar(value=mcomp.PRESETS[0][0])

        self._seccion("Opciones de compresión")
        self._combo(self.v_preset, "Compresión:", [n for n, _ in mcomp.PRESETS],
                    "Nivel de compresión: ‘Rápido’ es lo normal; ‘Máximo’ reduce "
                    "más pero tarda mucho más. Los archivos ya comprimidos (fotos, "
                    "vídeos, .zip) se guardan sin recomprimir.",
                    detalle="El nivel afecta al esfuerzo de DEFLATE (0–9). Entre "
                    "‘Rápido’ y ‘Máximo’ el tamaño suele bajar poco (a menudo <5 %) "
                    "pero el tiempo se multiplica. En discos lentos el cuello de "
                    "botella es el disco, no la CPU: ‘Rápido’ rinde mejor. Los "
                    "formatos ya comprimidos se almacenan (método STORE) para no "
                    "malgastar CPU inflándolos.")
        self._check(self.v_compacto, "Modo compacto (juntar carpetas pequeñas)",
                    "Junta las carpetas pequeñas en un solo ZIP: más rápido en "
                    "discos lentos. Cambia la estructura del resultado (no podrás "
                    "sacar una subcarpeta suelta).",
                    detalle="Sin modo compacto se crea un .zip por subcarpeta "
                    "(estructura anidada, reversible carpeta a carpeta). Compacto "
                    "agrupa las ramas pequeñas en menos ZIPs: muchos menos ficheros "
                    "que abrir y cerrar (clave en HDD y en carpetas con miles de "
                    "subdirectorios diminutos). A cambio, el resultado ya no permite "
                    "extraer una subcarpeta concreta por separado.")

        self._seccion("Filtros")
        self._check(self.v_ocultos, "Omitir ocultos",
                    "Excluir archivos del sistema o invisibles (los que empiezan "
                    "por ‘.’). No se incluirán en el resultado.",
                    detalle="Se consideran ocultos los nombres que empiezan por ‘.’ "
                    "(.git, .DS_Store, .env…) y, en Windows, los que llevan el "
                    "atributo oculto (desktop.ini, Thumbs.db). Útil para no arrastrar "
                    "metadatos del sistema ni control de versiones. Si comprimes para "
                    "hacer copia de seguridad EXACTA, déjalo desmarcado.")

        self._seccion("Manejo de archivos")
        self._check(self.v_verificar, "Verificar ZIP ya hechos al reanudar",
                    "Al reanudar, comprueba los ZIP ya creados y rehace los dañados. "
                    "Más seguro, algo más lento. Sin efecto si no hay nada previo.",
                    detalle="Solo actúa al CONTINUAR una compresión interrumpida: "
                    "revisa el CRC de cada ZIP ya existente y rehace los que estén "
                    "corruptos o a medias (p. ej. por un apagón). Cuesta una lectura "
                    "extra de lo ya hecho; en una compresión desde cero no hace nada.")
        self._check(self.v_limpiar, "Borrar ZIP intermedios al integrarlos",
                    "Deja solo el ZIP final borrando los intermedios según se "
                    "integran en su carpeta padre. Menos espacio temporal.",
                    detalle="La compresión anidada crea un ZIP por carpeta y luego "
                    "los va metiendo en el de su carpeta padre. Con esto, cada "
                    "intermedio se borra en cuanto se integra, así el pico de espacio "
                    "en disco es mucho menor. Desmárcalo solo si quieres conservar los "
                    "ZIP de cada nivel por separado (ocupan casi el doble).")

    def _nivel(self) -> int:
        for nombre, nivel in mcomp.PRESETS:
            if nombre == self.v_preset.get():
                return nivel
        return mcomp.Opciones.nivel

    def _destino_automatico(self, origen: str) -> str:
        if not origen:
            return ""
        p = Path(origen).expanduser()
        return str(p.parent / f"{p.name}_zips") if p.name else ""

    def _validar(self) -> dict:
        origen = self.valor("origen")
        if not origen:
            raise ValueError("Elige la carpeta que quieres comprimir.")
        destino = self.valor("destino")
        raiz, salida = mcomp.rutas_validadas(Path(origen),
                                             Path(destino) if destino else None)
        # Las variables Tk se leen aquí, en el hilo principal (Tk no es
        # seguro entre hilos); el motor recibe ya el objeto Opciones.
        opts = mcomp.Opciones(nivel=self._nivel(),
                              limpiar=self.v_limpiar.get(),
                              verificar=self.v_verificar.get(),
                              omitir_ocultos=self.v_ocultos.get(),
                              detallado=self._detallado(),
                              politica=self._politica())
        if self.v_compacto.get():
            mcomp.aplicar_modo_compacto(opts)
        return {"entradas": {"origen": raiz, "destino": salida}, "opts": opts}

    # El remate final (ruta del ZIP en consola, botón "Abrir carpeta" y el paso a
    # Descomprimir por handoff) es común a todas las tareas: lo hace PestanaBase; esta
    # pestaña ya no necesita _al_terminar.

