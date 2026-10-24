# %% [markdown]
# # Exploration: when and where the flow runs one way
# Development year only (October 2024 to September 2025). Writes figures 1 to 4 to `figures/`
# and prints the numbers the report quotes.

# %%
import os

os.environ["POLARS_MAX_THREADS"] = "6"

from datetime import datetime
from pathlib import Path

import polars as pl
from plotnine import (
    aes,
    annotate,
    element_blank,
    element_text,
    facet_wrap,
    geom_abline,
    geom_area,
    geom_bin_2d,
    geom_line,
    geom_point,
    geom_text,
    geom_tile,
    ggplot,
    labs,
    scale_color_gradient2,
    scale_color_manual,
    scale_fill_gradient,
    scale_fill_gradient2,
    scale_size_continuous,
    scale_x_continuous,
    scale_y_continuous,
    theme,
)

from lib.chart_style import (
    BLUE,
    CONTEXT,
    DARK_BLUE,
    FIGURES,
    FONT,
    INK,
    LIGHT_CONTEXT,
    LOSING_RED,
    NEUTRAL,
    ORANGE,
    PALE_BLUE,
    REPORT_THEME,
    MAP_THEME,
    on_map,
)
from lib.geography import land_outline, station_areas
from lib.rebalancing import HOLIDAYS

PROCESSED = Path("data/processed")
BOUNDARIES = Path("data/raw/boundaries")
TEST_START = datetime(2025, 10, 1)
FIGURES.mkdir(exist_ok=True)

stations = station_areas(pl.read_parquet(PROCESSED / "stations.parquet"), BOUNDARIES)
land = land_outline(BOUNDARIES)
# a weekday that is not a public holiday; holidays ride like weekends
is_workday = (pl.col("hour").dt.weekday() <= 5) & ~pl.col("hour").dt.date().is_in(
    HOLIDAYS
)

# %% [markdown]
# Hourly counts per station for the development year, built one month at a time.

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
dev_days = dev_hours.select(pl.col("hour").dt.date().unique())
workdays = dev_days.filter(
    (pl.col("hour").dt.weekday() <= 5) & ~pl.col("hour").is_in(HOLIDAYS)
).height
print(
    f"dev days {dev_days.height}, workdays {workdays}, station-hours with trips {dev_hours.height:,}"
)

# %% [markdown]
# ## Figure 1: the daily rhythm by rider type

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
print(
    by_hour.filter(pl.col("hour_of_day").is_in([8, 11, 17])).sort(
        "day_type", "rider", "hour_of_day"
    )
)

# each line is named where it runs, in the workday panel, instead of in a legend
rider_labels = pl.DataFrame(
    {
        "day_type": ["workday", "workday"],
        "hour_of_day": [9.4, 11.5],
        "starts": [9_000.0, 2_000.0],
        "rider": ["annual members", "casual riders"],
    }
).with_columns(pl.col("day_type").cast(by_hour.schema["day_type"]))
figure_1 = (
    ggplot(by_hour, aes("hour_of_day", "starts", color="rider"))
    # only the members' curve is shaded; two overlapping fills mix into brown
    + geom_area(
        data=by_hour.filter(pl.col("rider") == "annual members"),
        fill=BLUE,
        alpha=0.1,
        color="none",
    )
    + geom_line(size=1.1)
    + geom_text(
        aes(label="rider"),
        data=rider_labels,
        ha="left",
        size=7,
        fontweight="bold",
        family=FONT,
    )
    + facet_wrap("day_type")
    + scale_color_manual(
        values={"annual members": BLUE, "casual riders": ORANGE}, guide=None
    )
    + scale_x_continuous(
        breaks=range(0, 24, 3),
        labels=[f"{hour:02d}:00" for hour in range(0, 24, 3)],
        expand=(0, 0.4),
    )
    + scale_y_continuous(
        labels=lambda values: [f"{value:,.0f}" for value in values], expand=(0, 0, 0.05, 0)
    )
    + labs(
        title="Members ride at the rush hours on workdays; everyone rides midday at weekends",
        subtitle="Average trips started per hour, development year",
        x="",
        y="trips started per hour",
    )
    + REPORT_THEME
    + theme(figure_size=(6.7, 2.8))
)
figure_1.save(FIGURES / "fig1-daily-rhythm.png", verbose=False)

