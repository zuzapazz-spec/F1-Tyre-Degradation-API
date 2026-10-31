from fastapi.testclient import TestClient

from f1pred.api.main import DEG, app
from f1pred.strategy import lap_delta as _lap_delta

client = TestClient(app)


BASE = {
    "current_lap": 30,
    "total_laps": 57,
    "current_compound": "MEDIUM",
    "current_tyre_life": 30,
    "new_compound": "HARD",
}

def lap_delta(compound, tyre_life):
    return _lap_delta(DEG, compound, tyre_life)


def test_delta_grows_with_tyre_age():
    assert lap_delta("SOFT", 20) > lap_delta("SOFT", 5)


def test_soft_degrades_faster_than_hard():
    soft = lap_delta("SOFT", 20) - lap_delta("SOFT", 1)
    hard = lap_delta("HARD", 20) - lap_delta("HARD", 1)
    assert soft > hard


def test_soft_is_faster_when_fresh():
    assert lap_delta("SOFT", 1) < lap_delta("HARD", 1)


def test_unknown_compound_returns_400():
    r = client.post("/pit-window", json={**BASE, "current_compound": "XXX"})
    assert r.status_code == 400


def test_old_tyres_pit_is_beneficial():
    r = client.post("/pit-window", json=BASE)
    assert r.status_code == 200
    body = r.json()
    assert body["delta_vs_no_stop_s"] < 0
    assert body["pit_now"] is True


def test_extrapolation_warning():
    r = client.post("/pit-window", json=BASE)
    assert r.json()["warnings"]  # wiek bez zjazdu = 57 okr. > 35


def test_huge_pit_loss_means_no_benefit():
    r = client.post("/pit-window", json={**BASE, "pit_loss_s": 200})
    assert r.json()["delta_vs_no_stop_s"] > 0

def test_too_late_to_plan_returns_400():
    r = client.post("/pit-window", json={**BASE, "current_lap": 55, "current_tyre_life": 20})
    assert r.status_code == 400