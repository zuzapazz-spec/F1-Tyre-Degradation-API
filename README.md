# F1 Tyre Degradation & Pit Window API

Projekt szacuje degradację opon w Formule 1 na podstawie danych z wyścigów 2023-2025 i wstawia przez REST API (FastAPI) rekomendację okna zjazdu do alei serwisowej.

>Projekt hobbystyczny, niezwiązany z Formula 1 ani FIA.

## Wyniki 
Dane: 59 suchych wyścigów, 1088 par kierowca-wyścig, 53 101 okrążeń. 
Model : regresja liniowa z efektami stałymi kierowca-wyścig (mieszanka HARD jako odniesienie), przedziały 90% z bootstrapu po wyścigu (200 prób).

| Mieszanka | Degradacja [s/okr.] | 90% CI | Tempo świeżej opony vs HARD [s] | 90% CI |
|-----------|--------------------:|--------|--------------------------------:|--------|
| SOFT      | +0.056 | [0.049, 0.065] | -0.280 | [-0.394, -0.143] |
| MEDIUM    | +0.042 | [0.035, 0.047] | -0.017 | [-0.120, +0.098] |
| HARD      | +0.033 | [0.027, 0.039] | 0 (odniesienie) | - |


Trend czasu okrążenia (ubywające paliwo + gumowanie toru): -0.048 s/okr.
-SOFT wyraźnie odróżnia się od HARD zarówno tempem, jak i degradacją.
-MEDIUM zużywa się nieco szybciej niż HARD (różnica +0.009 s/okr.,
90% CI [0.001, 0.016]), ale efekt jest mały i na granicy istotności.
Tempo świeżej opony MEDIUM jest nierozróżnialne od HARD (CI offsetu obejmuje zero).

## Jak to dziła
1.**Dane** (`ingest.py`): FastF1 → czyszczenie ('pick_quicklaps', bez okrążeń zjazdowych, tylko zielona flaga) → PostgreSQL.
2.**Filtr**: wyścigi mokre (opony INTERMEDIATE/WET lub deszcz w danych pogodowych) są wykluczone, bo wysychający tor zaburza degradację.
3.**Model** (`degradation.py`): regresja z efektami stałymi kierowca-wyścig rozdziela zużycie opon od tempa kierowcy, toru i ubywającego paliwa.
4.**Strategia** (`strategy.py`): dla każdego okrążenia zjazdu sumuje przewidziane czasy okrążeń, dodaje stratę na zjazd i dobiera najlepsze okno.
5.**API** (`api/main.py`): FastAPI.

## Uruchomienie 
Wymagany Python 3.10+ (FastF1 3.9 nie działa na starszych).
 ```bash
 python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Pobieranie danych 
Od października 2026 FastF1 wymaga logowania kontem F1 TV (Access lub wyższy) przy pobieraniu danych:

```bash
python -m fastf1 auth f1tv --authenticate
docker compose up -d db
export PYTHONPATH=src
python -m f1pred.ingest        # limit FastF1: 500 zapytań/h, skrypt czeka i ponawia
python -m f1pred.degradation   # liczy model i zapisuje models/degradation.json
```
Gotowy `models/degradation.json` jest repo, więc samo API można uruchomić bez pobierania danych.

### API 


```bash
export PYTHONPATH=src
uvicorn f1pred.api.main:app --reload
```

Dokumentacja interaktywna: http://localhost:8000/docs

| Endpoint | Opis |
|----------|------|
| `GET /degradation` | współczynniki degradacji dla każdej mieszanki |
| `GET /predict?compound=SOFT&tyre_life=10` | przewidziane odchylenie czasu okrążenia [s] |
| `POST /pit-window` | najlepsze okno zjazdu |

Przykład:

```bash
curl -X POST http://localhost:8000/pit-window -H "Content-Type: application/json" -d '{
  "current_lap": 15, "total_laps": 57,
  "current_compound": "MEDIUM", "current_tyre_life": 15,
  "new_compound": "HARD"
}'
```

Odpowiedź (skrócona):

```json
{
  "best_pit_lap": 25,
  "pit_now": false,
  "delta_vs_no_stop_s": -16.18,
  "top_windows": [{"lap": 25, "delta_vs_no_stop_s": -16.18}],
  "warnings": ["Scenariusz bez zjazdu zakłada oponę MEDIUM w wieku 57 okr. ..."]
}
```
`delta_vs_no_stop_s` ujemne = zjazd się opłaca. Ostrzeżenia informują, że wynik
opiera się na ekstrapolacji (patrz Ograniczenia).
### Testy

```bash
python -m pytest -q
```

## Struktura

```
src/f1pred/
├── config.py        # ścieżki, stałe
├── ingest.py        # FastF1 -> PostgreSQL
├── features.py      # wczytanie i filtrowanie danych
├── degradation.py   # model degradacji (regresja + bootstrap)
├── strategy.py      # logika okna zjazdu
├── train.py         # eksperyment: globalny XGBoost (patrz niżej)
└── api/             # FastAPI (main.py, schemas.py)
tests/               # pytest
models/degradation.json
```

## Droga do rozwiązania 
Pierwsze podejście to globalny model XGBoost przewidujący odchylenie czasu okrążenia od tempa kierowcy. Miał MAE 0.49 s wobec 0.75 s dla baseline'u (walidacja po wyścigach, `GroupKFold`, ale nie rozdzielał zużycia opon od paliwa i dawał niemal identyczne krzywe dla wszystkich mieszanek. W efekcie `/pit-window` twierdził, że zjazd nigdy się nie opłacał. Zastąpiła go regresja z efektami stałymi, a XBGoost został w repo jako eksperyment (`train.py`).

## Ograniczenia 
- Degradacja jest liniowa i szacowana ze stentów do ok.35 okrążeń. Powyżej tego zakresu wynik to ekstrapolacja, a API zwraca ostrzeżenie. Model nie widzi "klifu", czyli nagłej utraty przyczepności starych opon.
- Współczynniki są uśrednione po wszystkich torach, a degradacja silnie zależy od tego toru.
- Błąd selekcji: opony zużywające się szybko raczej rzadziej jeżdżą długie stenty, więc nachylenia mogą być niedoszacowane.
- Strata na zjazd jest stała (21 s) i niezależna od toru. Brak safety carów, ruchu na torze i obowiązku użycia dwóch mieszanek.
- Różnica MEDIUM-HARD jest mała i na granicy istotności statystycznej.

## Dane 

Dane pobierane przez bibliotekę [FastF1] (https://github.com/theOehrly/Fast-F1).
Surowe dane nie są częścią repozytorium. Użytkownik pobiera je samodzielnie.