# %% [markdown]
# ## Figure 2: where bikes drain and pile up in the rush hours
# `rush_net_flow`: bikes a station gains over the three hours of a rush, per workday.

# %%
open_workdays = (
    pl.read_parquet(PROCESSED / "station_days.parquet")
    .filter(
        (pl.col("service_day") < TEST_START.date())
        & (pl.col("service_day").dt.weekday() <= 5)
        & ~pl.col("service_day").is_in(HOLIDAYS)
    )
    .group_by("station_id")
    .agg(pl.len().alias("open_workdays"))
)
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
    .join(stations, on="station_id")
)
print(
    rush.group_by("rush")
    .agg(
        (pl.col("rush_net_flow") <= -5).sum().alias("losing_5_plus"),
        (pl.col("rush_net_flow") >= 5).sum().alias("gaining_5_plus"),
        pl.col("rush_net_flow").min().alias("largest_loss"),
        pl.col("rush_net_flow").max().alias("largest_gain"),
    )
    .sort("rush")
)
print(
    rush.group_by("rush", "borough")
    .agg(pl.col("rush_net_flow").sum().round(0))
    .pivot("rush", index="borough", values="rush_net_flow")
)

figure_2 = (
    on_map(ggplot(), land, lng=(-74.07, -73.87), lat=(40.64, 40.86))
    + geom_point(
        aes("lng", "lat", color="rush_net_flow", size="swing"),
        data=rush.with_columns(
            pl.col("rush_net_flow").clip(-15, 15),
            swing=pl.col("rush_net_flow").abs().clip(0, 30),
        ).sort("swing"),
        stroke=0,
        alpha=0.9,
    )
    + facet_wrap("rush")
    + scale_size_continuous(range=(0.25, 1.9), guide=None)
    + scale_color_gradient2(
        low=LOSING_RED,
        mid=LIGHT_CONTEXT,
        high=BLUE,
        midpoint=0,
        limits=(-15, 15),
        breaks=[-15, 0, 15],
        labels=["loses 15+", "even", "gains 15+"],
    )
    + labs(
        title="Mornings drain the residential areas into Midtown and downtown; evenings run it back",
        subtitle="Average bikes each station gains over a workday rush; larger dots swing more",
        color="",
    )
    + REPORT_THEME
    + MAP_THEME
    + theme(figure_size=(6.7, 4.9), legend_key_width=110, legend_key_height=5)
)
figure_2.save(FIGURES / "fig2-rush-map.png", verbose=False)

# %% [markdown]
# ## Figure 3: the neighbourhood clock
# Average workday net flow per hour, added over the stations of each neighbourhood. The 24
# neighbourhoods with the largest swings, ordered from the one losing most in the morning rush.

