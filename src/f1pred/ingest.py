import os 
import fastf1
import traceback
import pandas as pd
import time
from sqlalchemy import create_engine , inspect, text
from f1pred.config import CACHE_DIR, DATABASE_URL, SEASONS

CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))
engine = create_engine(DATABASE_URL)

def load_race(year:int, gp:str)->pd.DataFrame:
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, weather=True, telemetry=False, messages=False)
    if not hasattr(session, "_laps"):
        raise RuntimeError("brak danych (sprawdź logowanie: python -m fastf1 auth f1tv --status)")

    wet_race = bool(session.laps["Compound"].isin(["INTERMEDIATE", "WET"]).any())
    laps = session.laps.pick_quicklaps().pick_wo_box()
    laps = laps.pick_track_status("1", how="equals")
    weather = laps.get_weather_data().reset_index(drop=True)
    laps = laps.reset_index(drop=True)

    df = pd.DataFrame({
        "year": year,
        "gp": gp,
        "driver" : laps["Driver"],
        "team" : laps["Team"],
        "stint" : laps["Stint"],
        "lap_number" : laps["LapNumber"],
        "compound" : laps["Compound"],
        "tyre_life" : laps["TyreLife"],
        "lap_time_s" : laps["LapTime"].dt.total_seconds(),
        "track_temp" : weather["TrackTemp"],
        "air_temp" : weather["AirTemp"],
        "wet_race" : wet_race,
        "rainfall" : weather["Rainfall"].astype(bool),

        })
    
    return df.dropna()

def load_with_retry(year:int, gp:str, max_waits:int = 6) -> pd.DataFrame:
    for attempt in range(max_waits + 1):
        try:
            return load_race(year, gp)
        except Exception as e:
            if "calls/h" in str(e) and attempt < max_waits:
                print(f"LIMIT {year} {gp} : czekam 10 minut ({attempt+1}/{max_waits})")
                time.sleep(600)
                continue 
            raise

def already_loaded()->set:
    if not inspect(engine).has_table("laps"):
        return set()
    with engine.connect() as c:
        rows = c.execute(text("SELECT DISTINCT year, gp FROM laps")).fetchall()
    return {(int(y), g) for y,g in rows}


if __name__ == "__main__":
    done = already_loaded()
    for year in SEASONS:
        schedule = fastf1.get_event_schedule(year, include_testing= False)
        for gp in schedule["EventName"]:
            if (year, gp) in done :
                continue
            try:
                df= load_with_retry(year,gp)
                df.to_sql("laps", engine, if_exists="append", index=False)
                print(f"OK {year} {gp} : {len(df)}")
            except Exception as e:
                print(f"SKIP {year} {gp} : {e}")
                print("".join(traceback.format_exc().splitlines(keepends=True)[-4:]))