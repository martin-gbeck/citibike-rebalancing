# %% [markdown]
# # How many people ride tomorrow: a daily demand model
# A linear regression of the log of each day's trips on weather and calendar, fitted on the
# development year and scored on the test year. It explains what moves volume, and its forecast
# scales the rebalancing targets on days that will be busier or quieter than the days before.
# Writes `data/processed/daily_demand.parquet` and figures 6 and 7.

# %%
import os

os.environ["POLARS_MAX_THREADS"] = "6"

from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import statsmodels.formula.api as smf
from plotnine import (
    aes,
    annotate,
    element_text,
    geom_errorbarh,
    geom_line,
    geom_point,
    geom_vline,
    ggplot,
    labs,
    scale_color_manual,
    scale_x_date,
    scale_y_continuous,
    theme,
)

from lib.chart_style import BLUE, CONTEXT, FIGURES, INK, LOSING_RED, REPORT_THEME
from lib.fetching import fetch_weather
from lib.rebalancing import HOLIDAYS

PROCESSED = Path("data/processed")
TEST_START = date(2025, 10, 1)
# riding hours: weather at 03:00 hardly changes anyone's plans
DAYTIME = (7, 21)
# above this, more warmth stops bringing more riders (the dev-year scatter levels off here)
WARM_C = 22

