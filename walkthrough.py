# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Citi Bike rebalancing: the report as code
#
# This notebook follows the report section by section. Each step says what we do and why, runs
# the analysis behind it, prints the numbers the report quotes and draws the report's figures
# (saved to `figures/`). The heavy steps run once beforehand as scripts and save their results to
# `data/processed/`; this notebook reads those and runs in under a minute.
#
# **The pipeline**, in run order. Each script reads what the one before wrote.
#
# | Step | Script | What it does | Time |
# |---|---|---|---|
# | 1 | `prepare_data.py` | Downloads two years of trips (92 million), fixes the station ids, counts starts and ends per station in 5-minute slots | 4 min |
# | 2 | `station_days.py` | For every station and day: how far its stock fell and rose from its 04:00 level | 6 s |
# | 3 | `demand_model.py` | Fits the daily demand model and saves every day's forecast, which step 4 tests | 5 s |
# | 4 | `rebalance.py dev` / `test` | Replays every trip of a year under each schedule and counts riders turned away | 2-3 min |
# | 5 | this notebook | The analysis, the numbers and all 13 figures | under 1 min |
#
# **The tools it imports**, so the code below reads without opening them:
#
# - `lib/rebalancing.py`: `HOLIDAYS`, the public holidays, which ride like weekends.
#   `target_band(need, room)` takes a station's need and room over its past days and returns the
#   band of starting levels that turns away the fewest riders. `simulate_slots(stock, docks,
#   starts, ends)` replays stations slot by slot from a starting stock and returns the stock
#   after, plus the riders who found no bike and no free dock. `load_day_slots` reads one day's
#   5-minute starts and ends for a list of stations. `SLOTS_PER_DAY` is 288.
# - `lib/demand.py`: `daily_demand` builds one row per day with trips, weather and calendar;
#   `fit_demand_model` fits the regression on the first year and adds each day's forecast.
# - `lib/geography.py`: `station_areas` adds each station's borough and neighbourhood;
#   `land_outline` gives the coastline for the maps.
# - `lib/fetching.py`: `fetch_rebalanced_bikes` reads Citi Bike's monthly reports of bikes moved.
# - `lib/figures.py`: one function per report figure. Each takes the table built here and
#   returns the chart; the look comes from `lib/chart_style.py`.

# %%
import os

os.environ["POLARS_MAX_THREADS"] = "6"

from datetime import date, datetime
from pathlib import Path
from typing import cast

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from IPython.display import display

from lib import figures
from lib.chart_style import FIGURES
from lib.demand import daily_demand, fit_demand_model
from lib.fetching import fetch_rebalanced_bikes
from lib.geography import land_outline, station_areas
from lib.rebalancing import (
    HOLIDAYS,
    SLOTS_PER_DAY,
    load_day_slots,
    simulate_slots,
    target_band,
)

PROCESSED = Path("data/processed")
BOUNDARIES = Path("data/raw/boundaries")
TEST_START = datetime(2025, 10, 1)
FIGURES.mkdir(exist_ok=True)

stations = pl.read_parquet(PROCESSED / "stations.parquet")
station_places = station_areas(stations, BOUNDARIES)
land = land_outline(BOUNDARIES)
station_days = pl.read_parquet(PROCESSED / "station_days.parquet")
# a weekday that is not a public holiday; holidays ride like weekends
is_workday = (pl.col("hour").dt.weekday() <= 5) & ~pl.col("hour").dt.date().is_in(
    HOLIDAYS
)

# %% [markdown]
# ## 1. The business problem
#
# Members ride from homes (Brooklyn, the East Village, the Upper West Side) to offices (Midtown,
# Lower Manhattan) in the morning and back in the evening. Home stations run out of bikes, office
# stations run out of docks, and the next rider is turned away. Citi Bike fixes this with trucks,
# about 2,500 bikes a day. Every bike moved costs money, and a move in the wrong place prevents
# nothing.
#
# **Our question:** each night, which stations should be restocked or cleared, and by how many
# bikes, to turn away the fewest riders per bike moved? And is a second visit during the day
# worth it?
#
# Everything about the riders' flow comes from the first year only. Hourly starts and ends per
# station:

# %%
dev_hours = (
    pl.scan_parquet(PROCESSED / "bins" / "*.parquet")
    .filter(pl.col("slot") < TEST_START)
    .group_by("station_id", hour=pl.col("slot").dt.truncate("1h"))
    .agg(pl.col("starts", "ends", "member_starts").cast(pl.Int32).sum())
    .with_columns(net_flow=pl.col("ends") - pl.col("starts"))
    .collect(engine="streaming")
    .with_columns(
        day_type=pl.when(is_workday)
        .then(pl.lit("workday"))
        .otherwise(pl.lit("weekend or holiday"))
    )
)
dev_dates = dev_hours.select(pl.col("hour").dt.date().unique())
workdays = dev_dates.filter(
    (pl.col("hour").dt.weekday() <= 5) & ~pl.col("hour").is_in(HOLIDAYS)
).height
print(
    f"{dev_dates.height} days, {workdays} workdays, {dev_hours.height:,} station-hours with trips"
)

# %% [markdown]
# Average trips started per hour, members against casual riders:

