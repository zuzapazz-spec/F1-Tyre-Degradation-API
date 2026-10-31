import os

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import create_engine
from xgboost import XGBRegressor

engine = create_engine(
    os.environ.get("DATABASE_URL", "postgresql+psycopg2://f1:f1@localhost:5432/f1")
)
df = pd.read_sql("SELECT * FROM laps", engine)
df = df[df["compound"].isin(["SOFT", "MEDIUM", "HARD"])].copy()

# wyścigi z oponami na mokre lub deszczem
df["race_rain"] = df["wet_race"] | df.groupby(["year", "gp"])["rainfall"].transform("any")
df = df[~df["race_rain"]].copy()

# cel: odchylenie od mediany kierowcy w tym wyścigu
df["driver_median"] = df.groupby(["year", "gp", "driver"])["lap_time_s"].transform("median")
df["delta_s"] = df["lap_time_s"] - df["driver_median"]
df = df[df["delta_s"].abs() < 5].copy()

# paliwo: ile okrążeń zostało do końca
df["total_laps"] = df.groupby(["year", "gp"])["lap_number"].transform("max")
df["laps_remaining"] = df["total_laps"] - df["lap_number"]

NUM = ["tyre_life", "lap_number", "laps_remaining", "track_temp", "air_temp"]
GP_CATS = sorted(df["gp"].unique())
# 1 = wartość rośnie => delta nie maleje: wiek opony i paliwo (laps_remaining)
MONO = "(" + ",".join(map(str, [1, 0, 1, 0, 0] + [0] * len(GP_CATS))) + ")"
FEATURES = ["gp"] + NUM


def make(model):
    prep = ColumnTransformer([
        ("num", "passthrough", NUM),
        ("gp", OneHotEncoder(categories=[GP_CATS], handle_unknown="ignore"), ["gp"]),
    ])
    return Pipeline([("prep", prep), ("model", model)])


def new_xgb():
    return make(XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8,
                             monotone_constraints=MONO))


df["group"] = df["year"].astype(str) + "_" + df["gp"]
cv = GroupKFold(5)

# baseline na całości
s = cross_val_score(make(DummyRegressor(strategy="mean")), df[FEATURES], df["delta_s"],
                    cv=cv, groups=df["group"], scoring="neg_mean_absolute_error")
print(f"baseline (srednia): MAE delty = {-s.mean():.3f} s")

# walidacja po wyścigach, osobno dla każdej mieszanki, wyniki zsumowane
oof = pd.Series(index=df.index, dtype=float)
for comp in ["SOFT", "MEDIUM", "HARD"]:
    d = df[df["compound"] == comp]
    oof[d.index] = cross_val_predict(new_xgb(), d[FEATURES], d["delta_s"],
                                     cv=cv, groups=d["group"])
print(f"XGBoost (per mieszanka): MAE delty = {(df['delta_s'] - oof).abs().mean():.3f} s")

# finalne modele + kontrola nachylenia degradacji (wiek 5 vs 25, to samo okrążenie)
models = {}
for comp in ["SOFT", "MEDIUM", "HARD"]:
    d = df[df["compound"] == comp]
    models[comp] = new_xgb().fit(d[FEATURES], d["delta_s"])
    rows = pd.DataFrame([dict(gp="Bahrain Grand Prix", tyre_life=t, lap_number=35,
                              laps_remaining=22, track_temp=35.0, air_temp=26.0)
                         for t in (5, 25)])
    p = models[comp].predict(rows[FEATURES])
    print(f"{comp}: degradacja {(p[1] - p[0]) / 20:+.3f} s/okr. (okrążeń: {len(d)})")

os.makedirs("models", exist_ok=True)
joblib.dump(models, "models/tyre_model.joblib")
print("Zapisano models/tyre_model.joblib")