# %% [markdown]
# # Simulating rebalancing schedules on two years of real trips
# Every trip of a year is replayed, in 5-minute slots, through every station with known docks,
# once per schedule. A schedule sets each station's stock at 04:00 and, optionally, again at one
# midday hour; riders who find their station empty or full are counted as shortages.
#
# `python rebalance.py dev` compares settings on the development year (November 2024 to
# September 2025, October being the first history); `python rebalance.py test` scores the chosen
# schedules once on the test year (October 2025 to September 2026). Each writes
# `data/processed/simulation-<year>.npz`.

# %%
import os

os.environ["POLARS_MAX_THREADS"] = "6"

import sys
import warnings
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Literal

import numpy as np
import polars as pl

from lib.rebalancing import (
    HOLIDAYS,
    SLOTS_PER_DAY,
    expected_shortages,
    load_day_slots,
    shortage_table,
    simulate_slots,
    slot_of_hour,
    spend_budget,
    target_band,
)

# stations without history give all-nan rows, whose means are nan on purpose
np.seterr(invalid="ignore")
warnings.filterwarnings("ignore", "Mean of empty slice")

PROCESSED = Path("data/processed")
FIRST_DAY, LAST_DAY = date(2024, 10, 1), date(2026, 9, 29)
YEARS = {
    "dev": (date(2024, 11, 1), date(2025, 9, 30)),
    "test": (date(2025, 10, 1), date(2026, 9, 29)),
}


@dataclass(frozen=True)
class Policy:
    """One rebalancing schedule.

    overnight: what happens at 04:00. `none` moves nothing; `half` sets every open station to half
    its docks; `band` moves a station only if its stock is outside its target band, and only to
    the nearest edge; `budget` spends at most `budget` bikes on the moves that prevent the most
    expected shortages; `oracle` uses the band of the day itself, known in advance, as the bound
    no forecast can beat.
    history_days: how many past days of the same type (workday, or weekend and holiday) the band
    is drawn from. scaled: stretch those days' swings by tomorrow's forecast volume over theirs.
    midday_hour, midday_stations: a second visit at that hour to the stations where moving to
    the band for the rest of the day prevents the most expected shortages.
    """

    name: str
    overnight: Literal["none", "half", "band", "budget", "oracle"]
    history_days: int = 10
    scaled: bool = False
    budget: int = 0
    midday_hour: int | None = None
    midday_stations: int = 0
    family: str = field(default="", compare=False)


year = sys.argv[1] if len(sys.argv) > 1 else "dev"
# bikes loaded or unloaded per night for the budget rule, and stations visited at midday
BUDGETS = (250, 500, 1000, 2000, 3000, 4000, 6000, 9000)
MIDDAY_STATIONS = (25, 50, 100, 200, 400)


def common_policies(days: int, scaled: bool) -> list[Policy]:
    """The schedules both years run: the two simple rules, the band, the oracle and the budget sweep."""
    return [
        Policy("none", "none", family="no rebalancing"),
        Policy("half", "half", family="reset to half"),
        Policy("band", "band", history_days=days, scaled=scaled, family="band"),
        Policy("oracle", "oracle", family="oracle"),
        *[
            Policy(
                f"budget-{bikes}",
                "budget",
                history_days=days,
                scaled=scaled,
                budget=bikes,
                family="budget",
            )
            for bikes in BUDGETS
        ],
    ]


def midday_policies(days: int, budget: int, hour: int) -> list[Policy]:
    """The budget rule at night plus a visit at `hour` to a growing number of stations."""
    return [
        Policy(
            f"budget-{budget}-midday-{hour}-{stations}",
            "budget",
            history_days=days,
            budget=budget,
            midday_hour=hour,
            midday_stations=stations,
            family=f"budget {budget} + midday {hour}:00",
        )
        for stations in MIDDAY_STATIONS
    ]


