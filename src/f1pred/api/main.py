import json

from fastapi import FastAPI, HTTPException

from f1pred import strategy
from f1pred.api.schemas import PitRequest
from f1pred.config import DEGRADATION_PATH

app = FastAPI(title="F1 Tyre Degradation API")

with open(DEGRADATION_PATH) as f:
    _cfg = json.load(f)
DEG = _cfg["compounds"]


def _check(compound: str):
    if compound not in DEG:
        raise HTTPException(400, f"Nieznana mieszanka '{compound}', dostępne: {list(DEG)}")


@app.get("/degradation")
def degradation():
    return {"lap_trend_s_per_lap": _cfg["lap_trend_s_per_lap"], "compounds": DEG}


@app.get("/predict")
def predict(compound: str, tyre_life: int):
    _check(compound)
    return {"delta_s": strategy.lap_delta(DEG, compound, tyre_life)}


@app.post("/pit-window")
def pit_window(r: PitRequest):
    _check(r.current_compound)
    _check(r.new_compound)
    try:
        return strategy.best_windows(DEG, r.current_lap, r.total_laps, r.current_compound,
                                     r.current_tyre_life, r.new_compound, r.pit_loss_s)
    except ValueError as e:
        raise HTTPException(400, str(e))