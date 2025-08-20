import time
import serial

class ELM327:
    """
    Минимальный слой для ELM327-совместимого адаптера.
    Протокол: ISO 9141-2 (SP=3). Подходит для быстрого старта с K-Line.
    """

    def __init__(self, port: str, baudrate: int = 38400, timeout: float = 1.0):
        self.port = port
        self.ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

    def _write(self, cmd: str):
        if not cmd.endswith("\r"):
            cmd += "\r"
        self.ser.write(cmd.encode("ascii", errors="ignore"))
        self.ser.flush()

    def _read_all(self) -> str:
        # Небольшая задержка, затем вычитываем всё, что лежит в буфере.
        time.sleep(0.15)
        out = []
        while True:
            chunk = self.ser.read(self.ser.in_waiting or 1)
            if not chunk:
                break
            out.append(chunk.decode(errors="ignore"))
            time.sleep(0.02)
        return "".join(out)

    def init(self) -> str:
        """
        Базовая инициализация ELM без агрессивных авто-настроек.
        ATE0 — без echo, ATL0 — без автопереносов, ATS0 — без пробелов,
        ATH1 — с заголовками (полезно для отладки), ATSP 3 — ISO 9141-2.
        """
        init_cmds = ["ATZ", "ATE0", "ATL0", "ATS0", "ATH1", "ATSP 3"]
        last = ""
        for cmd in init_cmds:
            self._write(cmd)
            time.sleep(0.25)
            last = self._read_all()
        return last

    def send_obd(self, data_hex: str) -> str:
        """
        Отправка «сырых» OBD-команд (напр. '03' для чтения DTC).
        Возвращает «сырой» ответ адаптера.
        """
        self._write(data_hex)
        return self._read_all()

    # ---- KWP2000 helpers ----
    def set_header(self, header: str) -> str:
        """Установить KWP-заголовок (3 байта HEX)."""
        self._write(f"AT SH {header}")
        return self._read_all()

    def send_raw(self, data_hex: str) -> str:
        """Отправить произвольные байты (HEX) без интерпретации."""
        self._write(data_hex)
        return self._read_all()

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass
