# kwp_tools.py
import time
from rich import print

def kwp_ping(elm, header="81 10 F1", verbose=True) -> bool:
    """
    Безопасный KWP-тест:
    - Устанавливает заголовок
    - Посылает 10 81 (DiagSessionControl — extended)
    - Посылает 3E 00 (TesterPresent)
    Возвращает True/False по факту «живой» реакции.
    """
    try:
        elm.set_header(header)
        time.sleep(0.05)
        resp1 = elm.send_raw("10 81")
        if verbose: print("[cyan]>> 10 81[/]"); print(resp1)
        ok1 = "50 81" in resp1.replace(" ", "").upper()  # PositiveResponse = 0x50
        time.sleep(0.05)
        resp2 = elm.send_raw("3E 00")
        if verbose: print("[cyan]>> 3E 00[/]"); print(resp2)
        ok2 = "7E 00" in resp2.replace(" ", "").upper() or "7E00" in resp2.replace(" ", "").upper() or "ACK" in resp2.upper()
        return bool(ok1 or ok2)
    except Exception as e:
        if verbose: print(f"[red]Ошибка KWP-ping:[/] {e}")
        return False