# %%
by_hour = (
    dev_hours.group_by(
        "day_type", date=pl.col("hour").dt.date(), hour_of_day=pl.col("hour").dt.hour()
    )
    .agg(
        member=pl.col("member_starts").sum(),
        casual=pl.col("starts").sum() - pl.col("member_starts").sum(),
    )
    .group_by("day_type", "hour_of_day")
    .agg(pl.col("member", "casual").mean())
    .unpivot(
        index=["day_type", "hour_of_day"], variable_name="rider", value_name="starts"
    )
    .with_columns(
        pl.col("day_type").cast(pl.Enum(["workday", "weekend or holiday"])),
        pl.col("rider").replace(
            {"member": "annual members", "casual": "casual riders"}
        ),
    )
)
display(
    by_hour.filter(pl.col("hour_of_day").is_in([8, 11, 17])).sort(
        "day_type", "rider", "hour_of_day"
    )
)
figure_1 = figures.daily_rhythm(by_hour)
figure_1.save(FIGURES / "fig1-daily-rhythm.png", verbose=False)
figure_1

# %% [markdown]
# Figure 1 is the whole problem in one picture: members spike at 08:00 and 17:00 on workdays,
# casual riders do not. So every rule below treats workdays and weekends separately.
#
# ## 2. The trick: rebuilding every station's stock from public trips
#
# Citi Bike publishes every trip (start and end station, start and end time) but never how many
# bikes stand in a dock. We do not need that: a station's stock changes only when a bike leaves
# or arrives. Count both in each 5-minute slot, add up arrivals minus departures, and you have
# the station's stock relative to where it started at 04:00. We call that the **drift**.
#
# `prepare_data.py` turned 92 million trips into those 5-minute counts. Here is one month's file:

# %%
bins = pl.read_parquet(PROCESSED / "bins" / "202605.parquet")
print(f"{len(bins):,} rows, one per station and 5-minute slot with at least one trip")
bins.head(5)

# %% [markdown]
# A worked example: Broadway & W 25 St, an office station with 109 docks, on Tuesday 12 May 2026.
# The drift is the running total of arrivals minus departures from 04:00.

# %%
office = stations.filter(pl.col("name") == "Broadway & W 25 St").row(0, named=True)
day_slots = (
    bins.filter(
        pl.col("station_id") == office["station_id"],
        pl.col("slot").is_between(
            pl.datetime(2026, 5, 12, 4), pl.datetime(2026, 5, 13, 4), closed="left"
        ),
    )
    .sort("slot")
    .with_columns(drift=(pl.col("ends") - pl.col("starts")).cum_sum())
)
# Series.min() is typed as any scalar; drift is a running count of bikes
lowest, highest = (
    cast(int, day_slots["drift"].min()),
    cast(int, day_slots["drift"].max()),
)
print(f"{office['name']}: {office['capacity']} docks")
print(f"drift from 04:00: lowest {lowest}, highest {highest}")

fig, ax = plt.subplots(figsize=(9, 3.5))
_ = ax.step(day_slots["slot"], day_slots["drift"], where="post")
_ = ax.axhline(0, color="grey", lw=0.8)
_ = ax.set(
    ylabel="bikes gained since 04:00",
    title=f"{office['name']}, 12 May 2026: arrivals minus departures, added up",
)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
plt.show()

# %% [markdown]
# Read the chart as: starting from whatever it had at 04:00, the station gains about 105 bikes
# by 10:00, holds them through the day, and gives them all back between 16:00 and 19:00. It
# never drops below its 04:00 level. Two numbers decide whether a starting level
# works that day:
#
# - **need** = how far the drift falls below zero. Start with fewer bikes than that and the
#   station runs empty at some point.
# - **room** = docks minus how far the drift rises. Start with more bikes than that and the
#   station fills up.
#
# Any start between need and room carries the station through the whole day.

# %%
need = max(-lowest, 0)
room = office["capacity"] - max(highest, 0)
print(
    f"need {need}, room {room}: any start from {need} to {room} bikes works on this day"
)
print(f"half full would be {round(office['capacity'] / 2)} bikes")

# %% [markdown]
# `station_days.py` stores the lowest and highest drift for every station and every day
# (1.6 million station-days), which is everything the rules below use.
#
# **The data's blind spots**, ranked by how much they could move the results:
#
# 1. Stock is never observed, only rebuilt. The simulation starts every station at the level a
#    schedule sets at 04:00.
# 2. The real trips already include Citi Bike's own trucks. The simulation handles this: a rider
#    turned away at an empty station never rides, so their bike never reaches the destination.
# 3. A rider who walked away from an empty station left no trip, so shortages are lower bounds.
#    Every schedule faces the same trips, so the comparison holds.
# 4. Dock counts come from one day (22 Oct 2026); 81 stations without them are left out.
# 5. Within a 5-minute slot, departures go before arrivals.
#
# The first year (Oct 2024 to Sep 2025) is for exploring and choosing every setting. The second
# year (Oct 2025 to Sep 2026) is used once, at the end, to score the schedules.
#
# ## 3. When and where the flow runs one way
#
# Each station's net flow over the three hours of each workday rush, per workday it was open:

