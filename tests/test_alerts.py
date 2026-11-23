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