# %%
neighbourhood_profile = (
    dev_hours.filter(is_workday)
    .join(stations.select("station_id", "neighbourhood", "borough"), on="station_id")
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
print(row_order.select("label", pl.col("morning").round(0)))

figure_3 = (
    ggplot(
        clock.with_columns(pl.col("net_flow").clip(-120, 120)),
        aes("hour_of_day", "label", fill="net_flow"),
    )
    + geom_tile(color="white", size=0.4)
    + scale_fill_gradient2(
        low=LOSING_RED,
        mid=NEUTRAL,
        high=BLUE,
        midpoint=0,
        limits=(-120, 120),
        breaks=[-120, 0, 120],
        labels=["loses 120+", "even", "gains 120+"],
    )
    + scale_x_continuous(
        breaks=range(0, 24, 3),
        labels=[f"{hour:02d}:00" for hour in range(0, 24, 3)],
        expand=(0, 0),
    )
    + labs(
        title="Homes empty and offices fill before 10:00; the evening rush runs it back",
        subtitle="Bikes gained per workday hour, all stations in the neighbourhood together",
        x="",
        y="",
        fill="",
    )
    + REPORT_THEME
    + theme(
        figure_size=(6.7, 4.0),
        axis_text_y=element_text(size=6.5, color=INK),
        axis_line_x=element_blank(),
        panel_grid_major_y=element_blank(),
        legend_key_width=110,
        legend_key_height=5,
    )
)
figure_3.save(FIGURES / "fig3-neighbourhood-clock.png", verbose=False)

# %% [markdown]
# ## Figure 4: the imbalance is a habit
# Each station's morning-rush net flow averaged over odd ISO weeks against even ones.

# %%
dev_workdays = pl.read_parquet(PROCESSED / "station_days.parquet").filter(
    (pl.col("service_day") < TEST_START.date())
    & (pl.col("service_day").dt.weekday() <= 5)
    & ~pl.col("service_day").is_in(HOLIDAYS)
)
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
print(
    halves.select(
        pl.corr("odd", "even").alias("correlation"),
        pl.corr("odd", "even", method="spearman").alias("rank_correlation"),
        pl.len().alias("stations"),
    )
)

halves_correlation = halves.select(pl.corr("odd", "even")).item()
figure_4 = (
    ggplot(halves.with_columns(tint=pl.col("odd").clip(-30, 30)), aes("odd", "even"))
    + geom_abline(color=CONTEXT, linetype="dashed", size=0.4)
    + geom_point(aes(color="tint"), alpha=0.6, size=0.9, stroke=0)
    + annotate(
        "text",
        x=-75,
        y=95,
        label=f"r = {halves_correlation:.3f}",
        ha="left",
        size=8,
        fontweight="bold",
        color=INK,
        family=FONT,
    )
    + scale_color_gradient2(
        low=LOSING_RED, mid=CONTEXT, high=BLUE, midpoint=0, limits=(-30, 30), guide=None
    )
    + labs(
        title="The morning imbalance repeats week after week",
        subtitle="One dot per station; dashed line: same in both",
        x="bikes gained per morning rush, odd weeks",
        y="even weeks",
    )
    + REPORT_THEME
    + theme(figure_size=(3.25, 3.0), plot_title=element_text(size=8.5))
)
figure_4.save(FIGURES / "fig4-habit.png", verbose=False)

# %% [markdown]
# ## Figure 5: a single day is noisier than the average
# Each station's morning-rush net flow on one workday against its average over the 10 workdays
# before. A schedule has to be set the night before, so this is the error it starts from.

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
print(
    morning_days.select(
        pl.corr("last_10", "net_flow").alias("correlation"),
        ((pl.col("net_flow") - pl.col("last_10")).abs())
        .median()
        .alias("median_abs_error"),
        pl.col("net_flow").abs().median().alias("median_abs_flow"),
        pl.len().alias("station_days"),
    )
)

day_correlation = morning_days.select(pl.corr("last_10", "net_flow")).item()
figure_5 = (
    ggplot(
        morning_days.sample(30_000, seed=1).filter(
            pl.col("last_10").is_between(-60, 110)
            & pl.col("net_flow").is_between(-60, 110)
        ),
        aes("last_10", "net_flow"),
    )
    + geom_bin_2d(binwidth=4)
    + geom_abline(color=INK, linetype="dashed", size=0.35, alpha=0.6)
    + annotate(
        "text",
        x=-55,
        y=100,
        label=f"r = {day_correlation:.2f}",
        ha="left",
        size=8,
        fontweight="bold",
        color=INK,
        family=FONT,
    )
    + scale_fill_gradient(low=PALE_BLUE, high=DARK_BLUE, trans="log10", guide=None)
    + labs(
        title="One day scatters around the station's habit",
        subtitle="30,000 station-days; darker: more of them",
        x="average over the 10 workdays before",
        y="that morning",
    )
    + REPORT_THEME
    + theme(figure_size=(3.25, 3.0), plot_title=element_text(size=8.5))
)
figure_5.save(FIGURES / "fig5-single-day.png", verbose=False)