# %%
dev_workdays = station_days.filter(
    (pl.col("service_day") < TEST_START.date())
    & (pl.col("service_day").dt.weekday() <= 5)
    & ~pl.col("service_day").is_in(HOLIDAYS)
)
open_workdays = dev_workdays.group_by("station_id").agg(pl.len().alias("open_workdays"))
rush = (
    dev_hours.filter(is_workday)
    .with_columns(
        rush=pl.when(pl.col("hour").dt.hour().is_between(7, 9))
        .then(pl.lit("morning rush, 07:00 to 10:00"))
        .when(pl.col("hour").dt.hour().is_between(16, 18))
        .then(pl.lit("evening rush, 16:00 to 19:00"))
        .cast(pl.Enum(["morning rush, 07:00 to 10:00", "evening rush, 16:00 to 19:00"]))
    )
    .drop_nulls("rush")
    .group_by("station_id", "rush")
    .agg(pl.col("net_flow").sum())
    .join(open_workdays, on="station_id")
    .with_columns(rush_net_flow=pl.col("net_flow") / pl.col("open_workdays"))
    .join(station_places, on="station_id")
)
display(
    rush.group_by("rush")
    .agg(
        (pl.col("rush_net_flow") <= -5).sum().alias("losing_5_plus"),
        (pl.col("rush_net_flow") >= 5).sum().alias("gaining_5_plus"),
        pl.col("rush_net_flow").max().alias("largest_gain"),
    )
    .sort("rush")
)
display(
    rush.group_by("rush", "borough")
    .agg(pl.col("rush_net_flow").sum().round(0))
    .pivot("rush", index="borough", values="rush_net_flow")
)
figure_2 = figures.rush_map(rush, land)
figure_2.save(FIGURES / "fig2-rush-map.png", verbose=False)
figure_2

# %% [markdown]
# In the morning rush Manhattan gains about 935 bikes and Brooklyn loses 1,055; the evening
# reverses it.
#
# The same flow by neighbourhood and hour: all stations of a neighbourhood added up per workday
# hour, for the 24 neighbourhoods with the largest swings, ordered from the one losing most in
# the morning rush.

# %%
neighbourhood_profile = (
    dev_hours.filter(is_workday)
    .join(
        station_places.select("station_id", "neighbourhood", "borough"), on="station_id"
    )
    .group_by("neighbourhood", "borough", hour_of_day=pl.col("hour").dt.hour())
    .agg(pl.col("net_flow").sum() / workdays)
)
largest = (
    neighbourhood_profile.group_by("neighbourhood")
    .agg(pl.col("net_flow").abs().sum().alias("swing"))
    .top_k(24, by="swing")
)
row_order = (
    neighbourhood_profile.filter(pl.col("hour_of_day").is_between(7, 9))
    .join(largest, on="neighbourhood")
    .group_by("neighbourhood", "borough")
    .agg(pl.col("net_flow").sum().alias("morning"))
    .sort("morning")
    .with_columns(
        # "Midtown South-Flatiron-Union Square" reads as "Midtown South, Flatiron"
        label=pl.col("neighbourhood").str.split("-").list.head(2).list.join(", ")
        + " ("
        + pl.col("borough").str.slice(0, 2)
        + ")"
    )
)
clock = neighbourhood_profile.join(
    row_order, on=["neighbourhood", "borough"]
).with_columns(pl.col("label").cast(pl.Enum(row_order["label"].to_list()[::-1])))
display(row_order.select("label", pl.col("morning").round(0)))
figure_3 = figures.neighbourhood_clock(clock)
figure_3.save(FIGURES / "fig3-neighbourhood-clock.png", verbose=False)
figure_3

# %% [markdown]
# Each neighbourhood has its own clock. Homes empty 06:00 to 10:00, offices fill then and empty
# 16:00 to 19:00, nightlife areas lose bikes again after 21:00. The sharp office drain from 16:00
# is why a van visit at 14:00 can still help.
#
# ## 4. Can it be planned the night before?
#
# A schedule set at night only works if tomorrow looks like the days before. First on average:
# each station's morning-rush net flow per workday in odd ISO weeks against even ones.

# %%
open_workdays_by_half = dev_workdays.group_by(
    "station_id",
    half=pl.when(pl.col("service_day").dt.week() % 2 == 1)
    .then(pl.lit("odd"))
    .otherwise(pl.lit("even")),
).agg(pl.len().alias("days"))
halves = (
    dev_hours.filter(is_workday & pl.col("hour").dt.hour().is_between(7, 9))
    .with_columns(
        half=pl.when(pl.col("hour").dt.week() % 2 == 1)
        .then(pl.lit("odd"))
        .otherwise(pl.lit("even"))
    )
    .group_by("station_id", "half")
    .agg(pl.col("net_flow").sum())
    .join(open_workdays_by_half, on=["station_id", "half"])
    .with_columns(per_day=pl.col("net_flow") / pl.col("days"))
    .pivot("half", index="station_id", values="per_day")
    .drop_nulls()
)
halves_correlation = cast(float, halves.select(pl.corr("odd", "even")).item())
print(f"{halves.height:,} stations, correlation {halves_correlation:.3f}")
figure_4 = figures.habit(halves, halves_correlation)
figure_4.save(FIGURES / "fig4-habit.png", verbose=False)
figure_4

# %% [markdown]
# Then one day at a time: each station's morning-rush net flow on one workday against its average
# over the 10 workdays before. That is the error a schedule set the night before starts from.

