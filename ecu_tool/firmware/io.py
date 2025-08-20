# firmware/io.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Iterable
from .map import FLASH
from .simulate import SimECU

# ---- Транспортный протокол (каркас) ----
class MemoryBackend(Protocol):
    def read_block(self, address: int, size: int) -> bytes: ...
    def write_block(self, address: int, data: bytes) -> None: ...
    def info(self) -> dict: ...

# ---- Реализация: DEMO / Симулятор ----
@dataclass
class SimBackend:
    path: Path

    def __post_init__(self):
        self.ecu = SimECU(self.path)

    def read_block(self, address: int, size: int) -> bytes:
        return self.ecu.read(address, size)

    def write_block(self, address: int, data: bytes) -> None:
        self.ecu.write(address, data)

    def info(self) -> dict:
        return self.ecu.info()

# ---- Заглушка под реальный ЭБУ (KWP2000) ----
@dataclass
class RealBackend:
    """
    Заготовка для реального K-Line/KWP2000.
    ТУТ НЕТ обхода защит и приватных seed-key: запись отключена.
    """
    adapter: object  # транспорт (например, экземпляр ELM327)
    developer_mode: bool = False  # без этого запись запрещена

    def __post_init__(self):
        try:
            from ..ecu_transport.kwp2000 import KWP2000
        except ImportError:
            from ecu_transport.kwp2000 import KWP2000
        self.kwp = KWP2000(self.adapter)
        try:
            self.adapter.init()
            self.adapter.set_header("81 10 F1")
            self.kwp.start_session()
        except Exception:
            pass

    def read_block(self, address: int, size: int) -> bytes:
        return self.kwp.read_memory(address, size)

    def write_block(self, address: int, data: bytes) -> None:
        if not self.developer_mode:
            raise PermissionError("Запись в реальный ЭБУ выключена (безопасность). Включи developer_mode только для тестов на стенде.")
        raise NotImplementedError("WriteMemory not implemented for real backend yet.")

    def info(self) -> dict:
        return {"backend": "real_kwp2000", "warning": "write disabled", "adapter": str(self.adapter)}

    def close(self):
        try:
            self.adapter.close()
        except Exception:
            pass

# ---- Высокоуровневые операции ----
def iter_chunks(data: bytes | None, chunk_size: int) -> Iterable[bytes]:
    if not data:
        return
    for i in range(0, len(data), chunk_size):
        yield data[i:i+chunk_size]

def dump_firmware(backend: MemoryBackend, out_path: Path, chunk: int = 256) -> dict:
    out_path = Path(out_path)
    buf = bytearray()
    read_total = 0
    while read_total < FLASH.size:
        size = min(chunk, FLASH.size - read_total)
        block = backend.read_block(FLASH.start + read_total, size)
        buf.extend(block)
        read_total += size
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(buf))
    return {"bytes": read_total, "out": str(out_path), "info": backend.info()}

def flash_firmware(backend: MemoryBackend, in_path: Path, chunk: int = 256) -> dict:
    in_path = Path(in_path)
    data = in_path.read_bytes()
    if len(data) != FLASH.size:
        raise ValueError(f"Размер образа {len(data)} байт не совпадает с размером памяти {FLASH.size} байт.")
    written = 0
    for i in range(0, FLASH.size, chunk):
        part = data[i:i+chunk]
        backend.write_block(FLASH.start + i, part)
        written += len(part)
    return {"bytes": written, "source": str(in_path), "info": backend.info()}
