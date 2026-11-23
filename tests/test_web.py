import tomllib

from aviaopromax import config
from aviaopromax.providers import MockProvider
from aviaopromax.web import App, apply_form, save_config


def test_apply_form_parses_codes():
    cfg = apply_form(config.Config(), {"destinations": "lis, mad cun", "months": "2027-01"})
    assert cfg.destinations == ["LIS", "MAD", "CUN"]
    assert cfg.months == ["2027-01"]


def test_save_config_roundtrip(tmp_path):
    p = tmp_path / "config.toml"
    cfg = config.Config(origin="BOS", destinations=["LIS"], max_price=350, direct_only=True)
    save_config(cfg, p)
    tomllib.loads(p.read_text())
    loaded = config.load(p)
    assert loaded.destinations == ["LIS"] and loaded.max_price == 350 and loaded.direct_only


def test_search_mock_direct_only(tmp_path):
    app = App(tmp_path / "config.toml", str(tmp_path / "p.db"))
    out = app.search({"mock": True, "max_price": 500, "direct_only": True})
    assert out["results"]
    assert all(r["transfers"] == 0 for r in out["results"])


def test_mock_direct_only_default():
    offers = MockProvider(seed=1).search(config.Config())
    assert all(o.transfers == 0 for o in offers)


def test_rejects_unknown_airport(tmp_path):
    import pytest
    app = App(tmp_path / "config.toml", str(tmp_path / "p.db"))
    with pytest.raises(ValueError, match="XXX"):
        app.search({"mock": True, "destinations": ["XXX"]})


def test_exact_dates_filter(tmp_path):
    app = App(tmp_path / "config.toml", str(tmp_path / "p.db"))
    out = app.search({
        "mock": True, "destinations": ["LIS", "MAD"],
        "depart_from": "2027-01-10", "depart_to": "2027-01-12",
        "return_from": "2027-01-20", "return_to": "2027-01-25",
    })
    assert out["months"] == ["2027-01"]
    assert len(out["results"]) == 2
    for r in out["results"]:
        assert "2027-01-10" <= r["depart"] <= "2027-01-12"
        assert "2027-01-20" <= r["ret"] <= "2027-01-25"


def test_return_before_depart_rejected(tmp_path):
    import pytest
    app = App(tmp_path / "config.toml", str(tmp_path / "p.db"))
    with pytest.raises(ValueError, match="volta"):
        app.search({"mock": True, "depart_from": "2027-02-10", "return_from": "2027-02-01"})


def test_save_token_persists_and_hides(tmp_path, monkeypatch):
    from aviaopromax import providers
    monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)
    monkeypatch.setattr(providers.TravelpayoutsProvider, "_get", lambda self, params: [])
    app = App(tmp_path / "config.toml", str(tmp_path / "p.db"))
    assert app.get_config()["has_token"] is False
    out = app.save_token({"token": "  abc123  "})
    assert out["has_token"] is True and "travelpayouts_token" not in out
    assert config.load(tmp_path / "config.toml").travelpayouts_token == "abc123"
    app.save({"max_price": 300})  # salvar outras opções mantém o token
    assert config.load(tmp_path / "config.toml").travelpayouts_token == "abc123"
