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