if year == "dev":
    policies = [
        *common_policies(10, False),
        *[
            Policy(f"band-{days}", "band", history_days=days, family="band by history")
            for days in (3, 5, 20, 40)
        ],
        *[
            Policy(
                f"band-{days}-scaled",
                "band",
                history_days=days,
                scaled=True,
                family="band scaled",
            )
            for days in (5, 10, 20)
        ],
        *[
            Policy(
                f"band-midday-{hour}",
                "band",
                midday_hour=hour,
                midday_stations=100,
                family="band + midday",
            )
            for hour in (10, 12, 14)
        ],
        *midday_policies(10, 2000, 14),
        *midday_policies(10, 3000, 14),
    ]
else:
    # chosen on the development year (its printout): 10 days of history (20 cut shortages 1% for 11%
    # more bikes), no volume scaling (more shortages for more bikes at every length), a nightly
    # budget of 3,000 bikes loaded or unloaded (fewest shortages of the sweep), the visit at 14:00
    # (fewer shortages than 10:00 or 12:00)
    policies = [*common_policies(10, False), *midday_policies(10, 3000, 14)]

# %% [markdown]
# Stations with a known number of docks, and their daily swings as [station, day] arrays.
# `need`: bikes the station needed at 04:00 never to run empty that day; `room`: the most it
# could hold at 04:00 never to fill up.

# %%
stations = (
    pl.read_parquet(PROCESSED / "stations.parquet")
    .drop_nulls("capacity")
    .sort("station_id")
)
station_ids = stations["station_id"].to_list()
capacity = stations["capacity"].to_numpy().astype(np.int32)
calendar = pl.date_range(FIRST_DAY, LAST_DAY, eager=True).to_list()
day_index = {day: i for i, day in enumerate(calendar)}

station_days = (
    pl.read_parquet(PROCESSED / "station_days.parquet")
    .filter(pl.col("station_id").is_in(station_ids))
    .with_columns(
        row=pl.col("station_id").replace_strict(
            station_ids, list(range(len(station_ids)))
        ),
        column=pl.col("service_day").replace_strict(
            calendar, list(range(len(calendar)))
        ),
    )
)


def as_grid(column: str) -> np.ndarray:
    """One station_days column as a float [station, day] array, nan where the station was closed."""
    grid = np.full((len(station_ids), len(calendar)), np.nan, dtype=np.float32)
    grid[station_days["row"].to_numpy(), station_days["column"].to_numpy()] = (
        station_days[column].to_numpy()
    )
    return grid


drift_min, drift_max = as_grid("drift_min"), as_grid("drift_max")
rest_grids = {
    hour: (as_grid(f"rest_min_{hour}"), as_grid(f"rest_max_{hour}"))
    for hour in (10, 12, 14)
}
is_open = ~np.isnan(drift_min)
trips_per_day = np.nansum(as_grid("starts") + as_grid("ends"), axis=0) / 2

demand = pl.read_parquet(PROCESSED / "daily_demand.parquet")
actual_volume = np.full(len(calendar), np.nan)
predicted_volume = np.full(len(calendar), np.nan)
for row in demand.filter(pl.col("date").is_in(calendar)).iter_rows(named=True):
    actual_volume[day_index[row["date"]]] = row["trips"]
    predicted_volume[day_index[row["date"]]] = row["predicted"]

is_workday = np.array([day.weekday() < 5 and day not in HOLIDAYS for day in calendar])
# for each day, the earlier days of the same type, most recent first
same_type_before = [
    np.array(
        [j for j in range(i - 1, -1, -1) if is_workday[j] == is_workday[i]],
        dtype=np.int64,
    )
    for i in range(len(calendar))
]
half_full = np.round(capacity / 2)


