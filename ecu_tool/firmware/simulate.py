# firmware/simulate.py
import os
import struct
from pathlib import Path
from .map import FLASH, REGIONS

class SimECU:
    """
    Очень простой симулятор ЭБУ:
    - хранит "прошивку" в файле .bin (создаётся при первом запуске)
    - умеет читать/писать байты по адресам
    - считает примитивный CRC32 для валидации
    """
    def __init__(self, store: Path):
        self.store = Path(store)
        self.store.parent.mkdir(parents=True, exist_ok=True)
        if not self.store.exists():
            # создаём "прошивку": 0xFF + сигнатура
            image = bytearray([0xFF] * FLASH.size)
            sign = b"SIM-J72\0"
            image[0:len(sign)] = sign
            self.store.write_bytes(image)

    def read(self, addr: int, size: int) -> bytes:
        data = bytearray(self.store.read_bytes())
        end = addr + size
        if addr < 0 or end > len(data):
            raise ValueError("Read out of range")
        return bytes(data[addr:end])

    def write(self, addr: int, chunk: bytes):
        data = bytearray(self.store.read_bytes())
        end = addr + len(chunk)
        if addr < 0 or end > len(data):
            raise ValueError("Write out of range")
        data[addr:end] = chunk
        self.store.write_bytes(bytes(data))

    def crc32(self) -> int:
        import zlib
        return zlib.crc32(self.store.read_bytes()) & 0xFFFFFFFF

    def info(self) -> dict:
        return {
            "regions": [r.__dict__ for r in REGIONS],
            "size": FLASH.size,
            "crc32": f"0x{self.crc32():08X}",
            "store": str(self.store)
        }
