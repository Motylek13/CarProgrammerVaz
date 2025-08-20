# ECU Tool

Инструмент для диагностики и работы с прошивками ЭБУ (электронных блоков управления) автомобилей ВАЗ.

## Установка

1. Установите [Python 3.10+](https://www.python.org/).
2. Создайте виртуальное окружение и активируйте его:
   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   ```
3. Установите зависимости (минимальный набор для CLI/GUI):
   ```bash
   pip install typer rich pyserial PySide6
   ```

## Запуск GUI

Запустите графический интерфейс:
```bash
python run_ecu.py
```
По умолчанию в окне включён флажок **«Демо»**, который использует симулятор вместо реального ЭБУ. Для работы с железом снимите флажок и выберите нужный COM‑порт.

Во вкладке «Тюнинг» можно наглядно менять ограничение оборотов, таблицу смеси и флаг «отстрелов». Изменения применяются к открытому образу прошивки, а график отображает таблицу смеси.

## Запуск из командной строки

CLI вызывается модулем `ecu_tool.main`:
```bash
python -m ecu_tool.main [команда] [опции]
```
Доступные команды: `ports`, `read-dtc`, `ecu-info`, `read-fw`, `write-fw`, `kwp-ping`.

### Примеры

*Считать DTC в демо‑режиме:*
```bash
python -m ecu_tool.main read-dtc --demo
```

*Считать DTC с реального ЭБУ (например, в порту COM3):*
```bash
python -m ecu_tool.main read-dtc COM3
```

*Считать прошивку в файл (демо):*
```bash
python -m ecu_tool.main read-fw logs/dump.bin --demo
```

*Записать прошивку в симулятор:*
```bash
python -m ecu_tool.main write-fw firmware.bin --demo
```

## Сборка standalone

Для создания исполняемого файла используйте [PyInstaller](https://pyinstaller.org/):
```bash
pyinstaller ECU-Tool.spec
```
Готовый бинарник появится в каталоге `dist/`.

