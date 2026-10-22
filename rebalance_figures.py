# %% [markdown]
# # Figures 8 to 12 and the numbers behind the recommendation
# Reads the test-year simulation from `rebalance.py test`, so nothing here is fitted or chosen.

# %%
import os

os.environ["POLARS_MAX_THREADS"] = "6"

from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
from plotnine import (
    aes,
    annotate,
    element_text,
    facet_wrap,
    geom_hline,
    geom_line,
    geom_path,
    geom_point,
    geom_step,
    geom_text,
    ggplot,
    labs,
    scale_color_gradient2,
    scale_color_manual,
    scale_size_area,
    scale_x_continuous,
    scale_y_continuous,
    theme,
)

from lib.chart_style import (
    BLUE,
    CONTEXT,
    DARK_BLUE,
    FIGURES,
    INK,
    LIGHT_CONTEXT,
    LOSING_RED,
    MAP_THEME,
    ORANGE,
    REPORT_THEME,
    on_map,
)
from lib.geography import land_outline, station_areas
from lib.rebalancing import SLOTS_PER_DAY, load_day_slots, simulate_slots

PROCESSED = Path("data/processed")
BOUNDARIES = Path("data/raw/boundaries")
RECOMMENDED = "budget-3000-midday-14-50"
NIGHT_ONLY = "budget-3000"

simulation = np.load(PROCESSED / "simulation-test.npz")
policies = simulation["policy"].tolist()
position = {name: i for i, name in enumerate(policies)}
summary = pl.read_parquet(PROCESSED / "simulation-test-summary.parquet")
days = simulation["day"].astype("datetime64[D]").astype(date).tolist()
station_ids = simulation["station_id"].tolist()
capacity = simulation["capacity"]
stations = station_areas(
    pl.read_parquet(PROCESSED / "stations.parquet"), BOUNDARIES
).filter(pl.col("station_id").is_in(station_ids))
stations = stations.sort("station_id")
land = land_outline(BOUNDARIES)

with pl.Config(tbl_rows=30, float_precision=0, fmt_str_lengths=30):
    print(summary.select("policy", "shortages_per_day", "bikes_moved_per_day"))

# %% [markdown]
# ## Figure 9: shortages against bikes moved, every schedule on the test year

# %%
labels = {
    "none": "no rebalancing",
    "half": "every station reset to half full",
    "band": "every station moved into its band (= budget 9,000)",
    "oracle": "the band known in advance (bound)",
}
points = summary.with_columns(
    kind=pl.when(pl.col("family") == "budget")
    .then(pl.lit("nightly budget"))
    .when(pl.col("family").str.contains("midday"))
    .then(pl.lit("budget 3,000 + 14:00 visits"))
    .otherwise(pl.lit("simple rule"))
)
budget_curve = points.filter(pl.col("kind") != "simple rule").sort(
    "bikes_moved_per_day"
)
# where each rule's name sits relative to its point, so no label leaves the panel or hits a curve
label_place = {
    "none": ("left", 60, 170),
    "half": ("right", -60, 170),
    "band": ("left", 60, 170),
    "oracle": ("left", 70, -150),
}
simple = points.filter(pl.col("kind") == "simple rule").with_columns(
    label=pl.col("policy").replace_strict(labels),
    ha=pl.col("policy").replace_strict(
        {name: place[0] for name, place in label_place.items()}
    ),
    label_x=pl.col("bikes_moved_per_day")
    + pl.col("policy").replace_strict(
        {name: place[1] for name, place in label_place.items()}
    ),
    label_y=pl.col("shortages_per_day")
    + pl.col("policy").replace_strict(
        {name: place[2] for name, place in label_place.items()}
    ),
)
budget_labels = points.filter(
    pl.col("policy").is_in(["budget-1000", "budget-3000"])
).with_columns(
    label=pl.col("policy")
    .str.replace("budget-", "")
    .cast(pl.Int32)
    .map_elements(lambda bikes: f"budget {bikes:,}", return_dtype=pl.String)
)
midday_labels = points.filter(pl.col("policy").str.ends_with("-400")).with_columns(
    label=pl.lit("400 stations")
)
recommended = points.filter(pl.col("policy") == RECOMMENDED)