# %%
morning_days = (
    dev_workdays.select("station_id", "service_day")
    .join(
        dev_hours.filter(is_workday & pl.col("hour").dt.hour().is_between(7, 9))
        .group_by("station_id", service_day=pl.col("hour").dt.date())
        .agg(pl.col("net_flow").sum()),
        on=["station_id", "service_day"],
        how="left",
    )
    .with_columns(pl.col("net_flow").fill_null(0))
    .sort("station_id", "service_day")
    .with_columns(
        last_10=pl.col("net_flow").shift(1).rolling_mean(10).over("station_id")
    )
    .drop_nulls("last_10")
)
day_correlation = cast(
    float, morning_days.select(pl.corr("last_10", "net_flow")).item()
)
display(
    morning_days.select(
        correlation=pl.corr("last_10", "net_flow"),
        median_miss=(pl.col("net_flow") - pl.col("last_10")).abs().median(),
        station_days=pl.len(),
    )
)
figure_5 = figures.single_day(morning_days, day_correlation)
figure_5.save(FIGURES / "fig5-single-day.png", verbose=False)
figure_5

# %% [markdown]
# On average, yes: a station's morning flow in odd weeks matches even weeks at a correlation of
# 0.998 (figure 4). One day is noisier: 0.90 against the average of the ten workdays before, a
# median miss of 1.6 bikes (figure 5). So a night-before plan will be a little off at most
# stations.
#
# The next check uses need and room from section 2 on every workday of the first year: how often
# does a half-full start fail, and how often would no start have worked?

# %%
dev_need_room = dev_workdays.join(
    stations.select("station_id", "capacity").drop_nulls(), on="station_id"
).with_columns(
    need=-pl.col("drift_min"),
    room=pl.col("capacity") - pl.col("drift_max"),
    half=(pl.col("capacity") / 2).round(),
)
half_fails = (
    (pl.col("half") < pl.col("need")) | (pl.col("half") > pl.col("room"))
).mean()
nothing_works = (pl.col("need") > pl.col("room")).mean()
dev_need_room.select(half_fails=half_fails, nothing_works=nothing_works)

# %% [markdown]
# A half-full start runs empty or full on about 22% of workday station-days, but on only about
# 1.3% would no start have worked (the swing was bigger than the docks). So nearly all the
# failures come from **the wrong starting level**, and fixing the starting level is the lever.
#
# ## 5. From history to a target for each station
#
# First, how busy will tomorrow be? A linear regression of the log of each day's trips on the
# weather in riding hours (07:00 to 21:00) and the calendar, fitted on the first year and scored
# on the second. 23 February 2026 is left out: the system was shut for snow, and a model of
# riders' choices cannot explain a closure.

# %%
all_days = daily_demand(PROCESSED / "bins", Path("data/raw"))
display(
    all_days.filter(pl.col("trips") == 0).select(
        "date", "snowfall_cm", "snow_3_days_cm"
    )
)
demand_model, demand_days = fit_demand_model(all_days.filter(pl.col("trips") > 0))
print(demand_model.summary().tables[1])
demand_scores = (
    demand_days.group_by("is_test")
    .agg(
        r2=1
        - ((pl.col("trips") - pl.col("predicted")) ** 2).sum()
        / ((pl.col("trips") - pl.col("trips").mean()) ** 2).sum(),
        median_miss=(
            (pl.col("trips") - pl.col("predicted")).abs() / pl.col("trips")
        ).median(),
        days=pl.len(),
    )
    .sort("is_test")
)
demand_scores

# %% [markdown]
# R² is 1 minus the squared forecast errors over the squared distances from the average day: 0.87
# on the test year means the model explains 87% of how much days differ. Half of all test days
# are forecast within 11%.

# %%
test_days = demand_days.filter(pl.col("is_test")).with_columns(
    kind=pl.when(pl.col("year_end") == 1)
    .then(pl.lit("Christmas week"))
    .when(pl.col("weekend_or_holiday") == 1)
    .then(pl.lit("weekend"))
    .otherwise(pl.lit("workday"))
)
test_score = demand_scores.filter(pl.col("is_test")).row(0, named=True)
figure_6 = figures.demand_fit(test_days, test_score["r2"], test_score["median_miss"])
figure_6.save(FIGURES / "fig6-demand-model.png", verbose=False)
figure_6

# %% [markdown]
# Each coefficient turned into the % change in a day's trips for a step of that variable,
# e^(b × step) − 1, with its 95% interval. Above 22 °C the temperature and warm-excess
# coefficients add up, so their interval comes from both and their covariance.

# %%
effect_steps: dict[str, tuple[list[str], float]] = {
    "+5 °C, below 22 °C": (["temperature_c"], 5),
    "+5 °C, above 22 °C": (["temperature_c", "warm_excess_c"], 5),
    "+1 wet hour in the day": (["wet_hours"], 1),
    "+5 cm snow in the last 3 days": (["snow_3_days_cm"], 5),
    "+10 km/h wind": (["wind_kmh"], 10),
    "weekend": (["weekend_or_holiday"], 1),
    "Christmas week": (["year_end"], 1),
}
covariance = demand_model.cov_params()
effect_rows: list[dict[str, float | str]] = []
for factor, (terms, step) in effect_steps.items():
    weights = np.ones(len(terms))
    estimate = float(demand_model.params[terms] @ weights)
    standard_error = float(
        np.sqrt(weights @ covariance.loc[terms, terms].to_numpy() @ weights)
    )
    effect_rows.append(
        {
            "factor": factor,
            "effect": np.expm1(step * estimate) * 100,
            "low": np.expm1(step * (estimate - 1.96 * standard_error)) * 100,
            "high": np.expm1(step * (estimate + 1.96 * standard_error)) * 100,
        }
    )