trips = (
    pl.scan_parquet(PROCESSED / "bins" / "*.parquet")
    .group_by(date=pl.col("slot").dt.date())
    .agg(pl.col("starts").cast(pl.Int64).sum().alias("trips"))
    .collect()
)
hourly_weather = fetch_weather(date(2024, 10, 1), date(2026, 9, 30), Path("data/raw"))
daytime = pl.col("hour").dt.hour().is_between(*DAYTIME)
weather = (
    hourly_weather.group_by(date=pl.col("hour").dt.date())
    .agg(
        pl.col("temperature_c").filter(daytime).mean().alias("temperature_c"),
        (pl.col("precipitation_mm").filter(daytime) >= 0.5).sum().alias("wet_hours"),
        pl.col("snowfall_cm").sum().alias("snowfall_cm"),
        pl.col("wind_kmh").filter(daytime).mean().alias("wind_kmh"),
    )
    .sort("date")
    # snow keeps riders off for days after it falls, while it lies on the bike lanes
    .with_columns(snow_3_days_cm=pl.col("snowfall_cm").rolling_sum(3, min_samples=1))
)
days = (
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
# 23 February 2026: the system was shut for a snowstorm, no trips at all; a model of riders'
# choices cannot explain a closure, so the day is left out of fitting and scoring
closed = days.filter(pl.col("trips") == 0)
print(closed.select("date", "snowfall_cm", "snow_3_days_cm"))
days = days.filter(pl.col("trips") > 0)

# no time trend: fitted on one year it picks up the season rather than growth, and with it the
# test-year R² fell from 0.87 to 0.71
formula = (
    "np.log(trips) ~ temperature_c + warm_excess_c + wet_hours + snow_3_days_cm + wind_kmh"
    " + weekend_or_holiday + year_end"
)
dev_days = days.filter(~pl.col("is_test")).to_pandas()
model = smf.ols(formula, data=dev_days).fit()
print(model.summary().tables[1])

days = days.with_columns(
    predicted=pl.Series(np.exp(model.predict(days.to_pandas())).to_numpy())
)
scores = (
    days.group_by("is_test")
    .agg(
        (
            1
            - ((pl.col("trips") - pl.col("predicted")) ** 2).sum()
            / ((pl.col("trips") - pl.col("trips").mean()) ** 2).sum()
        ).alias("r2"),
        ((pl.col("trips") - pl.col("predicted")).abs() / pl.col("trips"))
        .median()
        .alias("median_abs_pct_error"),
        pl.len().alias("days"),
    )
    .sort("is_test")
)
print(scores)
days.write_parquet(PROCESSED / "daily_demand.parquet")

# %% [markdown]
# ## Figure 6: the model against the two years

# %%
long = days.select("date", actual="trips", model="predicted").unpivot(
    index="date", variable_name="series", value_name="trips"
)
test_r2 = scores.filter(pl.col("is_test"))["r2"].item()
figure_6 = (
    ggplot(long, aes("date", "trips", color="series"))
    + geom_line(size=0.35)
    + geom_vline(xintercept=TEST_START, color=INK, linetype="dashed", size=0.4)
    + annotate(
        "text",
        x=date(2025, 9, 20),  # ty: ignore[invalid-argument-type]  plotnine takes dates on a date axis
        y=232_000,
        label="fitted",
        ha="right",
        size=6.5,
    )
    + annotate(
        "text",
        x=date(2025, 10, 10),  # ty: ignore[invalid-argument-type]
        y=232_000,
        label=f"scored: R² {test_r2:.2f}",
        ha="left",
        size=6.5,
    )
    + scale_color_manual(values={"actual": CONTEXT, "model": BLUE})
    + scale_x_date(date_labels="%b %y", date_breaks="6 months")
    + scale_y_continuous(
        labels=lambda values: [f"{float(value) / 1000:,.0f}k" for value in values]
    )
    + labs(
        title="Weather and calendar explain most daily swings",
        x="",
        y="trips per day",
        color="",
    )
    + REPORT_THEME
    + theme(
        figure_size=(3.35, 2.6),
        plot_title=element_text(size=8.5),
        axis_text_x=element_text(size=6.5),
    )
)
figure_6.save(FIGURES / "fig6-demand-model.png", verbose=False)

# %% [markdown]
# ## Figure 7: what each factor does to a day's trips
# Coefficients turned into percentage changes, with 95% confidence intervals.

# %%
effects = {
    "+5 °C, below 22 °C": ("temperature_c", 5),
    "+5 °C, above 22 °C": (("temperature_c", "warm_excess_c"), 5),
    "+1 wet hour in the day": ("wet_hours", 1),
    "+5 cm snow in the last 3 days": ("snow_3_days_cm", 5),
    "+10 km/h wind": ("wind_kmh", 10),
    "weekend or holiday": ("weekend_or_holiday", 1),
    "24 Dec to 1 Jan": ("year_end", 1),
}
covariance = model.cov_params()
rows: list[dict[str, float | str]] = []
for label, (terms, step) in effects.items():
    names = [terms] if isinstance(terms, str) else list(terms)
    weights = np.ones(len(names))
    estimate = float(model.params[names] @ weights)
    standard_error = float(
        np.sqrt(weights @ covariance.loc[names, names].to_numpy() @ weights)
    )
    rows.append(
        {
            "factor": label,
            "effect": np.expm1(step * estimate) * 100,
            "low": np.expm1(step * (estimate - 1.96 * standard_error)) * 100,
            "high": np.expm1(step * (estimate + 1.96 * standard_error)) * 100,
        }
    )
effect_table = pl.DataFrame(rows).with_columns(
    pl.col("factor").cast(pl.Enum(list(effects)[::-1])),
    direction=pl.when(pl.col("effect") >= 0)
    .then(pl.lit("more"))
    .otherwise(pl.lit("fewer")),
)
print(effect_table)

figure_7 = (
    ggplot(effect_table, aes("effect", "factor", color="direction"))
    + geom_vline(xintercept=0, color=CONTEXT, size=0.4)
    + geom_errorbarh(aes(xmin="low", xmax="high"), height=0.3, size=0.5)
    + geom_point(size=1.8)
    + scale_color_manual(values={"more": BLUE, "fewer": LOSING_RED}, guide=None)
    + labs(
        title="What moves a day's riding",
        x="change in the day's trips, %",
        y="",
    )
    + REPORT_THEME
    + theme(figure_size=(3.35, 2.6), plot_title=element_text(size=8.5))
)
figure_7.save(FIGURES / "fig7-demand-effects.png", verbose=False)
