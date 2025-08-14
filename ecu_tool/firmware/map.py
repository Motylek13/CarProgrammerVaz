# firmware/map.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Region:
    name: str
    start: int
    size: int

# Заглушка под Январь 7.2 (примерный размер ПЗУ 64..128 КБ; уточнять под твою прошивку)
# Для симулятора используем 64 КБ.
FLASH = Region("FLASH", start=0x0000, size=64 * 1024)

# Если понадобятся раздельные сегменты (boot/calibration), добавишь тут.
REGIONS = [FLASH]
