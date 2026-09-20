# -*- coding: utf-8 -*-
"""Persistencia de preferencias a nivel de App (Fase 2): validación de 'Hilos'
contra el equipo, mapeo id<->clase de la última tarea, restauración de la
navegación, volcado a disco y memoria de la carpeta de diálogos. El config real
está redirigido a un temporal por el fixture de sesión `_config_temporal`."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_hilos_validos_normaliza(app):
    assert app._hilos_validos("Auto") == "Auto"
    assert app._hilos_validos("abc") == "Auto"     # no numérico
    assert app._hilos_validos("0") == "Auto"       # < 1
    assert app._hilos_validos("999") == "Auto"     # por encima del máximo del equipo
    assert app._hilos_validos("1") == "1"          # 1 hilo siempre es seleccionable


def test_geometria_valida(app):
    assert app._geometria_valida("1200x800+100+50") is True
    assert app._geometria_valida("100x80+0+0") is False        # tamaño degenerado
    assert app._geometria_valida("no-es-geometria") is False
    assert app._geometria_valida(None) is False
    # Fuera de pantalla (x enorme): se descarta para no perder la ventana.
    ancho = app.winfo_screenwidth()
    assert app._geometria_valida(f"800x600+{ancho + 500}+0") is False


def test_cargar_ultimas_mapea_ids_y_descarta_desconocidos(app):
    from tasks.comprimir.pestana import PestanaComprimir
    cid = app._id_por_clase[PestanaComprimir]
    app._prefs["ultimas"] = {"Compresión": cid, "Fantasma": "no_existe"}
    out = app._cargar_ultimas()
    assert out == {"Compresión": PestanaComprimir}


def test_restaurar_navegacion_abre_la_tarea_guardada(app):
    from tasks.comprimir.pestana import PestanaComprimir
    app._prefs["abierto"] = app._id_por_clase[PestanaComprimir]
    app._restaurar_navegacion()
    assert app._tarea_actual is app.pestana(PestanaComprimir)


def test_restaurar_navegacion_ayuda(app):
    app._prefs["abierto"] = "ayuda"
    app._restaurar_navegacion()
    assert app._en_ayuda is True


def test_restaurar_navegacion_id_desconocido_va_al_menu(app):
    app._prefs["abierto"] = "tarea_que_no_existe"
    app._restaurar_navegacion()
    assert app._categoria_actual is None
    assert app._tarea_actual is None


def test_guardar_prefs_persiste_estado(app):
    from gui import preferencias
    from tasks.comprimir.pestana import PestanaComprimir
    app.v_ligero.set(False)
    app.v_detallado.set(True)
    app.v_hilos.set("Auto")
    app.mostrar(PestanaComprimir)

    app._guardar_prefs()
    guardado = preferencias.cargar()               # ruta temporal (parcheada)
    assert guardado["ligero"] is False
    assert guardado["detallado"] is True
    assert guardado["abierto"] == app._id_por_clase[PestanaComprimir]


def test_memoria_de_carpeta_de_dialogos(app, tmp_path):
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    # Una carpeta se recuerda tal cual.
    pes._recordar_carpeta(str(tmp_path))
    assert app.ultima_carpeta_dialogo() == str(tmp_path)
    # Un archivo recuerda su carpeta contenedora.
    f = tmp_path / "a.zip"
    f.write_text("x")
    pes._recordar_carpeta(str(f))
    assert app.ultima_carpeta_dialogo() == str(tmp_path)
