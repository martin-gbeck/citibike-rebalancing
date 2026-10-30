# %% [markdown]
# # The daily demand forecast for the simulation
# Fits the demand model in `lib/demand.py` on the development year and saves every day's
# forecast to `data/processed/daily_demand.parquet`, which `rebalance.py` reads to test
# stretching the station bands by tomorrow's volume. The walkthrough notebook reports the model
# and draws figures 6 and 7.

# %%
import os

os.environ["POLARS_MAX_THREADS"] = "6"

from pathlib import Path

import polars as pl

from lib.demand import daily_demand, fit_demand_model

PROCESSED = Path("data/processed")

# 23 February 2026: the system was shut for a snowstorm, no trips at all; a model of riders'
# choices cannot explain a closure, so the day is left out of fitting and scoring
days = daily_demand(PROCESSED / "bins", Path("data/raw")).filter(pl.col("trips") > 0)
model, days = fit_demand_model(days)
print(model.summary().tables[1])
days.write_parquet(PROCESSED / "daily_demand.parquet")
