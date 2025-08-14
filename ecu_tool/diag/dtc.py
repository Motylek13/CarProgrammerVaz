# diag/dtc.py
def parse_obd_dtc(raw: str):
    lines = [L.strip() for L in raw.replace("\r", "\n").split("\n") if L.strip()]
    data = "".join([l for l in lines if not l.startswith("AT") and "ELM" not in l]).replace(" ", "").upper()

    if "43" not in data:
        return [], raw

    try:
        idx = data.index("43") + 2
        payload = data[idx:]
        dtcs = []
        for i in range(0, len(payload), 4):
            chunk = payload[i:i+4]
            if len(chunk) < 4 or chunk == "0000":
                continue

            b1 = int(chunk[0:2], 16)
            b2 = int(chunk[2:4], 16)

            # первые 2 бита -> буква (P/C/B/U)
            first = (b1 & 0xC0) >> 6
            system = "P" if first == 0 else "C" if first == 1 else "B" if first == 2 else "U"

            # следующие 2 бита -> 1-я цифра, последние 4 бита -> 2-я цифра
            d1 = (b1 & 0x30) >> 4
            d2 = (b1 & 0x0F)

            code = f"{system}{d1:X}{d2:X}{b2:02X}"
            dtcs.append(code)

        return dtcs, raw
    except Exception:
        return [], raw
