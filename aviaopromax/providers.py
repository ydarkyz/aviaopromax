"""Fontes de preços.

TravelpayoutsProvider usa a Data API do Aviasales/Travelpayouts (gratuita,
precisa de token: https://www.travelpayouts.com/developers/api). Ela aceita
busca sem destino, o que permite "qualquer lugar".

MockProvider gera dados falsos para testar sem token.
"""
from __future__ import annotations

import json
import os
import random
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .config import Config


@dataclass(frozen=True)
class Offer:
    origin: str
    destination: str
    price: float
    currency: str
    depart: str  # ISO date
    ret: str  # ISO date ou ""
    airline: str
    transfers: int
    link: str

    @property
    def route(self) -> str:
        return f"{self.origin}-{self.destination}"


class TravelpayoutsProvider:
    URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("TRAVELPAYOUTS_TOKEN", "")
        if not self.token:
            raise RuntimeError("Defina TRAVELPAYOUTS_TOKEN (ou use --mock).")

    def _get(self, params: dict) -> list[dict]:
        url = f"{self.URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"X-Access-Token": self.token})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
        if not body.get("success", False):
            raise RuntimeError(f"Travelpayouts error: {body.get('error')}")
        return body.get("data", [])

    def search(self, cfg: Config) -> list[Offer]:
        offers: list[Offer] = []
        dests = cfg.destinations or [""]
        for dest in dests:
            for month in cfg.search_months():
                params = {
                    "origin": cfg.origin,
                    "departure_at": month,
                    "one_way": str(cfg.one_way).lower(),
                    "direct": str(cfg.direct_only).lower(),
                    "currency": cfg.currency,
                    "sorting": "price",
                    "limit": 1000,
                }
                if dest:
                    params["destination"] = dest
                for d in self._get(params):
                    link = d.get("link", "")
                    offers.append(
                        Offer(
                            origin=d.get("origin", cfg.origin),
                            destination=d.get("destination", dest),
                            price=float(d["price"]),
                            currency=cfg.currency,
                            depart=(d.get("departure_at") or "")[:10],
                            ret=(d.get("return_at") or "")[:10],
                            airline=d.get("airline", ""),
                            transfers=int(d.get("transfers", 0)),
                            link=f"https://www.aviasales.com{link}" if link else "",
                        )
                    )
        return offers


class MockProvider:
    DESTS = ["LIS", "MAD", "CUN", "SJU", "MIA", "LAX", "REY", "DUB", "GRU", "MEX"]

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def search(self, cfg: Config) -> list[Offer]:
        dests = cfg.destinations or self.DESTS
        out = []
        for dest in dests:
            for month in cfg.search_months():
                day = self.rng.randint(1, 21)
                out.append(
                    Offer(
                        origin=cfg.origin,
                        destination=dest,
                        price=float(self.rng.randint(90, 900)),
                        currency=cfg.currency,
                        depart=f"{month}-{day:02d}",
                        ret="" if cfg.one_way else f"{month}-{day + 7:02d}",
                        airline=self.rng.choice(["B6", "DL", "AA", "UA", "TP"]),
                        transfers=self.rng.randint(0, 2),
                        link="",
                    )
                )
        return out
