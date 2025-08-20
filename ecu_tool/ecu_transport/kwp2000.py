# ecu_transport/kwp2000.py
"""
Каркас KWP2000 поверх K-Line. Реализация команд здесь нарочно-пустая,
чтобы не трогать реальный ЭБУ до добавления легального SecurityAccess
и выверенных таймингов.

План команд:
- start_session(level) -> 0x10
- tester_present()     -> 0x3E
- read_ecu_id()        -> (набор 0x1A/0x1B/0x21 по спецификации конкретного блока)
- read_memory(addr, size) -> 0x23
"""

class KWP2000:
    def __init__(self, transport):
        self.t = transport  # низкоуровневый транспорт (ELM327 и др.)

    # утилита для преобразования строкового ответа ELM -> bytes
    @staticmethod
    def _parse(resp: str) -> bytes:
        tokens = resp.replace("\r", " ").replace("\n", " ").replace(">", " ").split()
        out = []
        for t in tokens:
            try:
                if len(t) == 2:
                    out.append(int(t, 16))
            except ValueError:
                continue
        return bytes(out)

    def start_session(self, level: int = 0x81):
        resp = self.t.send_raw(f"10 {level:02X}")
        data = self._parse(resp)
        if not data or data[0] != 0x50:
            raise RuntimeError(f"StartSession failed: {resp}")
        return data

    def tester_present(self):
        resp = self.t.send_raw("3E 00")
        data = self._parse(resp)
        if not data or data[0] not in (0x7E, 0xC0):
            raise RuntimeError(f"TesterPresent failed: {resp}")
        return data

    def read_ecu_id(self):
        resp = self.t.send_raw("1A 90")  # локальный идентификатор 0x90 — базовый ID
        data = self._parse(resp)
        if not data or data[0] != 0x5A:
            raise RuntimeError(f"ReadEcuId failed: {resp}")
        return data[2:]

    def read_memory(self, address: int, size: int) -> bytes:
        if not (0 < size <= 0xFF):
            raise ValueError("size must be 1..255")
        a2, a1, a0 = (address >> 16) & 0xFF, (address >> 8) & 0xFF, address & 0xFF
        resp = self.t.send_raw(f"23 {a2:02X} {a1:02X} {a0:02X} {size:02X}")
        data = self._parse(resp)
        if len(data) < 4 or data[0] != 0x63:
            raise RuntimeError(f"ReadMemory failed: {resp}")
        return data[4:]
