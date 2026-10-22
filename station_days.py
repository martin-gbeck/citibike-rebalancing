"""How far each station's stock swings on each service day, from the 5-minute counts.

`drift` is the bikes a station has gained since 04:00, added up slot by slot. For each station
and day this writes the lowest and highest drift over the whole day, and over the rest of the day
from each candidate midday visit hour, measured from the stock at that hour. Together with the
docks they say which starting levels would have carried the station through the day.

Writes data/processed/station_days.parquet; reads one month of slots at a time (about 1 GB).
"""

import os

os.environ["POLARS_MAX_THREADS"] = "6"

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from lib.rebalancing import load_day_slots, slot_of_hour

PROCESSED = Path("data/processed")
FIRST_DAY, LAST_DAY = date(2024, 10, 1), date(2026, 9, 29)
# hours a van could visit between the rushes, or before the evening one
MIDDAY_HOURS = [10, 12, 14]

stations = pl.read_parquet(PROCESSED / "stations.parquet")
station_ids = stations["station_id"].to_list()

pieces: list[pl.DataFrame] = []
month_first = FIRST_DAY
while month_first <= LAST_DAY:
    next_month = (month_first.replace(day=28) + timedelta(days=4)).replace(day=1)
    days = (min(next_month, LAST_DAY + timedelta(days=1)) - month_first).days
    starts, ends = load_day_slots(PROCESSED / "bins", station_ids, month_first, days)
    drift = np.cumsum(ends.astype(np.int32) - starts, axis=2)
    columns: dict[str, np.ndarray] = {
        "starts": starts.sum(axis=2),
        "ends": ends.sum(axis=2),
        "drift_min": np.minimum(drift.min(axis=2), 0),
        "drift_max": np.maximum(drift.max(axis=2), 0),
        "drift_end": drift[:, :, -1],
    }
    for hour in MIDDAY_HOURS:
        slot = slot_of_hour(hour)
        rest = drift[:, :, slot:] - drift[:, :, slot - 1 : slot]
        columns[f"rest_min_{hour}"] = np.minimum(rest.min(axis=2), 0)
        columns[f"rest_max_{hour}"] = np.maximum(rest.max(axis=2), 0)
    day_list = [month_first + timedelta(days=offset) for offset in range(days)]
    pieces.append(
        pl.DataFrame(
            {
                "station_id": np.repeat(station_ids, days),
                "service_day": day_list * len(station_ids),
                **{name: values.ravel() for name, values in columns.items()},
            }
        )
    )
    print(month_first, flush=True)
    month_first = next_month

# a station counts as open from the first day it had a trip to the last
station_days = (
    pl.concat(pieces)
    .with_columns(trips=pl.col("starts") + pl.col("ends"))
    .with_columns(
        is_open=pl.col("service_day").is_between(
            pl.col("service_day").filter(pl.col("trips") > 0).min().over("station_id"),
            pl.col("service_day").filter(pl.col("trips") > 0).max().over("station_id"),
        )
    )
    .filter(pl.col("is_open"))
    .drop("is_open")
)
station_days.write_parquet(PROCESSED / "station_days.parquet")
print(station_days.shape)
