from f1pred.config import MAX_RELIABLE_LIFE, PIT_LOSS_S


def lap_delta(deg: dict, compound: str, tyre_life: int) -> float:
    d = deg[compound]
    return d["offset"] + d["slope"] * (tyre_life - 1)


def race_time(deg, current_lap, total_laps, compound, tyre_life,
              pit_lap=None, new_compound=None, pit_loss_s=PIT_LOSS_S) -> float:
    total = 0.0
    for lap in range(current_lap, total_laps + 1):
        if pit_lap is not None and lap > pit_lap:
            total += lap_delta(deg, new_compound, lap - pit_lap)
        else:
            total += lap_delta(deg, compound, tyre_life + lap - current_lap)
    return total + (pit_loss_s if pit_lap is not None else 0.0)


def best_windows(deg, current_lap, total_laps, compound, tyre_life,
                 new_compound, pit_loss_s=PIT_LOSS_S) -> dict:
    laps = range(current_lap, total_laps - 3)
    if len(laps) == 0:
        raise ValueError("Za mało okrążeń do końca wyścigu, by planować zjazd")

    no_stop = race_time(deg, current_lap, total_laps, compound, tyre_life)
    results = {
        lap: race_time(deg, current_lap, total_laps, compound, tyre_life,
                       pit_lap=lap, new_compound=new_compound, pit_loss_s=pit_loss_s)
        for lap in laps
    }
    ranked = sorted(results.items(), key=lambda kv: kv[1])
    best_lap, best_time = ranked[0]

    warnings = []
    no_stop_age = tyre_life + total_laps - current_lap
    if no_stop_age > MAX_RELIABLE_LIFE:
        warnings.append(
            f"Scenariusz bez zjazdu zakłada oponę {compound} w wieku {no_stop_age} okr. "
            f"(dane do ok. {MAX_RELIABLE_LIFE}), więc zysk ze zjazdu jest zawyżony."
        )
    new_age = total_laps - best_lap
    if new_age > MAX_RELIABLE_LIFE:
        warnings.append(f"Nowa opona {new_compound} przejedzie {new_age} okr., powyżej zakresu danych.")

    return {
        "best_pit_lap": best_lap,
        "pit_now": best_lap == current_lap,
        "delta_vs_no_stop_s": best_time - no_stop, 
        "top_windows": [{"lap": l, "delta_vs_no_stop_s": t - no_stop} for l, t in ranked[:5]],
        "warnings": warnings,
    }