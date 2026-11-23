from __future__ import annotations

import datetime as dt
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    origin: str = "BOS"
    destinations: list[str] = field(default_factory=list)
    months: list[str] = field(default_factory=list)
    months_ahead: int = 6
    one_way: bool = False
    direct_only: bool = True
    currency: str = "usd"
    max_price: float = 400
    drop_pct: float = 15
    telegram_token: str = ""
    telegram_chat_id: str = ""

    def search_months(self, today: dt.date | None = None) -> list[str]:
        if self.months:
            return self.months
        today = today or dt.date.today()
        out = []
        y, m = today.year, today.month
        for _ in range(self.months_ahead):
            out.append(f"{y:04d}-{m:02d}")
            m += 1
            if m > 12:
                y, m = y + 1, 1
        return out


def load(path: str | Path = "config.toml") -> Config:
    data: dict = {}
    p = Path(path)
    if p.exists():
        data = tomllib.loads(p.read_text())
    alerts = data.get("alerts", {})
    tg = data.get("telegram", {})
    return Config(
        origin=data.get("origin", "BOS").upper(),
        destinations=[d.upper() for d in data.get("destinations", [])],
        months=data.get("months", []),
        months_ahead=int(data.get("months_ahead", 6)),
        one_way=bool(data.get("one_way", False)),
        direct_only=bool(data.get("direct_only", True)),
        currency=data.get("currency", "usd").lower(),
        max_price=float(alerts.get("max_price", 400)),
        drop_pct=float(alerts.get("drop_pct", 15)),
        telegram_token=tg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=tg.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID", ""),
    )
