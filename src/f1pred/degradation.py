import json 
import os
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from f1pred.features import load_dry_laps
from f1pred.config import DEGRADATION_PATH

df=load_dry_laps()

df["race"] = df["year"].astype(str) + "_" + df["gp"]
df["key"] = df["race"] + "_" + df["driver"]

med = df.groupby("key")["lap_time_s"].transform("median")
df = df[(df["lap_time_s"] - med).abs() < 4].copy()
df = df[df.groupby("key")["lap_time_s"].transform("size") >= 20].copy()
df = df.reset_index(drop=True)

# regresory: offset mieszanki (HARD = punkt odniesienia), nachylenie per mieszanka, trend okrążeń
df["t0"] = df["tyre_life"] - 1  # offset = tempo świeżej opony (wiek 1)
for c in ("SOFT", "MEDIUM"):
    df[f"d_{c}"] = (df["compound"] == c).astype(float)
for c in ("SOFT", "MEDIUM", "HARD"):
    df[f"s_{c}"] = df["t0"] * (df["compound"] == c)
COLS = ["d_SOFT", "d_MEDIUM", "s_SOFT", "s_MEDIUM", "s_HARD", "lap_number"]

grp = df.groupby("key")
X = (df[COLS].astype(float) - grp[COLS].transform("mean")).to_numpy()
y = (df["lap_time_s"] - grp["lap_time_s"].transform("mean")).to_numpy()


def fit(ix=None):
    Xs, ys = (X, y) if ix is None else (X[ix], y[ix])
    return np.linalg.lstsq(Xs, ys, rcond=None)[0]


beta = fit()

rng = np.random.default_rng(0)
by_race = df.groupby("race").indices
races = list(by_race)
boots = np.array([
    fit(np.concatenate([by_race[r] for r in rng.choice(races, len(races))]))
    for _ in range(200)
])
lo, hi = np.percentile(boots, [5, 95], axis=0)

names = ["offset SOFT vs HARD", "offset MEDIUM vs HARD", "degradacja SOFT",
         "degradacja MEDIUM", "degradacja HARD", "trend na okrążenie (paliwo+tor)"]
print(f"Okrążeń: {len(df)}, wyścigów: {len(races)}, par kierowca-wyścig: {df['key'].nunique()}")
for n, b, l, h in zip(names, beta, lo, hi):
    print(f"{n:34s} {b:+.3f} s   [90%: {l:+.3f}, {h:+.3f}]")
d = boots[:,3] - boots[:,4]
print(f"roznica degradacji MEDIUM-HARD   {beta[3] - beta[4]:+.3f} s "
      f"[90%: {np.percentile(d,5):+.3f}, {np.percentile(d,95):+.3f}]")

DEGRADATION_PATH.parent.mkdir(exist_ok=True)
out = {
    "lap_trend_s_per_lap": float(beta[5]),
    "compounds": {
        "HARD": {"slope": float(beta[4]), "offset": 0.0},
        "MEDIUM": {"slope": float(beta[3]), "offset": float(beta[1])},
        "SOFT": {"slope": float(beta[2]), "offset": float(beta[0])},
    },
}
with open(DEGRADATION_PATH, "w") as f:
    json.dump(out, f, indent=2)
print("Zapisano models/degradation.json")