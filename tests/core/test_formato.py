# -*- coding: utf-8 -*-
"""Caracterización de core.formato: tamaños legibles y duraciones."""
from __future__ import annotations

import pytest


import core.formato as formato


@pytest.mark.parametrize("n, esperado", [
    (0, "0 B"),
    (512, "512 B"),
    (1023, "1023 B"),
    (1024, "1.00 KB"),
    (1536, "1.50 KB"),
    (1024 * 1024, "1.00 MB"),
    (1024 ** 3, "1.00 GB"),
])
def test_humano(n, esperado):
    assert formato.humano(n) == esperado


@pytest.mark.parametrize("seg, esperado", [
    (0, "0s"),
    (5, "5s"),
    (65, "1m 05s"),
    (3661, "1h 01m"),
])
def test_duracion(seg, esperado):
    assert formato.duracion(seg) == esperado


def test_duracion_negativa_es_cero():
    assert formato.duracion(-10) == "0s"
