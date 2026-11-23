from __future__ import annotations

import json
import urllib.request

from .config import Config
from .providers import Offer
from .store import Store


def cheapest_per_route(offers: list[Offer]) -> dict[str, Offer]:
    best: dict[str, Offer] = {}
    for o in offers:
        if o.route not in best or o.price < best[o.route].price:
            best[o.route] = o
    return best


def find_deals(cfg: Config, offers: list[Offer], store: Store) -> list[tuple[Offer, str]]:
    """Retorna (oferta, motivo) para cada rota que merece alerta."""
    deals = []
    for route, o in sorted(cheapest_per_route(offers).items(), key=lambda kv: kv[1].price):
        reasons = []
        if cfg.max_price and o.price <= cfg.max_price:
            reasons.append(f"abaixo de {cfg.max_price:g}")
        prev = store.best_before(route, o.currency)
        if prev and o.price <= prev * (1 - cfg.drop_pct / 100):
            reasons.append(f"caiu {100 * (1 - o.price / prev):.0f}% (antes {prev:g})")
        if reasons:
            deals.append((o, "; ".join(reasons)))
    return deals


def format_deal(o: Offer, reason: str) -> str:
    trip = f"{o.depart} → {o.ret}" if o.ret else f"{o.depart} (só ida)"
    stops = "direto" if o.transfers == 0 else f"{o.transfers} escala(s)"
    line = f"✈️ {o.route}  {o.price:g} {o.currency.upper()}  {trip}  {o.airline} {stops}  [{reason}]"
    return f"{line}\n   {o.link}" if o.link else line


def send_telegram(cfg: Config, text: str) -> None:
    if not (cfg.telegram_token and cfg.telegram_chat_id):
        return
    url = f"https://api.telegram.org/bot{cfg.telegram_token}/sendMessage"
    data = json.dumps(
        {"chat_id": cfg.telegram_chat_id, "text": text, "disable_web_page_preview": True}
    ).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()
