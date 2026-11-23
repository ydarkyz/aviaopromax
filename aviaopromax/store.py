"""Histórico de preços em SQLite."""
from __future__ import annotations

import sqlite3
import time

from .providers import Offer

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    route TEXT NOT NULL,
    depart TEXT NOT NULL,
    ret TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    seen_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_route ON prices(route, currency);
"""


class Store:
    def __init__(self, path: str = "prices.db"):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def best_before(self, route: str, currency: str) -> float | None:
        row = self.db.execute(
            "SELECT MIN(price) FROM prices WHERE route=? AND currency=?",
            (route, currency),
        ).fetchone()
        return row[0]

    def save(self, offers: list[Offer]) -> None:
        now = int(time.time())
        self.db.executemany(
            "INSERT INTO prices VALUES (?,?,?,?,?,?)",
            [(o.route, o.depart, o.ret, o.price, o.currency, now) for o in offers],
        )
        self.db.commit()
