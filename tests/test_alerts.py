import datetime as dt

from aviaopromax.alerts import find_deals
from aviaopromax.config import Config
from aviaopromax.providers import Offer
from aviaopromax.store import Store


def offer(dest, price):
    return Offer("BOS", dest, price, "usd", "2027-01-10", "2027-01-17", "B6", 0, "")


def test_search_months_rolls_over_year():
    cfg = Config(months_ahead=3)
    assert cfg.search_months(dt.date(2026, 11, 23)) == ["2026-11", "2026-12", "2027-01"]


def test_max_price_alert():
    cfg = Config(max_price=300)
    deals = find_deals(cfg, [offer("LIS", 250), offer("MAD", 500)], Store(":memory:"))
    assert [o.destination for o, _ in deals] == ["LIS"]


def test_drop_alert():
    cfg = Config(max_price=0, drop_pct=20)
    store = Store(":memory:")
    store.save([offer("LIS", 500)])
    assert find_deals(cfg, [offer("LIS", 450)], store) == []
    deals = find_deals(cfg, [offer("LIS", 390)], store)
    assert len(deals) == 1 and "caiu" in deals[0][1]


def test_months_from_exact_window():
    cfg = Config(depart_from="2026-12-28", depart_to="2027-02-02")
    assert cfg.search_months() == ["2026-12", "2027-01", "2027-02"]
    assert cfg.matches_dates("2027-01-15", "")
    assert not cfg.matches_dates("2027-02-03", "")


def test_travelpayouts_exact_day_params():
    from aviaopromax.providers import TravelpayoutsProvider
    cfg = Config(depart_from="2027-01-10", return_from="2027-01-17")
    assert TravelpayoutsProvider._date_params(cfg) == [
        {"departure_at": "2027-01-10", "return_at": "2027-01-17"}
    ]


def test_travelpayouts_keeps_only_exact_airports(monkeypatch):
    from aviaopromax.providers import TravelpayoutsProvider
    rows = [
        {"origin": "BOS", "origin_airport": "PSM", "destination": "ORL", "destination_airport": "MCO",
         "price": 128, "departure_at": "2027-01-30T10:00:00-05:00", "transfers": 0},
        {"origin": "BOS", "origin_airport": "BOS", "destination": "NYC", "destination_airport": "LGA",
         "price": 141, "departure_at": "2027-01-14T06:00:00-05:00", "transfers": 0},
        {"origin": "BOS", "origin_airport": "BOS", "destination": "SAN", "destination_airport": "SAN",
         "price": 154, "departure_at": "2027-01-28T06:00:00-05:00", "transfers": 1},
    ]
    p = TravelpayoutsProvider(token="x")
    monkeypatch.setattr(p, "_get", lambda params: rows)
    offers = p.search(Config(months=["2027-01"], one_way=True))
    assert [o.route for o in offers] == ["BOS-LGA"]
