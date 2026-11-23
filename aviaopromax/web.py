"""Interface web local: python -m aviaopromax.web  →  http://localhost:8000"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import alerts, config
from .providers import (
    CombinedProvider,
    MockProvider,
    SerpApiProvider,
    TravelpayoutsProvider,
    google_flights_url,
)
from .store import Store

STATIC = Path(__file__).parent / "static"
_AIRPORTS: set[str] | None = None


def known_airports() -> set[str]:
    global _AIRPORTS
    if _AIRPORTS is None:
        _AIRPORTS = {a[0] for a in json.loads((STATIC / "airports.json").read_text())}
    return _AIRPORTS


def validate(cfg: config.Config) -> None:
    known = known_airports()
    bad = [c for c in [cfg.origin, *cfg.destinations] if c not in known]
    if bad:
        raise ValueError(f"Aeroporto desconhecido: {', '.join(bad)}")
    win, rwin = cfg.depart_window(), cfg.return_window()
    if rwin and not win:
        raise ValueError("Escolha a data de ida antes da volta.")
    if win and rwin and rwin[1] < win[0]:
        raise ValueError("A volta não pode ser antes da ida.")


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return f"{v:g}"
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return json.dumps(str(v))


def save_config(cfg: config.Config, path: Path) -> None:
    lines = [
        f"origin = {_toml_value(cfg.origin)}",
        f"destinations = {_toml_value(cfg.destinations)}",
        f"months = {_toml_value(cfg.months)}",
        f"months_ahead = {cfg.months_ahead}",
        f"depart_from = {_toml_value(cfg.depart_from)}",
        f"depart_to = {_toml_value(cfg.depart_to)}",
        f"return_from = {_toml_value(cfg.return_from)}",
        f"return_to = {_toml_value(cfg.return_to)}",
        f"one_way = {_toml_value(cfg.one_way)}",
        f"direct_only = {_toml_value(cfg.direct_only)}",
        f"currency = {_toml_value(cfg.currency)}",
        "",
        "[alerts]",
        f"max_price = {_toml_value(cfg.max_price)}",
        f"drop_pct = {_toml_value(cfg.drop_pct)}",
        "",
        "[travelpayouts]",
        f"token = {_toml_value(cfg.travelpayouts_token)}",
        "",
        "[serpapi]",
        f"key = {_toml_value(cfg.serpapi_key)}",
        "",
        "[telegram]",
        f"bot_token = {_toml_value(cfg.telegram_token)}",
        f"chat_id = {_toml_value(cfg.telegram_chat_id)}",
    ]
    path.write_text("\n".join(lines) + "\n")


def _codes(v) -> list[str]:
    if isinstance(v, str):
        v = v.replace(",", " ").split()
    return [str(x).strip().upper() for x in v or [] if str(x).strip()]


def apply_form(cfg: config.Config, form: dict) -> config.Config:
    if "origin" in form:
        cfg.origin = str(form["origin"]).strip().upper() or cfg.origin
    if "destinations" in form:
        cfg.destinations = _codes(form["destinations"])
    if "months" in form:
        cfg.months = [m for m in _codes(form["months"]) if m]
    if "months_ahead" in form:
        cfg.months_ahead = max(1, min(12, int(form["months_ahead"] or 6)))
    for key in ("depart_from", "depart_to", "return_from", "return_to"):
        if key in form:
            v = str(form[key] or "").strip()
            if v:
                dt.date.fromisoformat(v)  # erro se a data for inválida
            setattr(cfg, key, v)
    for key in ("one_way", "direct_only"):
        if key in form:
            setattr(cfg, key, bool(form[key]))
    for key in ("max_price", "drop_pct"):
        if key in form:
            setattr(cfg, key, float(form[key] or 0))
    if form.get("currency"):
        cfg.currency = str(form["currency"]).lower()
    return cfg


class App:
    def __init__(self, config_path: Path, db_path: str):
        self.config_path = config_path
        self.db_path = db_path

    def get_config(self) -> dict:
        cfg = config.load(self.config_path)
        d = asdict(cfg)
        d.pop("telegram_token")
        d.pop("travelpayouts_token")
        d.pop("serpapi_key")
        d.pop("telegram_chat_id")
        d["has_token"] = bool(cfg.travelpayouts_token)
        d["has_serpapi"] = bool(cfg.serpapi_key)
        d["has_telegram"] = bool(cfg.telegram_token and cfg.telegram_chat_id)
        d["search_months"] = cfg.search_months()
        return d

    def search(self, form: dict) -> dict:
        cfg = apply_form(config.load(self.config_path), form)
        validate(cfg)
        provider = self.provider(cfg, bool(form.get("mock")))
        store = Store(self.db_path)
        offers = provider.search(cfg)
        notes = list(getattr(provider, "notes", []))
        deals = dict((o.route, r) for o, r in alerts.find_deals(cfg, offers, store))
        best = sorted(alerts.cheapest_per_route(offers).values(), key=lambda o: o.price)
        rows = []
        for o in best:
            rows.append(
                {
                    **asdict(o),
                    "route": o.route,
                    "previous_best": store.best_before(o.route, o.currency),
                    "deal": deals.get(o.route, ""),
                }
            )
        store.save(offers)
        if deals and form.get("notify"):
            msg = "Promoções encontradas:\n" + "\n".join(
                alerts.format_deal(o, deals[o.route]) for o in best if o.route in deals
            )
            alerts.send_telegram(cfg, msg)
        found = {o.destination for o in best}
        win, rwin = cfg.depart_window(), cfg.return_window()
        depart = win[0].isoformat() if win else ""
        ret = rwin[0].isoformat() if rwin else ""
        missing = [
            {"destination": d, "google_flights": google_flights_url(cfg.origin, d, depart, ret, cfg.direct_only)}
            for d in cfg.destinations
            if d not in found
        ]
        return {
            "months": cfg.search_months(),
            "results": rows,
            "deal_count": len(deals),
            "notes": notes,
            "missing": missing,
        }

    @staticmethod
    def provider(cfg: config.Config, mock: bool):
        if mock:
            return MockProvider()
        sources = []
        if cfg.travelpayouts_token:
            sources.append(TravelpayoutsProvider(cfg.travelpayouts_token))
        if cfg.serpapi_key:
            sources.append(SerpApiProvider(cfg.serpapi_key))
        if not sources:
            raise RuntimeError("Nenhuma chave de API configurada (ou use o modo teste).")
        return CombinedProvider(sources)

    def save_token(self, form: dict) -> dict:
        token = str(form.get("token") or "").strip()
        if not token:
            raise ValueError("Cole a chave.")
        cfg = config.load(self.config_path)
        if form.get("kind") == "serpapi":
            cfg.serpapi_key = token
            # confere a chave sem gastar busca (a API de conta é grátis)
            url = "https://serpapi.com/account.json?" + urllib.parse.urlencode({"api_key": token})
            with urllib.request.urlopen(url, timeout=30) as r:
                info = json.load(r)
            if info.get("error"):
                raise ValueError(info["error"])
        else:
            cfg.travelpayouts_token = token
            TravelpayoutsProvider(token)._get(  # confere se o token funciona
                {"origin": cfg.origin, "currency": cfg.currency, "limit": 1}
            )
        save_config(cfg, self.config_path)
        return self.get_config()

    def save(self, form: dict) -> dict:
        cfg = apply_form(config.load(self.config_path), form)
        validate(cfg)
        save_config(cfg, self.config_path)
        return self.get_config()


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data) -> None:
            self._send(code, json.dumps(data).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/airports.json":
                self._send(200, (STATIC / "airports.json").read_bytes(), "application/json")
            elif self.path == "/api/config":
                self._json(200, app.get_config())
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                form = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/search":
                    self._json(200, app.search(form))
                elif self.path == "/api/config":
                    self._json(200, app.save(form))
                elif self.path == "/api/token":
                    self._json(200, app.save_token(form))
                else:
                    self._json(404, {"error": "not found"})
            except Exception as e:  # mostra o erro na interface
                self._json(400, {"error": str(e)})

    return Handler


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aviaopromax.web")
    ap.add_argument("-c", "--config", default="config.toml")
    ap.add_argument("--db", default="prices.db")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)

    app = App(Path(args.config), args.db)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    url = f"http://localhost:{args.port}"
    print(f"aviaopromax rodando em {url}  (Ctrl+C para sair)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
