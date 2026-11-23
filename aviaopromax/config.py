from __future__ import annotations

import datetime as dt
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _month_range(start: dt.date, end: dt.date) -> list[str]:
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _date(s: str) -> dt.date | None:
    return dt.date.fromisoformat(s) if s else None


@dataclass
class Config:
    origin: str = "BOS"
    destinations: list[str] = field(default_factory=list)
    months: list[str] = field(default_factory=list)
    months_ahead: int = 6
    # Datas exatas (AAAA-MM-DD). Se depart_from estiver preenchido, substituem `months`.
    # "até" vazio = mesmo dia do "de".
    depart_from: str = ""
    depart_to: str = ""
    return_from: str = ""
    return_to: str = ""
    one_way: bool = False
    direct_only: bool = True
    currency: str = "usd"
    max_price: float = 400
    drop_pct: float = 15
    travelpayouts_token: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""

    def depart_window(self) -> tuple[dt.date, dt.date] | None:
        if not self.depart_from:
            return None
        a = _date(self.depart_from)
        b = _date(self.depart_to) or a
        return (min(a, b), max(a, b))

    def return_window(self) -> tuple[dt.date, dt.date] | None:
        if self.one_way or not self.return_from:
            return None
        a = _date(self.return_from)
        b = _date(self.return_to) or a
        return (min(a, b), max(a, b))

    def search_months(self, today: dt.date | None = None) -> list[str]:
        win = self.depart_window()
        if win:
            return _month_range(*win)
        if self.months:
            return self.months
        today = today or dt.date.today()
        end_m = today.month + self.months_ahead - 1
        end = dt.date(today.year + (end_m - 1) // 12, (end_m - 1) % 12 + 1, 1)
        return _month_range(today, end)

    def matches_dates(self, depart: str, ret: str) -> bool:
        """Confere se a oferta cai nas janelas de data escolhidas."""
        win = self.depart_window()
        if win and not (depart and win[0] <= _date(depart) <= win[1]):
            return False
        rwin = self.return_window()
        if rwin and not (ret and rwin[0] <= _date(ret) <= rwin[1]):
            return False
        return True


def load(path: str | Path = "config.toml") -> Config:
    data: dict = {}
    p = Path(path)
    if p.exists():
        data = tomllib.loads(p.read_text())
    alerts = data.get("alerts", {})
    tg = data.get("telegram", {})
    tp = data.get("travelpayouts", {})
    return Config(
        origin=data.get("origin", "BOS").upper(),
        destinations=[d.upper() for d in data.get("destinations", [])],
        months=data.get("months", []),
        months_ahead=int(data.get("months_ahead", 6)),
        depart_from=data.get("depart_from", ""),
        depart_to=data.get("depart_to", ""),
        return_from=data.get("return_from", ""),
        return_to=data.get("return_to", ""),
        one_way=bool(data.get("one_way", False)),
        direct_only=bool(data.get("direct_only", True)),
        currency=data.get("currency", "usd").lower(),
        max_price=float(alerts.get("max_price", 400)),
        drop_pct=float(alerts.get("drop_pct", 15)),
        travelpayouts_token=(tp.get("token") or os.getenv("TRAVELPAYOUTS_TOKEN", "")).strip(),
        telegram_token=tg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=tg.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID", ""),
    )