figure_8 = (
    ggplot()
    + geom_path(
        aes("bikes_moved_per_day", "shortages_per_day", color="kind"),
        data=budget_curve.filter(pl.col("kind") == "nightly budget"),
        size=0.8,
    )
    + geom_path(
        aes("bikes_moved_per_day", "shortages_per_day", color="kind"),
        data=pl.concat(
            [
                points.filter(pl.col("policy") == NIGHT_ONLY),
                budget_curve.filter(pl.col("kind") == "budget 3,000 + 14:00 visits"),
            ],
            how="diagonal",
        ).with_columns(kind=pl.lit("budget 3,000 + 14:00 visits")),
        size=0.8,
    )
    + geom_point(
        aes("bikes_moved_per_day", "shortages_per_day", color="kind"),
        data=budget_curve,
        size=1.4,
    )
    + geom_text(
        aes("bikes_moved_per_day", "shortages_per_day", label="label"),
        data=budget_labels,
        size=6,
        nudge_y=-140,
        color=DARK_BLUE,
    )
    + geom_text(
        aes("bikes_moved_per_day", "shortages_per_day", label="label"),
        data=midday_labels,
        size=6,
        nudge_x=60,
        ha="left",
        color=ORANGE,
    )
    + geom_point(
        aes("bikes_moved_per_day", "shortages_per_day"),
        data=simple,
        color=INK,
        size=2,
    )
    + geom_text(
        aes("label_x", "label_y", label="label", ha="ha"),
        data=simple,
        size=6.5,
        color=INK,
    )
    + geom_point(
        aes("bikes_moved_per_day", "shortages_per_day"),
        data=recommended,
        color=ORANGE,
        size=4,
        fill="none",
        stroke=1,
    )
    + annotate(
        "text",
        x=float(recommended["bikes_moved_per_day"].item()),
        y=float(recommended["shortages_per_day"].item()) - 420,
        label="recommended: budget 3,000\n+ 50 stations at 14:00",
        ha="center",
        size=7,
        color=ORANGE,
        fontweight="bold",
    )
    + scale_color_manual(
        values={"nightly budget": BLUE, "budget 3,000 + 14:00 visits": ORANGE}
    )
    + scale_x_continuous(
        labels=lambda values: [f"{float(value):,.0f}" for value in values]
    )
    + scale_y_continuous(
        labels=lambda values: [f"{float(value):,.0f}" for value in values],
        limits=(0, 4500),
    )
    + labs(
        title="Moving fewer bikes, to the right stations, prevents more shortages than moving many",
        subtitle="Test year, October 2025 to September 2026. Budget: bikes loaded or unloaded per night. Orange: stations visited at 14:00",
        x="bikes moved per day",
        y="riders finding a station empty or full, per day",
        color="",
    )
    + REPORT_THEME
    + theme(figure_size=(6.7, 3.6))
)
figure_8.save(FIGURES / "fig9-tradeoff.png", verbose=False)

# %% [markdown]
# Wasted moves under the half-full rule: bikes moved at stations whose stock was already inside
# the band the history recommends.

# %%
half = position["half"]
before = simulation["stock_before_move"][half].astype(np.float32)
after = simulation["stock_after_move"][half].astype(np.float32)
low, high = simulation["band_low"], simulation["band_high"]
inside = (before >= low) & (before <= high)
moved = np.abs(after - before)
print(
    f"half-full rule: {moved[inside].sum() / moved.sum():.0%} of bikes handled were at stations "
    f"already inside their band; {(after[~np.isnan(low)] > high[~np.isnan(low)]).mean():.0%} of "
    f"station-nights it set the stock above the band and "
    f"{(after[~np.isnan(low)] < low[~np.isnan(low)]).mean():.0%} below"
)

# %% [markdown]
# ## Figures 10 and 11: where the vans go, and where shortages are left