effects = pl.DataFrame(effect_rows)
display(effects.with_columns(pl.col("effect", "low", "high").round(1)))
figure_7 = figures.demand_effects(effects, list(effect_steps))
figure_7.save(FIGURES / "fig7-demand-effects.png", verbose=False)
figure_7

# %% [markdown]
# Each wet hour costs about 6.6% of trips, each 5 °C up to 22 °C adds about 21%. But volume does
# not say *where* bikes run out, and stretching each station's history by the forecast made
# decisions worse (the settings table below). So the forecast sizes the night shift, and the
# station targets come from each station's own recent days.
#
# **The target band, worked through on one station.** Take the last 10 workdays before 12 May
# 2026 at E 10 St & Ave A (a home station). For each day we have need and room. Starting a day
# with x bikes turns away about `need - x` riders if x is below need, `x - room` if it is above
# room, and none in between. Add that up over the 10 days for every x:

# %%
home = stations.filter(pl.col("name") == "E 10 St & Ave A").row(0, named=True)
last_10 = (
    station_days.filter(
        pl.col("station_id") == home["station_id"],
        pl.col("service_day") < date(2026, 5, 12),
        pl.col("service_day").dt.weekday() <= 5,
        ~pl.col("service_day").is_in(HOLIDAYS),
    )
    .sort("service_day")
    .tail(10)
    .select(
        "service_day",
        need=-pl.col("drift_min"),
        room=home["capacity"] - pl.col("drift_max"),
    )
)
print(f"{home['name']}: {home['capacity']} docks")
display(last_10)

levels = np.arange(home["capacity"] + 1)
past_need, past_room = last_10["need"].to_numpy(), last_10["room"].to_numpy()
turned_away = (
    np.maximum(past_need[None, :] - levels[:, None], 0)
    + np.maximum(levels[:, None] - past_room[None, :], 0)
).sum(axis=1)

home_low, home_high = target_band(
    past_need[None, :].astype(float), past_room[None, :].astype(float)
)
home_half = round(home["capacity"] / 2)
fig, ax = plt.subplots(figsize=(9, 3.5))
_ = ax.plot(levels, turned_away)
_ = ax.axvspan(
    home_low[0],
    home_high[0],
    alpha=0.3,
    label=f"target band: {home_low[0]:.0f} to {home_high[0]:.0f} bikes",
)
_ = ax.axvline(home_half, color="grey", ls="--", label="half full")
_ = ax.set(xlabel="bikes at 04:00", ylabel="riders turned away over the 10 days")
_ = ax.legend()
plt.show()
print(
    f"over these 10 days: half full turns away {turned_away[home_half]}, "
    f"the band {turned_away[int(home_low[0])]}"
)

# %% [markdown]
# The curve is flat at its lowest, from 91 to 94 bikes: that range is the **target band**. A home
# station needs to start nearly full. Half full (54) would have turned away 364 riders over these
# 10 days against 135 in the band, and on its worst days (need above room) no start could have
# saved every rider.
#
# Why the lowest point sits there: moving the start up one bike helps on every day where need is
# still above it, and hurts on every day where room is already below it. Counting over all 20 need
# and room numbers, the slope is (numbers below x) minus 10, which is zero between the 10th and
# 11th smallest. In other words, the band is the median of the 20 numbers. That is all
# `target_band` does.
#
# A station already inside its band is left alone; one outside it is moved to the nearest edge.
# This is the overnight-stock rule of Raviv and Kolka (2013), with the station's own last 10 days
# in place of a fitted demand model.
#
# **Settings, all chosen on the first year**, from the development-year simulation:
#
# | Setting | Tried | Chosen | Why |
# |---|---|---|---|
# | Days of history | 5, 10, 20 | 10 | 20 days cut shortages by 1% for 10% more bikes moved |
# | Stretch the band by tomorrow's forecast | yes, no | no | more shortages and more bikes moved |
# | Midday visit hour | 10, 12, 14 | 14:00 | fewest shortages, just before the evening drain |
# | Night budget, midday stations | 250 to 9,000; 25 to 400 | 3,000 and 100 | fewest shortages without moving more than Citi Bike reported (2,707 a day, Jan to Sep 2025) |
#
# ## 6. Simulating the schedules on the test year
#
# **Replaying one station-day.** Back to the office station on 12 May 2026: replay its real
# departures and arrivals from two starting levels and count who is turned away.
# `simulate_slots` goes slot by slot: add arrivals, subtract departures, and count anything below
# 0 (no bike) or above the docks (no free dock) as turned away.

