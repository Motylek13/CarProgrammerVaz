from __future__ import annotations
import json, sys
from pathlib import Path
from datetime import datetime

import typer
from rich import print
from serial.tools import list_ports

# --- сначала пакетные импорты (когда модуль загружается как ecu_tool.main),
#     затем fallback для запуска файла напрямую из папки ecu_tool ---
try:
    from .config import LOG_FILE
    from .diag.dtc import parse_obd_dtc
    from .ai_assistant.engine import Assistant
    from .ecu_transport.elm327 import ELM327
    from .firmware.io import SimBackend, RealBackend, dump_firmware, flash_firmware
    from .kwp_tools import kwp_ping          # <<< ВАЖНО: относительный импорт
except ImportError:
    from config import LOG_FILE
    from diag.dtc import parse_obd_dtc
    from ai_assistant.engine import Assistant
    from ecu_transport.elm327 import ELM327
    from firmware.io import SimBackend, RealBackend, dump_firmware, flash_firmware
    from kwp_tools import kwp_ping           # fallback для запуска main.py напрямую

# путь к rules.json, который работает и в exe (PyInstaller), и в исходниках
PKG_ROOT = Path(__file__).resolve().parent
BASE_RES = Path(getattr(sys, "_MEIPASS", PKG_ROOT))

DEFAULT_RULES_PATH = BASE_RES / "ai_assistant" / "rules.json"

app = typer.Typer(add_completion=False, help="ECU CLI: DTC, dump/flash (DEMO), KWP-ping.")

def _log_event(kind: str, payload: dict):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "kind": kind,
        "payload": payload,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

@app.command()
def ports():
    """Показать доступные COM-порты."""
    found = list_ports.comports()
    if not found:
        print("[yellow]Порты не найдены.[/]")
        return
    for p in found:
        print(f"[cyan]{p.device}[/] - {p.description}")

@app.command("read-dtc")
def read_dtc(
    port: str = typer.Argument(None, help="Напр. COM3 или /dev/ttyUSB0"),
    demo: bool = typer.Option(False, help="Демо-режим без железа"),
    rules: Path = typer.Option(DEFAULT_RULES_PATH, help="Файл правил для помощника"),
):
    assistant = Assistant(rules)

    if demo:
        print("[yellow]Демо-режим: используем пример ответа адаптера.[/]")
        raw = "43 01 71 00 00 00\r\n>"
        dtcs, _ = parse_obd_dtc(raw)
        _log_event("demo_response", {"raw": raw, "dtcs": dtcs})
    else:
        if not port:
            print("[red]Укажи порт, например: python main.py read-dtc COM3[/]")
            raise typer.Exit(code=2)

        print(f"[green]Подключение к адаптеру {port}...[/]")
        elm = ELM327(port)
        try:
            init_resp = elm.init()
            _log_event("elm_init", {"port": port, "resp": init_resp})
            print("[green]Инициализация завершена. Запрос DTC (Mode 03)...[/]")
            raw = elm.send_obd("03")
            _log_event("elm_resp", {"raw": raw})
            dtcs, _ = parse_obd_dtc(raw)
        finally:
            elm.close()

    if dtcs:
        print(f"[bold green]Найдено DTC:[/] {dtcs}")
    else:
        print("[bold yellow]Коды неисправностей не обнаружены или не распознаны.[/]")

    advice = assistant.advise_for_dtcs(dtcs)
    print("\n[bold]Подсказки по диагностике:[/]")
    for item in advice:
        code = item["code"] or "-"
        print(f"[cyan]{code}[/]: {item['title']}")
        for step in item["checks"]:
            print(f"  • {step}")

    _log_event("advice", {"dtcs": dtcs, "advice": advice})
    print(f"\n[dim]Логи записаны в: {LOG_FILE}[/]")

# -------- НОВЫЕ КОМАНДЫ: INFO / READ-FW / WRITE-FW ----------

@app.command("ecu-info")
def ecu_info(
    port: str = typer.Option(None, help="COM-порт, напр. COM3"),
    demo: bool = typer.Option(False, help="Демо/симулятор вместо реального ЭБУ"),
):
    """
    Показать базовую информацию о памяти/прошивке (демо: из симулятора).
    """
    if demo:
        backend = SimBackend(Path("logs/sim_ecu.bin"))
    else:
        if not port:
            print("[red]Укажи COM-порт.[/]")
            raise typer.Exit(code=2)
        elm = ELM327(port)
        backend = RealBackend(adapter=elm, developer_mode=False)

    try:
        info = backend.info()
        print("[bold]Информация об ЭБУ/памяти:[/]")
        print(json.dumps(info, ensure_ascii=False, indent=2))
    finally:
        if not demo and hasattr(backend, "close"):
            backend.close()

