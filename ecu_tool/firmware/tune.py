# firmware/tune.py
"""Небольшие утилиты для демонстрационного «тюнинга» прошивки.

Модуль оперирует простыми параметрами в бинарном образе прошивки
симулятора:

* Ограничение оборотов двигателя (2 байта, little-endian).
* Таблица смесеобразования из 8 точек (по одной байте на точку).
* Флаг "отстрелов" — демонстрационный переключатель (1 байт).

Эти адреса выбраны условно и предназначены лишь для примера.
На реальной прошивке смещения и формат необходимо уточнять.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


# Смещения параметров внутри бинарного образа
RPM_LIMIT_OFF = 0x0100
MIX_TABLE_OFF = 0x0200
MIX_TABLE_LEN = 8
POPS_FLAG_OFF = 0x0300


@dataclass
class TuneParams:
    """Набор параметров тюнинга прошивки."""

    rpm_limit: int  # максимальные обороты
    mixture: List[int]  # условная таблица смеси (0..255)
    pops: int  # 0 или 1 — демонстрационный флаг "отстрелов"


def read_params(data: bytes) -> TuneParams:
    """Извлечь параметры тюнинга из бинарного образа."""

    rpm = int.from_bytes(data[RPM_LIMIT_OFF : RPM_LIMIT_OFF + 2], "little")
    mix = list(data[MIX_TABLE_OFF : MIX_TABLE_OFF + MIX_TABLE_LEN])
    pops = data[POPS_FLAG_OFF]
    return TuneParams(rpm_limit=rpm, mixture=mix, pops=pops)


def write_params(buf: bytearray, params: TuneParams) -> None:
    """Записать изменённые параметры обратно в образ."""

    buf[RPM_LIMIT_OFF : RPM_LIMIT_OFF + 2] = params.rpm_limit.to_bytes(2, "little")
    mix = bytes((params.mixture + [0] * MIX_TABLE_LEN)[:MIX_TABLE_LEN])
    buf[MIX_TABLE_OFF : MIX_TABLE_OFF + MIX_TABLE_LEN] = mix
    buf[POPS_FLAG_OFF] = params.pops & 0xFF


def blank_params() -> TuneParams:
    """Параметры по умолчанию (если в образе мусор)."""

    return TuneParams(rpm_limit=6000, mixture=[128] * MIX_TABLE_LEN, pops=0)