# %%
recommended_i = position[RECOMMENDED]
per_night = pl.DataFrame(
    {
        "station_id": station_ids,
        "dropped": simulation["bikes_in_by_station"][recommended_i] / len(days),
        "picked": simulation["bikes_out_by_station"][recommended_i] / len(days),
        "shortages": simulation["shortages_by_station"][recommended_i] / len(days),
        "half_shortages": simulation["shortages_by_station"][half] / len(days),
    }
).join(
    stations.select(
        "station_id", "name", "lat", "lng", "borough", "neighbourhood", "capacity"
    ),
    on="station_id",
)
per_night = per_night.with_columns(
    handled=pl.col("dropped") + pl.col("picked"),
    role=pl.when(pl.col("dropped") > 2 * pl.col("picked"))
    .then(pl.lit("mostly drop-offs"))
    .when(pl.col("picked") > 2 * pl.col("dropped"))
    .then(pl.lit("mostly pick-ups"))
    .otherwise(pl.lit("both")),
)
ranked = per_night.sort("handled", descending=True).with_columns(
    cumulative_share=pl.col("handled").cum_sum() / pl.col("handled").sum()
)
top_tenth_share = (
    ranked.head(per_night.height // 10).select(pl.col("handled").sum()).item()
    / ranked.select(pl.col("handled").sum()).item()
)
print(
    f"stations visited at all: {(per_night['handled'] > 0.05).sum()} of {per_night.height}; "
    f"the top 10% of stations take {top_tenth_share:.0%} "
    f"of the bikes handled; stations covering 80% of handling: {(ranked['cumulative_share'] < 0.8).sum() + 1}"
)
print(
    per_night.group_by("borough")
    .agg(pl.col("dropped", "picked", "shortages", "half_shortages").sum().round(0))
    .sort("dropped", descending=True)
)
print(
    ranked.head(12).select(
        "name",
        "neighbourhood",
        pl.col("dropped", "picked", "shortages").round(1),
        "capacity",
    )
)

figure_9 = (
    on_map(ggplot(), land, lng=(-74.07, -73.87), lat=(40.64, 40.86))
    + geom_point(
        aes("lng", "lat"),
        data=per_night.filter(pl.col("handled") <= 0.5),
        color=LIGHT_CONTEXT,
        size=0.3,
        stroke=0,
    )
    + geom_point(
        aes("lng", "lat", size="handled", color="net_dropped"),
        data=per_night.filter(pl.col("handled") > 0.5)
        .with_columns(net_dropped=(pl.col("dropped") - pl.col("picked")).clip(-4, 4))
        .sort("handled"),
        alpha=0.8,
        stroke=0,
    )
    + scale_size_area(max_size=4, breaks=[2, 10, 20])
    + scale_color_gradient2(
        low=LOSING_RED,
        mid="#8a8f99",
        high=BLUE,
        midpoint=0,
        limits=(-4, 4),
        breaks=[-4, 0, 4],
        labels=["4+ picked up", "even", "4+ dropped"],
    )
    + labs(
        title="A quarter of the stations take 80% of the moves",
        subtitle="Recommended schedule, test year, per day; grey: left alone",
        size="bikes handled",
        color="net per day",
    )
    + REPORT_THEME
    + MAP_THEME
    + theme(
        figure_size=(3.35, 4.3),
        legend_position="right",
        plot_title=element_text(size=8.5),
        legend_box="vertical",
        legend_key_height=40,
        legend_key_width=6,
    )
)
figure_9.save(FIGURES / "fig10-where-vans-go.png", verbose=False)

leftover = per_night.filter(pl.col("shortages") >= 0.5).sort("shortages")
worst_20_share = (
    per_night.top_k(20, by="shortages").select(pl.col("shortages").sum()).item()
    / per_night.select(pl.col("shortages").sum()).item()
)
print(f"shortages left at the 20 worst stations: {worst_20_share:.0%}")
figure_11 = (
    on_map(ggplot(), land, lng=(-74.07, -73.87), lat=(40.64, 40.86))
    + geom_point(
        aes("lng", "lat"), data=per_night, color=LIGHT_CONTEXT, size=0.3, stroke=0
    )
    + geom_point(
        aes("lng", "lat", size="shortages"),
        data=leftover,
        color=LOSING_RED,
        alpha=0.7,
        stroke=0,
    )
    + scale_size_area(max_size=6, breaks=[1, 10, 50])
    + labs(
        title="What is left sits at a few stations",
        subtitle="Riders turned away per day, recommended schedule",
        size="per day",
    )
    + REPORT_THEME
    + MAP_THEME
    + theme(
        figure_size=(3.35, 4.3),
        legend_position="right",
        plot_title=element_text(size=8.5),
    )
)
figure_11.save(FIGURES / "fig11-shortages-left.png", verbose=False)

# %% [markdown]
# ## Figure 12: when the shortages that are left happen

# %%
by_slot = simulation["shortages_by_slot"]
slot_hours = (np.arange(SLOTS_PER_DAY) // 12 + 4) % 24
hour_labels = {
    "half": "reset to half",
    "none": "no rebalancing",
    NIGHT_ONLY: "budget, nights only",
    RECOMMENDED: "budget + 14:00 visits",
    "oracle": "band known in advance",
}
by_hour = pl.concat(
    [
        pl.DataFrame(
            {
                "hour": np.arange(24),
                "shortages": np.bincount(
                    slot_hours, weights=by_slot[position[name]], minlength=24
                )
                / len(days),
                "schedule": label,
            }
        )
        for name, label in hour_labels.items()
    ]
).with_columns(pl.col("schedule").cast(pl.Enum(list(hour_labels.values()))))
print(
    by_hour.pivot("schedule", index="hour", values="shortages").select(
        pl.all().round(0)
    )
)

figure_10 = (
    ggplot(by_hour, aes("hour", "shortages", color="schedule"))
    + geom_step(size=0.7, direction="mid")
    + scale_color_manual(
        values={
            "reset to half": CONTEXT,
            "no rebalancing": LIGHT_CONTEXT,
            "budget, nights only": BLUE,
            "budget + 14:00 visits": ORANGE,
            "band known in advance": INK,
        }
    )
    + scale_x_continuous(
        breaks=range(0, 24, 3), labels=[f"{hour:02d}:00" for hour in range(0, 24, 3)]
    )
    + labs(
        title="Half-full stations fail in the morning rush; the budget's leftovers come in the evening",
        x="hour of the day",
        y="shortages per hour",
        color="",
    )
    + REPORT_THEME
    + theme(figure_size=(6.7, 2.8))
)
figure_10.save(FIGURES / "fig12-shortages-by-hour.png", verbose=False)

# %% [markdown]
# ## Figure 8: one workday at three stations
# The stock hour by hour from the level each schedule set at 04:00, on a dry, ordinary Tuesday.

# %%
example_day = date(2026, 5, 12)
day_i = days.index(example_day)
print(
    pl.read_parquet(PROCESSED / "daily_demand.parquet").filter(
        pl.col("date") == example_day
    )
)
# an office station that fills, a home station that empties, and one whose swing is larger than
# its docks, so that no starting level works
examples = {
    "office": "Broadway & W 25 St",
    "home": "E 10 St & Ave A",
    "swings past its docks": "9 Ave & W 33 St",
}
rows = [
    station_ids.index(stations.filter(pl.col("name") == name)["station_id"].item())
    for name in examples.values()
]
starts, ends = load_day_slots(
    PROCESSED / "bins", [station_ids[row] for row in rows], example_day, 1
)
traces: list[pl.DataFrame] = []
for schedule, name in (("reset to half", "half"), ("recommended", RECOMMENDED)):
    stock = simulation["stock_after_move"][position[name], rows, day_i].astype(np.int32)
    path = [stock.copy()]
    for slot in range(SLOTS_PER_DAY):
        stock, _, _ = simulate_slots(
            stock[None, :],
            capacity[rows],
            starts[:, 0, slot : slot + 1],
            ends[:, 0, slot : slot + 1],
        )
        stock = stock[0]
        path.append(stock.copy())
    stock_path = np.array(path)
    for k, (kind, station_name) in enumerate(examples.items()):
        traces.append(
            pl.DataFrame(
                {
                    "hours_from_4": np.arange(SLOTS_PER_DAY + 1) / 12,
                    "stock": stock_path[:, k],
                    "schedule": schedule,
                    "station": f"{station_name} ({kind}, {capacity[rows[k]]} docks)",
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
    {"station": trace["station"].unique(maintain_order=True), "docks": capacity[rows]}
).with_columns(pl.col("station").cast(trace.schema["station"]))
figure_11 = (
    ggplot(trace, aes("hours_from_4", "stock", color="schedule"))
    + geom_hline(
        aes(yintercept="docks"), data=docks, color=CONTEXT, linetype="dashed", size=0.4
    )
    + geom_hline(yintercept=0, color=CONTEXT, size=0.4)
    + geom_line(size=0.7)
    + facet_wrap("station", ncol=3, scales="free_y")
    + scale_color_manual(values={"reset to half": CONTEXT, "recommended": BLUE})
    + scale_x_continuous(
        breaks=[0, 4, 8, 12, 16, 20],
        labels=["04:00", "08:00", "12:00", "16:00", "20:00", "00:00"],
    )
    + labs(
        title="Half full is the wrong start at a commuter station, and some stations no start can save",
        subtitle="Tuesday 12 May 2026. Dashed line: the station's docks; flat at the line or at zero means riders turned away",
        x="",
        y="bikes in the station",
        color="",
    )
    + REPORT_THEME
    + theme(figure_size=(6.7, 2.6), strip_text=element_text(size=6.5))
)
figure_11.save(FIGURES / "fig8-one-day.png", verbose=False)
