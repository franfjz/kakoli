# -*- coding: utf-8 -*-
"""Mapeo por pestaña: fijar las variables Tk -> `_validar()` -> Opciones esperadas
y los ValueError. Es la frontera GUI -> motor; estos tests la congelan."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _dir(tmp_path, nombre):
    d = tmp_path / nombre
    d.mkdir()
    (d / "a.txt").write_text("x")
    return d


def test_comprimir_mapea_opciones(app, tmp_path):
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    pes.v_origen.set(str(_dir(tmp_path, "datos")))     # el destino se autocompleta
    datos = pes._validar()
    assert set(datos["entradas"]) == {"origen", "destino"}
    o = datos["opts"]
    assert o.nivel == 1 and o.limpiar is True and o.verificar is True
    assert o.omitir_ocultos is False


def test_comprimir_modo_compacto(app, tmp_path):
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    pes.v_origen.set(str(_dir(tmp_path, "datos")))
    pes.v_compacto.set(True)
    o = pes._validar()["opts"]
    assert o.agrupar_mb > 0                             # compacto activado


def test_comprimir_sin_origen_falla(app):
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    pes.v_origen.set("")
    with pytest.raises(ValueError):
        pes._validar()


def test_destino_automatico_comprimir(app, tmp_path):
    from tasks.comprimir.pestana import PestanaComprimir
    pes = app.pestana(PestanaComprimir)
    pes.v_origen.set(str(_dir(tmp_path, "datos")))
    assert pes.v_destino.get().endswith("_zips")


def test_descomprimir_mapea_opciones(app, tmp_path):
    import zipfile
    from tasks.descomprimir.pestana import PestanaDescomprimir
    z = tmp_path / "carpeta.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("dentro.txt", "x")
    pes = app.pestana(PestanaDescomprimir)
    pes.v_origen.set(str(z))
    datos = pes._validar()
    assert set(datos["entradas"]) == {"origen", "destino"}
    assert datos["opts"].verificar is False


def _poner_lista(pes, *rutas):
    """Escribe rutas (una por línea) en el campo 'lista' de origenes."""
    txt = pes._widgets_lista["origenes"]
    txt.delete("1.0", "end")
    txt.insert("1.0", "\n".join(str(r) for r in rutas) + "\n")


def test_eliminar_sin_confirmar_falla(app, tmp_path):
    from tasks.eliminar.pestana import PestanaEliminar
    pes = app.pestana(PestanaEliminar)
    _poner_lista(pes, _dir(tmp_path, "victima"))
    pes.v_simular.set(False)
    pes.v_confirmo.set(False)
    with pytest.raises(ValueError):
        pes._validar()


def test_eliminar_simular_mapea(app, tmp_path):
    from tasks.eliminar.pestana import PestanaEliminar
    pes = app.pestana(PestanaEliminar)
    _poner_lista(pes, _dir(tmp_path, "victima"))
    pes.v_simular.set(True)
    datos = pes._validar()
    assert datos["entradas"].keys() == {"origenes"}
    assert len(datos["entradas"]["origenes"]) == 1
    assert datos["opts"].simular is True


def test_eliminar_varias_carpetas_en_orden(app, tmp_path):
    from tasks.eliminar.pestana import PestanaEliminar
    pes = app.pestana(PestanaEliminar)
    a, b, c = (_dir(tmp_path, n) for n in ("a", "b", "c"))
    _poner_lista(pes, a, b, c)
    pes.v_simular.set(True)
    origenes = pes._validar()["entradas"]["origenes"]
    assert [p.name for p in origenes] == ["a", "b", "c"]      # respeta el orden


def test_renombrar_sin_operacion_falla(app, tmp_path):
    from tasks.renombrar.pestana import PestanaRenombrar
    pes = app.pestana(PestanaRenombrar)
    _poner_lista(pes, _dir(tmp_path, "carpeta"))
    with pytest.raises(ValueError):
        pes._validar()


def test_renombrar_mapea(app, tmp_path):
    from tasks.renombrar.pestana import PestanaRenombrar
    pes = app.pestana(PestanaRenombrar)
    _poner_lista(pes, _dir(tmp_path, "carpeta"))
    pes.v_prefijo.set("p_")
    datos = pes._validar()
    assert datos["entradas"].keys() == {"origenes"}
    assert datos["opts"].prefijo == "p_"


def test_combinar_mapea(app, tmp_path):
    from tasks.combinar.pestana import PestanaCombinar
    pes = app.pestana(PestanaCombinar)
    pes.vars_entrada["principal"].set(str(tmp_path / "principal"))
    # Las fuentes van todas por el campo 'lista' (una ruta por línea).
    txt = pes._widgets_lista["mas"]
    txt.delete("1.0", "end")
    txt.insert("1.0", str(_dir(tmp_path, "fuente")) + "\n")
    datos = pes._validar()
    assert set(datos["entradas"]) == {"principal", "fuentes"}
    assert len(datos["entradas"]["fuentes"]) == 1


def test_descombinar_sin_indice_falla(app, tmp_path):
    from tasks.descombinar.pestana import PestanaDescombinar
    pes = app.pestana(PestanaDescombinar)
    pes.v_origen.set(str(_dir(tmp_path, "sin_indice")))
    with pytest.raises(ValueError):
        pes._validar()


def test_aplanar_mapea(app, tmp_path):
    from tasks.aplanar.pestana import PestanaAplanar
    pes = app.pestana(PestanaAplanar)
    pes.v_origen.set(str(_dir(tmp_path, "arbol")))
    o = pes._validar()["opts"]
    assert o.modo_nombre == "ruta"


def test_desaplanar_mapea(app, tmp_path):
    from tasks.desaplanar.pestana import PestanaDesaplanar
    pes = app.pestana(PestanaDesaplanar)
    pes.v_origen.set(str(_dir(tmp_path, "aplanada")))
    o = pes._validar()["opts"]
    assert o.separador == "-"
