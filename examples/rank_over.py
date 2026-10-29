# %% [markdown]
# # Place in line, the old way: a window over (slot, station)
#
# Not used by the pipeline. Shows how `load_trip_slots` gave each rider their place in line
# among the riders leaving the same station in the same 5-minute slot, before commit 22d89e7.
# `rank_diff.py` beside it does the same job the new way. Run from the project folder:
# `.venv/bin/python examples/rank_over.py`

# %%
import time
from datetime import datetime

import polars as pl

# %% [markdown]
# A toy day: three riders leave station 7 in slot 0, one leaves station 2 in slot 0, two leave
# station 7 in slot 1. After the sort, `rank` counts 0, 1, 2 within each (slot, station).

# %%
riders = pl.DataFrame(
    {
        "start": [1, 0, 0, 1, 0, 0],
        "origin": [7, 7, 2, 4, 6, 4],
        "rider": ["f", "a", "d", "e", "b", "c"],
    }
)
ranked = riders.sort("start", "origin").with_columns(
    rank=pl.int_range(pl.len()).over("start", "origin")
)
print(ranked)

# %% [markdown]
# One month of real trips. `over` hashes every (slot, station) pair to build its groups, even
# though the sort has already put each group in one run of rows; that hashing is the cost.

# %%
month_start = datetime(2025, 10, 1, 4)
trips = (
    pl.scan_parquet("data/processed/trips/*.parquet")
    .filter(
        pl.col("start_slot").is_between(
            month_start, datetime(2025, 11, 1, 4), closed="left"
        )
    )
    .select(
        start=((pl.col("start_slot") - month_start).dt.total_minutes() // 5).cast(
            pl.Int64
        ),
        origin=pl.col("start_station_id"),
    )
    .collect()
)
began = time.perf_counter()
ranked_month = trips.sort("start", "origin").with_columns(
    rank=pl.int_range(pl.len()).over("start", "origin")
)
print(f"{len(trips):,} trips ranked in {time.perf_counter() - began:.2f} s")