# %%
office_slots = (
    bins.filter(pl.col("station_id") == office["station_id"])
    .filter(
        pl.col("slot").is_between(
            pl.datetime(2026, 5, 12, 4), pl.datetime(2026, 5, 13, 4), closed="left"
        )
    )
    .with_columns(
        k=((pl.col("slot") - pl.datetime(2026, 5, 12, 4)).dt.total_minutes() // 5)
    )
)
office_starts = np.zeros((1, SLOTS_PER_DAY), dtype=np.int16)
office_ends = np.zeros((1, SLOTS_PER_DAY), dtype=np.int16)
office_starts[0, office_slots["k"]] = office_slots["starts"]
office_ends[0, office_slots["k"]] = office_slots["ends"]

office_half = round(office["capacity"] / 2)
starting_levels = np.array([[office_half], [5]])  # [schedule, station]
_, empty, full = simulate_slots(
    starting_levels, np.array([office["capacity"]]), office_starts, office_ends
)
for name, level, no_bike, no_dock in zip(
    ["half full", "band start"],
    starting_levels[:, 0],
    empty.sum(axis=(1, 2)),
    full.sum(axis=(1, 2)),
):
    print(
        f"start {level:>3} bikes ({name}): {no_bike} found no bike, {no_dock} found no dock"
    )

# %% [markdown]
# The full simulation (`rebalance.py`) does exactly this for all 2,470 stations at once, every day
# of the test year, for every schedule side by side, with one addition: a rider turned away at an
# empty start station is struck from their destination's arrivals too, since that bike never
# arrives. Without that, never moving a bike looks better than resetting to half full, which is
# wrong.
#
# **The schedules:**
#
# - **No rebalancing:** stock carries over from day to day.
# - **Reset to half full:** every station set to half its docks at 04:00. The benchmark.
# - **Band:** every station outside its band moved to the nearest edge.
# - **Night budget:** each bike moved one step toward a station's band saves some expected
#   shortages, and the saving shrinks as the station nears its band. Rank every single-bike move
#   across the network and take the best 3,000 (bikes loaded plus unloaded). Since each extra
#   bike at a station saves less than the one before, taking the biggest savings first is the
#   best possible use of the budget.
# - **Budget + 14:00:** the same, plus a van visit at 14:00 to the 100 stations where it prevents
#   the most shortages for the rest of the day. Recommended.
# - **Band known in advance:** each station gets the best start for the day that actually
#   happened. The best any overnight plan could do.
#
# A "bike moved" is one picked up at one station and dropped at another: the larger of pickups
# and drop-offs, with a depot covering the difference.
#
# The test-year run saved, for every schedule, each station-night's stock before and after the
# move, and the riders turned away by station, slot and day:

# %%
# the schedule chosen on the development year, and its night budget alone
RECOMMENDED = "budget-3000-midday-14-100"
NIGHT_ONLY = "budget-3000"
simulation = np.load(PROCESSED / "simulation-test.npz")
policies: list[str] = simulation["policy"].tolist()
position = {name: i for i, name in enumerate(policies)}
summary = pl.read_parquet(PROCESSED / "simulation-test-summary.parquet")
sim_days: list[date] = simulation["day"].astype("datetime64[D]").astype(date).tolist()
station_ids: list[str] = simulation["station_id"].tolist()
capacity = simulation["capacity"]
simulated_places = station_places.filter(pl.col("station_id").is_in(station_ids)).sort(
    "station_id"
)
print(f"{len(policies)} schedules, {len(sim_days)} days, {len(station_ids):,} stations")

# %% [markdown]
# **One day at three stations.** The stock every 5 minutes from the level each schedule set at
# 04:00, on a dry, ordinary Tuesday: an office station that fills, a home station that empties,
# and one whose swing is larger than its docks, so that no starting level works.

# %%
example_day = date(2026, 5, 12)
day_i = sim_days.index(example_day)
display(demand_days.filter(pl.col("date") == example_day))
examples = {
    "office": "Broadway & W 25 St",
    "home": "E 10 St & Ave A",
    "swing beats its docks": "9 Ave & W 33 St",
}
example_rows = [
    station_ids.index(
        simulated_places.filter(pl.col("name") == name)["station_id"].item()
    )
    for name in examples.values()
]
example_starts, example_ends = load_day_slots(
    PROCESSED / "bins", [station_ids[row] for row in example_rows], example_day, 1
)
traces: list[pl.DataFrame] = []
for schedule, policy in (("reset to half", "half"), ("recommended", RECOMMENDED)):
    stock = simulation["stock_after_move"][
        position[policy], example_rows, day_i
    ].astype(np.int32)
    path = [stock.copy()]
    for slot in range(SLOTS_PER_DAY):
        stock, _, _ = simulate_slots(
            stock[None, :],
            capacity[example_rows],
            example_starts[:, 0, slot : slot + 1],
            example_ends[:, 0, slot : slot + 1],
        )
        stock = stock[0]
        path.append(stock.copy())
    stock_path = np.array(path)
    for k, (kind, station_name) in enumerate(examples.items()):
        traces.append(
            pl.DataFrame(
                {
                    "hours_from_4": np.arange(SLOTS_PER_DAY + 1) / 12,
                    "stock": stock_path[:, k].astype(np.float64),
                    "schedule": schedule,
                    "station": f"{station_name}\n{kind}, {capacity[example_rows[k]]} docks",
                }
            )
        )
trace = pl.concat(traces)
trace = trace.with_columns(
    pl.col("station").cast(
        pl.Enum(trace["station"].unique(maintain_order=True).to_list())
    )
)
docks = pl.DataFrame(
    {
        "station": trace["station"].unique(maintain_order=True),
        "docks": capacity[example_rows],
    }
).with_columns(pl.col("station").cast(trace.schema["station"]))
figure_8 = figures.one_day(trace, docks)
figure_8.save(FIGURES / "fig8-one-day.png", verbose=False)
figure_8

# %% [markdown]
# **Every schedule on the test year**, with Citi Bike's own reported moves for the same months
# as the yardstick for workload:

# %%
schedule_names = {
    "none": "never move a bike",
    "half": "reset to half full",
    "band": "every station into its band",
    NIGHT_ONLY: "night budget 3,000",
    RECOMMENDED: "recommended",
    "oracle": "band known in advance",
}
display(
    summary.filter(pl.col("policy").is_in(list(schedule_names)))
    .select(
        schedule=pl.col("policy").replace_strict(schedule_names),
        turned_away_per_day=pl.col("shortages_per_day").round(0),
        per_100_trips=pl.col("shortages_per_100_trips").round(1),
        bikes_moved_per_day=pl.col("bikes_moved_per_day").round(0),
    )
    .sort("turned_away_per_day", descending=True)
)
# what Citi Bike reports moving per day over the test-year months with a report
reported = fetch_rebalanced_bikes(Path("data/raw")).filter(
    pl.col("month") >= sim_days[0]
)
reported_per_day = cast(
    float,
    reported.select(
        pl.col("bikes_rebalanced").sum()
        / pl.col("month").dt.month_end().dt.day().cast(pl.Int64).sum()
    ).item(),
)
figure_9 = figures.tradeoff(summary, schedule_names, RECOMMENDED, reported_per_day)
figure_9.save(FIGURES / "fig9-tradeoff.png", verbose=False)
figure_9

# %% [markdown]
# The headline, computed from that table:

# %%
by_policy = {row["policy"]: row for row in summary.iter_rows(named=True)}
half_result, best = by_policy["half"], by_policy[RECOMMENDED]
fewer_shortages = 1 - best["shortages_per_day"] / half_result["shortages_per_day"]
fewer_bikes = 1 - best["bikes_moved_per_day"] / half_result["bikes_moved_per_day"]
print(
    f"recommended vs half full: {fewer_shortages:.0%} fewer riders turned away, "
    f"{fewer_bikes:.0%} fewer bikes moved"
)

# %% [markdown]
# Where the half-full reset wastes its work: bikes moved at stations whose stock was already
# inside the band their history recommends.

# %%
half_i = position["half"]
before = simulation["stock_before_move"][half_i].astype(np.float32)
after = simulation["stock_after_move"][half_i].astype(np.float32)
band_low, band_high = simulation["band_low"], simulation["band_high"]
has_band = ~np.isnan(band_low)
inside = (before >= band_low) & (before <= band_high)
moved = np.abs(after - before)
print(
    f"half-full rule: {moved[inside].sum() / moved.sum():.0%} of bikes handled were at stations "
    f"already inside their band; {(after[has_band] > band_high[has_band]).mean():.0%} of "
    f"station-nights it set the stock above the band and "
    f"{(after[has_band] < band_low[has_band]).mean():.0%} below"
)

# %% [markdown]
# **What the table says**, in order of importance:
#
# 1. The half-full reset moves the most bikes and still fails: it moves bikes at stations already
#    inside their band, and undoes the evening rush that had already refilled the homes.
# 2. A few well-aimed moves beat fixing every station: the 3,000 budget turns away 87 fewer
#    riders than the band rule while moving about 1,440 fewer bikes. Past a budget of about 4,000
#    it gets worse again, because the extra moves chase savings that are mostly noise.
# 3. The 14:00 visit is the best use of extra bikes: 166 fewer shortages for 672 more bikes,
#    0.25 per bike, against 0.06 per bike for a bigger night budget.
# 4. Better forecasts are where the rest is: perfect knowledge of each day would reach 869.
#
# **How sensitive is it?** Changing which rider gets the last bike when several leave a station in
# the same 5 minutes (the order is not in the data) moved the recommended result from 1,779 to
# 1,784 a day and changed no ranking.
#
# ## 7. Where, when, and against Citi Bike's own operations
#
# Bikes dropped and picked up per day at each station under the recommended schedule, and the
# riders still turned away there:

# %%
recommended_i = position[RECOMMENDED]
per_night = pl.DataFrame(
    {
        "station_id": station_ids,
        "dropped": simulation["bikes_in_by_station"][recommended_i] / len(sim_days),
        "picked": simulation["bikes_out_by_station"][recommended_i] / len(sim_days),
        "shortages": simulation["shortages_by_station"][recommended_i] / len(sim_days),
        "half_shortages": simulation["shortages_by_station"][half_i] / len(sim_days),
    }
).join(
    simulated_places.select(
        "station_id", "name", "lat", "lng", "borough", "neighbourhood", "capacity"
    ),
    on="station_id",
)
per_night = per_night.with_columns(handled=pl.col("dropped") + pl.col("picked"))
ranked = per_night.sort("handled", descending=True).with_columns(
    cumulative_share=pl.col("handled").cum_sum() / pl.col("handled").sum()
)
top_tenth_share = cast(
    float, ranked.head(per_night.height // 10)["handled"].sum()
) / cast(float, ranked["handled"].sum())
print(
    f"the busiest 10% of stations take {top_tenth_share:.0%} of the bikes handled; "
    f"{(ranked['cumulative_share'] < 0.8).sum() + 1} stations cover 80%"
)
display(
    per_night.group_by("borough")
    .agg(pl.col("dropped", "picked", "shortages", "half_shortages").sum().round(0))
    .sort("dropped", descending=True)
)
figure_10 = figures.where_vans_go(per_night, land)
figure_10.save(FIGURES / "fig10-where-vans-go.png", verbose=False)
figure_10

# %%
worst_20_share = cast(
    float, per_night.top_k(20, by="shortages")["shortages"].sum()
) / cast(float, per_night["shortages"].sum())
print(f"shortages left at the 20 worst stations: {worst_20_share:.0%}")
display(
    per_night.top_k(7, by="shortages").select(
        "name", "neighbourhood", pl.col("shortages").round(0), "capacity"
    )
)
figure_11 = figures.shortages_left(per_night, land)
figure_11.save(FIGURES / "fig11-shortages-left.png", verbose=False)
figure_11

# %% [markdown]
# The work is concentrated: the busiest 10% of stations take about half the bikes handled
# (figure 10). What is left is even more concentrated: seven stations hold a quarter of the
# remaining shortages, because their daily swing is bigger than their docks (figure 11, and the
# Penn Station example in figure 8). Trucks cannot fix those; more docks or a valet can.
#
# **When** the shortages that are left happen, by hour of the day:

# %%
by_slot = simulation["shortages_by_slot"]
# slot 0 starts at 04:00, and there are 12 slots to an hour
slot_hours = (np.arange(SLOTS_PER_DAY) // 12 + 4) % 24
hour_labels = {
    "half": "reset to half",
    NIGHT_ONLY: "budget, nights only",
    RECOMMENDED: "recommended",
    "oracle": "band known in advance",
}
shortages_hourly = pl.concat(
    [
        pl.DataFrame(
            {
                "hour": np.arange(24),
                "shortages": np.bincount(
                    slot_hours, weights=by_slot[position[policy]], minlength=24
                )
                / len(sim_days),
                "schedule": label,
            }
        )
        for policy, label in hour_labels.items()
    ]
).with_columns(pl.col("schedule").cast(pl.Enum(list(hour_labels.values()))))
display(
    shortages_hourly.filter(pl.col("hour").is_in([8, 17]))
    .pivot("schedule", index="hour", values="shortages")
    .select(pl.all().round(0))
)
figure_12 = figures.shortages_by_hour(shortages_hourly)
figure_12.save(FIGURES / "fig12-shortages-by-hour.png", verbose=False)
figure_12

# %% [markdown]
# The half-full reset fails in the morning rush (wrong starting level); the recommended
# schedule's worst hour is 17:00, when offices drain.
#
# **The reality check**: bikes moved per day in each month, simulated against what Citi Bike
# reports. A midday visit picks bikes up and drops them in the same trip, so half its handlings
# count as bikes moved.

# %%
moved_by_day = (
    np.maximum(simulation["pickups_by_day"], simulation["dropoffs_by_day"])
    + simulation["midday_moves_by_day"] / 2
)
months = pl.Series("month", sim_days).dt.truncate("1mo")
simulated = pl.concat(
    [
        pl.DataFrame(
            {"month": months, "bikes": moved_by_day[position[policy]], "source": label}
        )
        .group_by("month", "source")
        .agg(pl.col("bikes").mean())
        for policy, label in (
            ("half", "reset to half (simulated)"),
            (RECOMMENDED, "recommended (simulated)"),
        )
    ]
)
monthly_moves = pl.concat(
    [
        simulated,
        reported.select(
            "month",
            source=pl.lit("Citi Bike, reported"),
            bikes=pl.col("bikes_rebalanced") / pl.col("month").dt.month_end().dt.day(),
        ),
    ]
).with_columns(
    pl.col("source").cast(
        pl.Enum(
            [
                "Citi Bike, reported",
                "recommended (simulated)",
                "reset to half (simulated)",
            ]
        )
    )
)
comparison = monthly_moves.pivot("source", index="month", values="bikes").drop_nulls()
recommended_in_reported_months = pl.DataFrame(
    {"month": months, "bikes": moved_by_day[position[RECOMMENDED]]}
).filter(pl.col("month").is_in(reported["month"].implode()))
recommended_per_day = cast(float, recommended_in_reported_months["bikes"].mean())
months_correlation = cast(
    float,
    comparison.select(pl.corr("Citi Bike, reported", "recommended (simulated)")).item(),
)
print(
    f"months with a report: Citi Bike moved {reported_per_day:,.0f} a day, recommended "
    f"{recommended_per_day:,.0f}; correlation across months {months_correlation:.2f}"
)
figure_13 = figures.moves_vs_reported(monthly_moves)
figure_13.save(FIGURES / "fig13-moves-vs-reported.png", verbose=False)
figure_13

# %% [markdown]
# The simulated schedule moves about as many bikes as Citi Bike reports, and the two rise and
# fall together. Citi Bike's number also includes Bike Angels riders and valets, so our truck
# workload fits inside what it already does.
#
# ## 8. Recommendations, ranked by riders saved
#
# 1. Replace the half-full reset with a target band per station, and touch only stations outside
#    it (about 2,700 fewer turned away a day, 2,550 fewer bikes moved).
# 2. Treat the seven stations whose swing beats their docks as a capacity problem: more docks or
#    valets (442 riders a day).
# 3. Send vans to the 100 neediest stations at 14:00 (166 fewer a day for 672 bikes).
# 4. Cap the night at 3,000 bikes loaded or unloaded, biggest savings first.
# 5. Size the night shift from the weather forecast; keep station targets on history.
#
# ## 9. Limits
#
# Shortage counts are lower bounds. A rider at a full dock leaves the simulation instead of riding
# to the next station. Docks are from one day. No routing: the cost of a move depends on how far
# the van drives. No dollar figures, since no public cost per bike moved exists. The demand model
# is scored on the weather that happened, not the forecast issued the night before, so its 11%
# miss is a best case. And the gap to the best overnight plan (1,779 against 869) says better
# station-level forecasts are worth more than more tuning of the rule.