@app.command("read-fw")
def read_fw(
    out_file: Path = typer.Argument(Path("logs/dump.bin"), help="Куда сохранить дамп"),
    port: str = typer.Option(None, help="COM-порт для подключения"),
    demo: bool = typer.Option(False, help="Демо/симулятор вместо реального ЭБУ"),
    chunk: int = typer.Option(256, help="Размер блока чтения")
):
    """
    Считать прошивку из памяти ЭБУ (демо-симулятор полностью работает).
    На реальном ЭБУ read пока не реализован.
    """
    if demo:
        backend = SimBackend(Path("logs/sim_ecu.bin"))
    else:
        if not port:
            print("[red]Укажи COM-порт.[/]")
            raise typer.Exit(code=2)
        elm = ELM327(port)
        backend = RealBackend(adapter=elm, developer_mode=False)

    try:
        result = dump_firmware(backend, out_file, chunk)
        _log_event("read_fw", result)
        print(f"[green]Готово:[/] сохранено {result['bytes']} байт -> {result['out']}")
    except NotImplementedError as e:
        print(f"[red]{e}[/]")
    except Exception as e:
        print(f"[red]Ошибка чтения:[/] {e}")
    finally:
        if not demo and hasattr(backend, "close"):
            backend.close()

@app.command("write-fw")
def write_fw(
    in_file: Path = typer.Argument(..., help="Образ прошивки для записи"),
    port: str = typer.Option(None, help="COM-порт для подключения"),
    demo: bool = typer.Option(False, help="Демо/симулятор вместо реального ЭБУ"),
    chunk: int = typer.Option(256, help="Размер блока записи"),
    force: bool = typer.Option(False, help="Подтверждение, что понимаешь риск записи")
):
    """
    Записать прошивку в память.
    В ДЕМО работает полностью. На реальном ЭБУ ЗАПРЕЩЕНО (без developer_mode+SecurityAccess).
    """
    if not in_file.exists():
        print(f"[red]Файл не найден:[/] {in_file}")
        raise typer.Exit(code=2)

    if demo:
        backend = SimBackend(Path("logs/sim_ecu.bin"))
    else:
        if not port:
            print("[red]Укажи COM-порт.[/]")
            raise typer.Exit(code=2)
        elm = ELM327(port)
        backend = RealBackend(adapter=elm, developer_mode=False)

    if not demo and not force:
        print("[red]На реальном ЭБУ запись отключена по безопасности.[/]")
        print("Если ты действительно на стенде и понимаешь риск — работаем в DEMO сейчас.")
        raise typer.Exit(code=3)

    try:
        result = flash_firmware(backend, in_file, chunk)
        _log_event("write_fw", result)
        print(f"[green]Готово:[/] записано {result['bytes']} байт из {result['source']}")
    except PermissionError as e:
        print(f"[red]{e}[/]")
    except NotImplementedError as e:
        print(f"[red]{e}[/]")
    except Exception as e:
        print(f"[red]Ошибка записи:[/] {e}")
    finally:
        if not demo and hasattr(backend, "close"):
            backend.close()

# ... внизу рядом с другими командами:

@app.command("kwp-ping")
def kwp_ping_cmd(port: str = typer.Argument(..., help="COM-порт, напр. COM3"),
                 header: str = typer.Option("81 10 F1", help="KWP заголовок (3 байта HEX)")):
    """
    Безопасный тест KWP2000: 10 81 + 3E 00. Ничего не пишет в ЭБУ.
    """
    elm = ELM327(port)
    try:
        print("[green]Инициализация адаптера…[/]")
        elm.init()
        print(f"[green]Устанавливаю заголовок {header}…[/]")
        ok = kwp_ping(elm, header=header, verbose=True)
        if ok:
            print("[bold green]Связь по KWP есть (ECU отвечает).[/]")
        else:
            print("[bold yellow]Ответ не распознан. Проверь линии, заголовок, зажигание.[/]")
    finally:
        elm.close()


if __name__ == "__main__":
    app()