def history(
    day: int, days: int, scaled: bool, low_drift: np.ndarray, high_drift: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """`need` and `room` [station, past day] over the last `days` days of the same type as `day`.

    `low_drift` and `high_drift` are the lowest and highest drift grids to draw from (whole day, or
    rest of the day from a midday hour). With `scaled`, each past day's swings are stretched by
    the forecast volume of `day` over that day's actual volume.
    """
    past = same_type_before[day][:days]
    low, high = low_drift[:, past], high_drift[:, past]
    if scaled and len(past):
        stretch = predicted_volume[day] / actual_volume[past]
        stretch = np.where(np.isfinite(stretch), stretch, 1.0)[None, :]
        low, high = low * stretch, high * stretch
    return -low, capacity[:, None] - high


# %% [markdown]
# ## The simulation
# All schedules run side by side: `stock` is [policy, station].

# %%
first_day, last_day = YEARS[year]
eval_days = [day for day in calendar if first_day <= day <= last_day]
policy_count, station_count = len(policies), len(station_ids)
stock = np.repeat(half_full[None, :], policy_count, axis=0).astype(np.int32)

empty_by_day = np.zeros((policy_count, len(eval_days)), dtype=np.int64)
full_by_day = np.zeros_like(empty_by_day)
pickups_by_day = np.zeros_like(empty_by_day)
dropoffs_by_day = np.zeros_like(empty_by_day)
midday_moves_by_day = np.zeros_like(empty_by_day)
shortages_by_station = np.zeros((policy_count, station_count), dtype=np.int64)
bikes_in_by_station = np.zeros_like(shortages_by_station)
bikes_out_by_station = np.zeros_like(shortages_by_station)
shortages_by_slot = np.zeros((policy_count, SLOTS_PER_DAY), dtype=np.int64)
stock_before_move = np.zeros(
    (policy_count, station_count, len(eval_days)), dtype=np.int16
)
stock_after_move = np.zeros_like(stock_before_move)
band_low = np.full((station_count, len(eval_days)), np.nan, dtype=np.float32)
band_high = np.full_like(band_low, np.nan)
midday_slots = sorted(
    {slot_of_hour(policy.midday_hour) for policy in policies if policy.midday_hour}
)

month_first = first_day
while month_first <= last_day:
    next_month = (month_first.replace(day=28) + timedelta(days=4)).replace(day=1)
    block_days = (min(next_month, last_day + timedelta(days=1)) - month_first).days
    starts, ends = load_day_slots(
        PROCESSED / "bins", station_ids, month_first, block_days
    )
    for offset in range(block_days):
        day = day_index[month_first + timedelta(days=offset)]
        eval_i = eval_days.index(calendar[day])
        open_today = is_open[:, day]
        bands: dict[
            tuple[int, bool], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
        ] = {}
        tables: dict[tuple[int, bool], np.ndarray] = {}

        # overnight, at 04:00
        new_stock = stock.copy()
        for p, policy in enumerate(policies):
            key = (policy.history_days, policy.scaled)
            if policy.overnight in ("band", "budget") and key not in bands:
                need, room = history(day, *key, drift_min, drift_max)
                bands[key] = (*target_band(need, room), need, room)
            if policy.overnight == "half":
                new_stock[p] = np.where(open_today, half_full, stock[p])
            elif policy.overnight == "band":
                low, high, _, _ = bands[key]
                low, high = (
                    np.where(np.isnan(low), half_full, low),
                    np.where(np.isnan(high), half_full, high),
                )
                new_stock[p] = np.where(
                    open_today, np.clip(stock[p], low, high), stock[p]
                )
            elif policy.overnight == "budget":
                low, high, need, room = bands[key]
                if key not in tables:
                    tables[key] = shortage_table(need, room, int(capacity.max()) + 1)
                moved = spend_budget(stock[p], low, high, tables[key], policy.budget)
                new_stock[p] = np.where(open_today, moved, stock[p])
            elif policy.overnight == "oracle":
                low, high = target_band(
                    -drift_min[:, day : day + 1],
                    capacity[:, None] - drift_max[:, day : day + 1],
                )
                new_stock[p] = np.where(
                    open_today, np.clip(stock[p], low, high), stock[p]
                )
        if (10, False) in bands:
            band_low[:, eval_i], band_high[:, eval_i] = bands[(10, False)][:2]
        moves = new_stock - stock
        stock_before_move[:, :, eval_i] = stock
        stock_after_move[:, :, eval_i] = new_stock
        pickups_by_day[:, eval_i] = np.maximum(-moves, 0).sum(axis=1)
        dropoffs_by_day[:, eval_i] = np.maximum(moves, 0).sum(axis=1)
        bikes_in_by_station += np.maximum(moves, 0)
        bikes_out_by_station += np.maximum(-moves, 0)
        stock = new_stock

        # the day, in segments split at the midday visits
        boundaries = [0, *midday_slots, SLOTS_PER_DAY]
        for segment_start, segment_end in pairwise(boundaries):
            if segment_start > 0:
                for p, policy in enumerate(policies):
                    if (
                        policy.midday_hour is None
                        or slot_of_hour(policy.midday_hour) != segment_start
                    ):
                        continue
                    need, room = history(
                        day, policy.history_days, False, *rest_grids[policy.midday_hour]
                    )
                    low, high = target_band(need, room)
                    has_band = ~np.isnan(low) & open_today
                    target = np.where(
                        has_band,
                        np.clip(stock[p], np.nan_to_num(low), np.nan_to_num(high)),
                        stock[p],
                    ).astype(np.int32)
                    prevented = np.where(
                        has_band,
                        expected_shortages(need, room, stock[p].astype(np.float32))
                        - expected_shortages(need, room, target.astype(np.float32)),
                        0,
                    )
                    chosen = np.argsort(-prevented)[: policy.midday_stations]
                    chosen = chosen[prevented[chosen] > 0]
                    midday_move = target[chosen] - stock[p, chosen]
                    midday_moves_by_day[p, eval_i] += int(np.abs(midday_move).sum())
                    bikes_in_by_station[p, chosen] += np.maximum(midday_move, 0)
                    bikes_out_by_station[p, chosen] += np.maximum(-midday_move, 0)
                    stock[p, chosen] = target[chosen]
            stock, empty, full = simulate_slots(
                stock,
                capacity,
                starts[:, offset, segment_start:segment_end],
                ends[:, offset, segment_start:segment_end],
            )
            empty_by_day[:, eval_i] += empty.sum(axis=(1, 2))
            full_by_day[:, eval_i] += full.sum(axis=(1, 2))
            shortages_by_station += (empty + full).sum(axis=2)
            shortages_by_slot[:, segment_start:segment_end] += (empty + full).sum(
                axis=1
            )
    print(month_first, flush=True)
    month_first = next_month

# %% [markdown]
# ## Results

# %%
eval_columns = [day_index[day] for day in eval_days]
summary = pl.DataFrame(
    {
        "policy": [policy.name for policy in policies],
        "family": [policy.family for policy in policies],
        "empty_per_day": empty_by_day.mean(axis=1),
        "full_per_day": full_by_day.mean(axis=1),
        "pickups_per_day": pickups_by_day.mean(axis=1),
        "dropoffs_per_day": dropoffs_by_day.mean(axis=1),
        "midday_moves_per_day": midday_moves_by_day.mean(axis=1),
    }
).with_columns(
    shortages_per_day=pl.col("empty_per_day") + pl.col("full_per_day"),
    # a bike moved is picked up at one station and dropped at another; the depot evens out the rest
    bikes_moved_per_day=pl.max_horizontal("pickups_per_day", "dropoffs_per_day")
    + pl.col("midday_moves_per_day") / 2,
    shortages_per_100_trips=(pl.col("empty_per_day") + pl.col("full_per_day"))
    / float(trips_per_day[eval_columns].mean())
    * 100,
)
with pl.Config(tbl_rows=40, tbl_cols=-1, tbl_width_chars=200, float_precision=1):
    print(summary)

np.savez_compressed(
    PROCESSED / f"simulation-{year}.npz",
    policy=np.array([policy.name for policy in policies]),
    family=np.array([policy.family for policy in policies]),
    station_id=np.array(station_ids),
    day=np.array(eval_days, dtype="datetime64[D]"),
    trips_per_day=trips_per_day[eval_columns],
    empty_by_day=empty_by_day,
    full_by_day=full_by_day,
    pickups_by_day=pickups_by_day,
    dropoffs_by_day=dropoffs_by_day,
    midday_moves_by_day=midday_moves_by_day,
    shortages_by_station=shortages_by_station,
    bikes_in_by_station=bikes_in_by_station,
    bikes_out_by_station=bikes_out_by_station,
    shortages_by_slot=shortages_by_slot,
    stock_before_move=stock_before_move,
    stock_after_move=stock_after_move,
    band_low=band_low,
    band_high=band_high,
    capacity=capacity,
)
summary.write_parquet(PROCESSED / f"simulation-{year}-summary.parquet")
