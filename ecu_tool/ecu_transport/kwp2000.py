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
        self.t = transport  # сюда потом передадим низкоуровневый K-Line

    def start_session(self, level: int = 0x81):
        raise NotImplementedError("KWP2000.start_session: not implemented yet")

    def tester_present(self):
        raise NotImplementedError("KWP2000.tester_present: not implemented yet")

    def read_ecu_id(self):
        raise NotImplementedError("KWP2000.read_ecu_id: not implemented yet")

    def read_memory(self, address: int, size: int) -> bytes:
        raise NotImplementedError("KWP2000.read_memory: not implemented yet")
