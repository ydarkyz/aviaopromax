from __future__ import annotations

import argparse

from . import alerts, config
from .store import Store


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aviaopromax", description="Monitor de promoções de passagens")
    ap.add_argument("-c", "--config", default="config.toml")
    ap.add_argument("--db", default="prices.db")
    ap.add_argument("--mock", action="store_true", help="usa dados falsos (sem token)")
    ap.add_argument("--top", type=int, default=10, help="quantas rotas mais baratas listar")
    args = ap.parse_args(argv)

    cfg = config.load(args.config)
    from .web import App

    provider = App.provider(cfg, args.mock)
    store = Store(args.db)

    dest = ", ".join(cfg.destinations) or "qualquer lugar"
    print(f"Buscando {cfg.origin} → {dest} | meses: {', '.join(cfg.search_months())}")
    offers = provider.search(cfg)
    if not offers:
        print("Nenhuma oferta encontrada.")
        return 0

    deals = alerts.find_deals(cfg, offers, store)
    store.save(offers)

    print(f"\nTop {args.top} mais baratas:")
    best = sorted(alerts.cheapest_per_route(offers).values(), key=lambda o: o.price)
    for o in best[: args.top]:
        print("  " + alerts.format_deal(o, "").replace("  []", ""))

    if deals:
        msg = "Promoções encontradas:\n" + "\n".join(alerts.format_deal(o, r) for o, r in deals)
        print("\n" + msg)
        alerts.send_telegram(cfg, msg)
    else:
        print("\nNenhum alerta desta vez.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
