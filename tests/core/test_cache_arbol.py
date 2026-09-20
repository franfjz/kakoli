# -*- coding: utf-8 -*-
"""Caracterización de core.cache_arbol: caché en disco del recorrido del árbol,
validada por firma, común a las tareas reanudables (evita re-explorar al reanudar)."""
from __future__ import annotations

import core.cache_arbol as cache_arbol
from core.cache_arbol import CacheArbol


def nolog(*_a, **_k) -> None:
    pass


# ---------------- guardar / cargar ----------------

def test_guardar_y_cargar_es_fiel(tmp_path):
    c = CacheArbol(tmp_path / "arbol.json", firma={"omitir_ocultos": False})
    c.guardar(["a", "b/c", "d"])
    assert CacheArbol(tmp_path / "arbol.json",
                      firma={"omitir_ocultos": False}).cargar() == ["a", "b/c", "d"]


def test_cargar_inexistente_devuelve_none(tmp_path):
    assert CacheArbol(tmp_path / "no_existe.json").cargar() is None


def test_cargar_con_firma_distinta_devuelve_none(tmp_path):
    ruta = tmp_path / "arbol.json"
    CacheArbol(ruta, firma={"omitir_ocultos": False}).guardar(["a"])
    # Otra firma (p. ej. el usuario cambió una opción de recorrido): no vale.
    assert CacheArbol(ruta, firma={"omitir_ocultos": True}).cargar() is None


def test_cargar_con_formato_distinto_devuelve_none(tmp_path):
    ruta = tmp_path / "arbol.json"
    from core.json_util import guardar_json
    guardar_json(ruta, {"formato": "otro/9", "firma": {}, "payload": ["a"]})
    assert CacheArbol(ruta, firma={}).cargar() is None


def test_cargar_corrupto_devuelve_none(tmp_path):
    ruta = tmp_path / "roto.json"
    ruta.write_text("{no es json", encoding="utf-8")
    assert CacheArbol(ruta).cargar() is None


def test_cargar_payload_malformado_devuelve_none(tmp_path):
    """Si el deserializador falla (payload inesperado), se trata como fallo → None."""
    ruta = tmp_path / "arbol.json"
    CacheArbol(ruta, firma={}).guardar({"orden": ["a"]})

    def deserializar(payload):
        return payload["no_existe"]          # KeyError

    assert CacheArbol(ruta, firma={}).cargar(deserializar) is None


def test_serializar_deserializar_personalizados(tmp_path):
    """Para árboles que no son JSON nativo se pasan (de)serializadores."""
    ruta = tmp_path / "arbol.json"
    c = CacheArbol(ruta, firma={})
    original = {"a", "b", "c"}               # un set no es JSON-serializable
    c.obtener(lambda: original, serializar=sorted, deserializar=set, log=nolog)
    assert CacheArbol(ruta, firma={}).cargar(deserializar=set) == original


# ---------------- obtener (load-or-explore) ----------------

def test_obtener_explora_y_cachea_la_primera_vez(tmp_path):
    ruta = tmp_path / "arbol.json"
    llamadas = {"n": 0}

    def explorar():
        llamadas["n"] += 1
        return ["a", "b"]

    res = CacheArbol(ruta, firma={}).obtener(explorar, log=nolog)
    assert res == ["a", "b"]
    assert llamadas["n"] == 1
    assert ruta.exists()                     # se dejó la caché


def test_obtener_reanuda_desde_cache_sin_reexplorar(tmp_path):
    ruta = tmp_path / "arbol.json"
    llamadas = {"n": 0}

    def explorar():
        llamadas["n"] += 1
        return ["a", "b"]

    CacheArbol(ruta, firma={"x": 1}).obtener(explorar, log=nolog)
    # Segunda vuelta (misma firma): carga del caché, NO vuelve a explorar.
    res = CacheArbol(ruta, firma={"x": 1}).obtener(explorar, log=nolog)
    assert res == ["a", "b"]
    assert llamadas["n"] == 1


def test_obtener_reiniciar_descarta_y_reexplora(tmp_path):
    ruta = tmp_path / "arbol.json"
    llamadas = {"n": 0}

    def explorar():
        llamadas["n"] += 1
        return ["a"]

    c = CacheArbol(ruta, firma={})
    c.obtener(explorar, log=nolog)
    c.obtener(explorar, reiniciar=True, log=nolog)
    assert llamadas["n"] == 2                 # reiniciar forzó re-explorar


def test_obtener_sigue_si_falla_el_guardado(tmp_path, monkeypatch):
    """Cachear es una optimización: si el guardado falla, se devuelve lo explorado."""
    def falla(*_a, **_k):
        raise OSError("disco lleno")

    monkeypatch.setattr(cache_arbol, "guardar_json", falla)
    res = CacheArbol(tmp_path / "arbol.json", firma={}).obtener(
        lambda: ["a", "b"], log=nolog)
    assert res == ["a", "b"]


def test_borrar_quita_la_cache(tmp_path):
    ruta = tmp_path / "arbol.json"
    c = CacheArbol(ruta, firma={})
    c.guardar(["a"])
    assert ruta.exists()
    c.borrar()
    assert not ruta.exists()
    c.borrar()                                # idempotente (no lanza si no existe)
