"""Fontes de preços.

TravelpayoutsProvider usa a Data API do Aviasales/Travelpayouts (gratuita,
precisa de token: https://www.travelpayouts.com/developers/api). Ela aceita
busca sem destino, o que permite "qualquer lugar".

MockProvider gera dados falsos para testar sem token.
"""
from __future__ import annotations

import datetime as dt
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

    @staticmethod
    def _date_params(cfg: Config) -> list[dict]:
        """Um conjunto de parâmetros de data por chamada à API."""
        win = cfg.depart_window()
        departs = [win[0].isoformat()] if win and win[0] == win[1] else cfg.search_months()
        extra = {}
        rwin = cfg.return_window()
        if rwin and rwin[0] == rwin[1]:
            extra["return_at"] = rwin[0].isoformat()
        elif rwin and rwin[0].strftime("%Y-%m") == rwin[1].strftime("%Y-%m"):
            extra["return_at"] = rwin[0].strftime("%Y-%m")
        return [{"departure_at": d, **extra} for d in departs]

    def search(self, cfg: Config) -> list[Offer]:
        offers: list[Offer] = []
        dests = cfg.destinations or [""]
        for dest in dests:
            for dates in self._date_params(cfg):
                params = {
                    "origin": cfg.origin,
                    **dates,
                    "one_way": str(cfg.one_way).lower(),
                    "direct": str(cfg.direct_only).lower(),
                    "currency": cfg.currency,
                    "sorting": "price",
                    "limit": 1000,
                }
                if dest:
                    params["destination"] = dest
                for d in self._get(params):
                    if cfg.direct_only and (d.get("transfers") or d.get("return_transfers")):
                        continue
                    link = d.get("link", "")
                    o = Offer(
                        origin=d.get("origin_airport") or d.get("origin", cfg.origin),
                        destination=d.get("destination_airport") or d.get("destination", dest),
                        price=float(d["price"]),
                        currency=cfg.currency,
                        depart=(d.get("departure_at") or "")[:10],
                        ret=(d.get("return_at") or "")[:10],
                        airline=d.get("airline", ""),
                        transfers=int(d.get("transfers", 0)),
                        link=f"https://www.aviasales.com{link}" if link else "",
                    )
                    # A API usa códigos de cidade (BOS inclui PSM, NYC = JFK/LGA/EWR):
                    # só aceita o aeroporto exato que foi escolhido.
                    if o.origin != cfg.origin or (cfg.destinations and o.destination not in cfg.destinations):
                        continue
                    if cfg.matches_dates(o.depart, o.ret):
                        offers.append(o)
        return offers


class MockProvider:
    DESTS = ["LIS", "MAD", "CUN", "SJU", "MIA", "LAX", "REY", "DUB", "GRU", "MEX"]

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def _pick(self, lo: dt.date, hi: dt.date) -> dt.date:
        return lo + dt.timedelta(days=self.rng.randint(0, (hi - lo).days))

    def search(self, cfg: Config) -> list[Offer]:
        dests = cfg.destinations or self.DESTS
        win, rwin = cfg.depart_window(), cfg.return_window()
        out = []
        for dest in dests:
            for month in cfg.search_months():
                y, m = map(int, month.split("-"))
                lo, hi = dt.date(y, m, 1), dt.date(y, m, 28)
                if win:
                    lo, hi = max(lo, win[0]), min(hi, win[1])
                    if lo > hi:
                        continue
                dep = self._pick(lo, hi)
                if cfg.one_way:
                    ret = ""
                elif rwin:
                    ret = self._pick(max(rwin[0], dep), max(rwin[1], dep)).isoformat()
                else:
                    ret = (dep + dt.timedelta(days=7)).isoformat()
                out.append(
                    Offer(
                        origin=cfg.origin,
                        destination=dest,
                        price=float(self.rng.randint(90, 900)),
                        currency=cfg.currency,
                        depart=dep.isoformat(),
                        ret=ret,
                        airline=self.rng.choice(["B6", "DL", "AA", "UA", "TP"]),
                        transfers=0 if cfg.direct_only else self.rng.randint(0, 2),
                        link="",
                    )
                )
        return out
