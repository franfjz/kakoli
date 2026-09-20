# -*- coding: utf-8 -*-
"""Caracterización de core.registro: DescriptorTarea/Categoria/Registro, validación
y las búsquedas que usa la GUI. Sin Tkinter (las 'clases' son objetos cualquiera)."""
from __future__ import annotations

import pytest


import core.registro as registro
Categoria = registro.Categoria
DescriptorTarea = registro.DescriptorTarea
Registro = registro.Registro


class _A: pass
class _B: pass
class _C: pass


def _reg_valido():
    return Registro([
        Categoria("Cat1", "desc1",
                  (DescriptorTarea("a", "A", _A, produce="art"),
                   DescriptorTarea("b", "B", _B, consume="art"))),
        Categoria("Cat2", "desc2",
                  (DescriptorTarea("c", "C", _C),)),
    ])


def test_descriptores_en_orden():
    reg = _reg_valido()
    assert [d.id for d in reg.descriptores()] == ["a", "b", "c"]


def test_descriptor_de_clase():
    reg = _reg_valido()
    assert reg.descriptor_de(_B).nombre == "B"
    assert reg.descriptor_de(object) is None


def test_descriptor_por_id():
    reg = _reg_valido()
    assert reg.descriptor_por_id("c").clase is _C
    assert reg.descriptor_por_id("zzz") is None


def test_consumidor_de_artefacto():
    reg = _reg_valido()
    assert reg.consumidor_de("art").id == "b"
    assert reg.consumidor_de("otro") is None


def test_validacion_sin_categorias():
    with pytest.raises(ValueError):
        Registro([])


def test_validacion_categoria_vacia():
    with pytest.raises(ValueError):
        Registro([Categoria("Vacía", "d", ())])


def test_validacion_id_duplicado():
    with pytest.raises(ValueError):
        Registro([Categoria("C", "d",
                            (DescriptorTarea("x", "A", _A),
                             DescriptorTarea("x", "B", _B)))])


def test_validacion_clase_duplicada():
    with pytest.raises(ValueError):
        Registro([Categoria("C", "d",
                            (DescriptorTarea("a", "A", _A),
                             DescriptorTarea("b", "B", _A)))])


def test_validacion_categoria_sin_nombre():
    with pytest.raises(ValueError):
        Registro([Categoria("", "d", (DescriptorTarea("a", "A", _A),))])


def test_validacion_artefacto_consumido_por_dos():
    """Dos tareas no pueden consumir el mismo artefacto (handoff ambiguo)."""
    with pytest.raises(ValueError):
        Registro([Categoria("C", "d",
                            (DescriptorTarea("a", "A", _A, consume="art"),
                             DescriptorTarea("b", "B", _B, consume="art")))])


def test_registro_real_casa_las_tres_parejas():
    """El REGISTRO real empareja produce->consume de las tres gemelas."""
    from tasks import REGISTRO
    assert REGISTRO.consumidor_de("zip_anidado").nombre == "Descomprimir"
    assert REGISTRO.consumidor_de("carpeta_combinada").nombre == "Descombinar"
    assert REGISTRO.consumidor_de("carpeta_aplanada").nombre == "Desaplanar"
