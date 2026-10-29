# %% [markdown]
# # Place in line, the new way: row number minus where the run starts
#
# Not used by the pipeline. Shows how `load_trip_slots` gives each rider their place in line
# among the riders leaving the same station in the same 5-minute slot, since commit 22d89e7.
# `rank_over.py` beside it does the same job the old way. Run from the project folder:
# `.venv/bin/python examples/rank_diff.py`

# %%
import time
from datetime import datetime

import polars as pl

# %% [markdown]
# The same toy day as `rank_over.py`. After the sort each (slot, station) is one run of rows.
# A row where the slot or the station changes starts a new run; `forward_fill` carries that
# row's number down the run, and a rider's place in line is their row minus it. The first row
# has no previous row, so its `diff` is null and `fill_null(0)` starts the first run at 0.

# %%
riders = pl.DataFrame(
    {
        "start": [1, 0, 0, 1, 0, 0],
        "origin": [7, 7, 2, 7, 7, 7],
        "rider": ["f", "a", "d", "e", "b", "c"],
    }
)
run_start = (
    pl.when((pl.col("start").diff() != 0) | (pl.col("origin").diff() != 0))
    .then(pl.col("row"))
    .forward_fill()
    .fill_null(0)
)
ranked = (
    riders.sort("start", "origin")
    .with_columns(row=pl.int_range(pl.len()))
    .with_columns(rank=pl.col("row") - run_start)
    .drop("row")
)
print(ranked)

# %% [markdown]
# One month of real trips. Only a pass down the sorted rows, no grouping, so it runs several
# times faster than the window in `rank_over.py`. Station ids are cast to an Enum first, since
# `diff` needs numbers; the pipeline does the same cast to turn ids into station rows.

# %%
month_start = datetime(2025, 10, 1, 4)
station_ids = pl.read_parquet("data/processed/stations.parquet")["station_id"].to_list()
trips = (
    pl.scan_parquet("data/processed/trips/*.parquet")
    .filter(pl.col("start_slot").is_between(month_start, datetime(2025, 11, 1, 4), closed="left"))
    .select(
        start=((pl.col("start_slot") - month_start).dt.total_minutes() // 5).cast(pl.Int64),
        origin=pl.col("start_station_id")
        .cast(pl.Enum(station_ids), strict=False)
        .to_physical()
        .cast(pl.Int32),
    )
    .filter(pl.col("origin").is_not_null())
    .collect()
)
began = time.perf_counter()
ranked_month = (
    trips.sort("start", "origin")
    .with_columns(row=pl.int_range(pl.len()))
    .with_columns(rank=pl.col("row") - run_start)
    .drop("row")
)
print(f"{len(trips):,} trips ranked in {time.perf_counter() - began:.2f} s")
