import pandas as pd
from sqlalchemy import create_engine

from f1pred.config import DATABASE_URL

DRY_COMPOUNDS = ["SOFT", "MEDIUM", "HARD"]


def load_dry_laps() -> pd.DataFrame:
    """Okrążenia z bazy: tylko opony na suchy tor, bez wyścigów mokrych."""
    df = pd.read_sql("SELECT * FROM laps", create_engine(DATABASE_URL))
    df = df[df["compound"].isin(DRY_COMPOUNDS)].copy()
    df["race_rain"] = df["wet_race"] | df.groupby(["year", "gp"])["rainfall"].transform("any")
    return df[~df["race_rain"]].copy()