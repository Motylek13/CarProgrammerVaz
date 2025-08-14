import json
from pathlib import Path

class Assistant:
    """
    Простой офлайн «ИИ»-помощник на базе правил.
    На вход получает список DTC и отдаёт структурированные подсказки.
    """
    def __init__(self, rules_path: Path):
        with open(rules_path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)

    def advise_for_dtcs(self, dtcs: list[str]) -> list[dict]:
        advices = []
        for code in dtcs:
            rule = self.rules.get(code) or self.rules.get(code[:4] + "x") or self.rules.get("default")
            advices.append({
                "code": code,
                "title": rule.get("title", "Рекомендации"),
                "checks": rule.get("checks", [])
            })
        if not dtcs:  # на всякий случай
            advices.append({
                "code": None,
                "title": self.rules.get("default", {}).get("title", "Рекомендации"),
                "checks": self.rules.get("default", {}).get("checks", [])
            })
        return advices
