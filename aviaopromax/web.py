"""Interface web local: python -m aviaopromax.web  →  http://localhost:8000"""
from __future__ import annotations

import argparse
import json
import os
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import alerts, config
from .providers import MockProvider, TravelpayoutsProvider
from .store import Store

STATIC = Path(__file__).parent / "static"


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
        f"one_way = {_toml_value(cfg.one_way)}",
        f"direct_only = {_toml_value(cfg.direct_only)}",
        f"currency = {_toml_value(cfg.currency)}",
        "",
        "[alerts]",
        f"max_price = {_toml_value(cfg.max_price)}",
        f"drop_pct = {_toml_value(cfg.drop_pct)}",
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
    for key in ("months_ahead",):
        if key in form:
            cfg.months_ahead = max(1, min(12, int(form[key] or 6)))
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
        d.pop("telegram_chat_id")
        d["has_token"] = bool(os.getenv("TRAVELPAYOUTS_TOKEN"))
        d["has_telegram"] = bool(cfg.telegram_token and cfg.telegram_chat_id)
        d["search_months"] = cfg.search_months()
        return d

    def search(self, form: dict) -> dict:
        cfg = apply_form(config.load(self.config_path), form)
        provider = MockProvider() if form.get("mock") else TravelpayoutsProvider()
        store = Store(self.db_path)
        offers = provider.search(cfg)
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
        return {"months": cfg.search_months(), "results": rows, "deal_count": len(deals)}

    def save(self, form: dict) -> dict:
        cfg = apply_form(config.load(self.config_path), form)
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
