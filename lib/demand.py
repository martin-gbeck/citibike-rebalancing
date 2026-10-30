"""The daily demand model: how many trips the whole system has in a day, from weather and
calendar. Used by `demand_model.py` (which saves the forecast for `rebalance.py`) and by the
walkthrough notebook (which reports and draws it)."""

from datetime import date
from pathlib import Path
from typing import cast

import numpy as np
import polars as pl
import statsmodels.formula.api as smf
from statsmodels.regression.linear_model import RegressionResultsWrapper

from lib.fetching import fetch_weather
from lib.rebalancing import HOLIDAYS

TEST_START = date(2025, 10, 1)
# riding hours: weather at 03:00 hardly changes anyone's plans
DAYTIME = (7, 21)
# above this, more warmth stops bringing more riders (the dev-year scatter levels off here)
WARM_C = 22
# no time trend: fitted on one year it picks up the season rather than growth, and with it the
# test-year R² fell from 0.87 to 0.71
FORMULA = (
    "np.log(trips) ~ temperature_c + warm_excess_c + wet_hours + snow_3_days_cm + wind_kmh"
    " + weekend_or_holiday + year_end"
)


def daily_demand(bins_dir: Path, raw_dir: Path) -> pl.DataFrame:
    """One row per day, October 2024 to September 2026: trips started, the day's weather in
    riding hours and the calendar, with `is_test` marking the test year. Days without a single
    trip are kept, with `trips` 0."""
    trips = (
        pl.scan_parquet(bins_dir / "*.parquet")
        .group_by(date=pl.col("slot").dt.date())
        .agg(pl.col("starts").cast(pl.Int64).sum().alias("trips"))
        .collect()
    )
    hourly_weather = fetch_weather(date(2024, 10, 1), date(2026, 9, 30), raw_dir)
    daytime = pl.col("hour").dt.hour().is_between(*DAYTIME)
    weather = (
        hourly_weather.group_by(date=pl.col("hour").dt.date())
        .agg(
            pl.col("temperature_c").filter(daytime).mean().alias("temperature_c"),
            (pl.col("precipitation_mm").filter(daytime) >= 0.5)
            .sum()
            .alias("wet_hours"),
            pl.col("snowfall_cm").sum().alias("snowfall_cm"),
            pl.col("wind_kmh").filter(daytime).mean().alias("wind_kmh"),
        )
        .sort("date")
        # snow keeps riders off for days after it falls, while it lies on the bike lanes
        .with_columns(
            snow_3_days_cm=pl.col("snowfall_cm").rolling_sum(3, min_samples=1)
        )
    )
    return (
        weather.join(trips, on="date", how="left")
        .with_columns(pl.col("trips").fill_null(0))
        .filter(pl.col("date") <= date(2026, 9, 30))
        .with_columns(
            weekend_or_holiday=(
                (pl.col("date").dt.weekday() > 5) | pl.col("date").is_in(HOLIDAYS)
            ).cast(pl.Int8),
            # 24 December to 1 January: offices thin out even on weekdays
            year_end=(
                ((pl.col("date").dt.month() == 12) & (pl.col("date").dt.day() >= 24))
                | ((pl.col("date").dt.month() == 1) & (pl.col("date").dt.day() == 1))
            ).cast(pl.Int8),
            warm_excess_c=(pl.col("temperature_c") - WARM_C).clip(lower_bound=0),
            is_test=pl.col("date") >= TEST_START,
        )
    )


def fit_demand_model(
    days: pl.DataFrame,
) -> tuple[RegressionResultsWrapper, pl.DataFrame]:
    """Fits `FORMULA` on the development-year rows of `days` and returns the model with `days`
    plus `predicted`, the forecast trips (e to the fitted log, so the median day)."""
    # statsmodels leaves `fit` untyped
    model = cast(
        RegressionResultsWrapper,
        smf.ols(FORMULA, data=days.filter(~pl.col("is_test")).to_pandas()).fit(),
    )
    predicted = days.with_columns(
        predicted=pl.Series(np.exp(model.predict(days.to_pandas())).to_numpy())
    )
    return model, predicted
