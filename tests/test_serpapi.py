from aviaopromax.config import Config
from aviaopromax.providers import CombinedProvider, SerpApiProvider, google_flights_url


def fake_body(dest, day, stops_legs=1):
    legs = [{"departure_airport": {"id": "BOS", "time": f"{day} 21:30"},
             "arrival_airport": {"id": dest, "time": "x"}, "airline": "LATAM"}]
    if stops_legs == 2:
        legs = [{"departure_airport": {"id": "BOS", "time": f"{day} 08:00"},
                 "arrival_airport": {"id": "MIA", "time": "x"}, "airline": "AA"},
                {"departure_airport": {"id": "MIA", "time": "x"},
                 "arrival_airport": {"id": dest, "time": "x"}, "airline": "LATAM"}]
    return {"search_metadata": {"google_flights_url": "https://g/f"},
            "best_flights": [{"flights": legs, "price": 612}], "other_flights": []}


def test_serpapi_parses_direct_flights(monkeypatch):
    p = SerpApiProvider("k")
    calls = []
    monkeypatch.setattr(p, "_get", lambda params: calls.append(params) or fake_body(params["arrival_id"], params["outbound_date"]))
    cfg = Config(destinations=["GRU"], depart_from="2027-01-16", depart_to="2027-01-17", one_way=True)
    offers = p.search(cfg)
    assert [(o.route, o.depart, o.price, o.airline) for o in offers] == [
        ("BOS-GRU", "2027-01-16", 612.0, "LATAM"), ("BOS-GRU", "2027-01-17", 612.0, "LATAM")]
    assert calls[0]["stops"] == "1" and calls[0]["type"] == "2"


def test_serpapi_drops_connections_when_direct_only(monkeypatch):
    p = SerpApiProvider("k")
    monkeypatch.setattr(p, "_get", lambda params: fake_body("GRU", params["outbound_date"], stops_legs=2))
    cfg = Config(destinations=["GRU"], depart_from="2027-01-16", one_way=True)
    assert p.search(cfg) == []


def test_serpapi_skipped_without_exact_dates_and_capped():
    p = SerpApiProvider("k", max_calls=3)
    assert p.plan(Config(destinations=["GRU"])) == []  # meses flexíveis
    assert p.plan(Config(depart_from="2027-01-16", one_way=True)) == []  # qualquer destino
    assert p.plan(Config(destinations=["GRU"], depart_from="2027-01-16")) == []  # ida e volta sem volta
    cfg = Config(destinations=["GRU", "LIS"], depart_from="2027-01-16", depart_to="2027-01-23", one_way=True)
    assert len(p.plan(cfg)) == 16


def test_combined_turns_failure_into_note():
    class Boom:
        def search(self, cfg):
            raise RuntimeError("fora do ar")

    class Ok:
        notes = ["aviso"]
        def search(self, cfg):
            return []

    c = CombinedProvider([Boom(), Ok()])
    assert c.search(Config()) == []
    assert c.notes == ["Boom: fora do ar", "aviso"]


def test_google_flights_url():
    url = google_flights_url("BOS", "GRU", "2027-01-16", "", True)
    assert url.startswith("https://www.google.com/travel/flights?q=")
    assert "GRU" in url and "nonstop" in url and "one+way" in url
