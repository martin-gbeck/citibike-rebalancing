# %% [markdown]
# # Figures 8 to 13 and the numbers behind the recommendation
# Reads the test-year simulation from `rebalance.py test`, so nothing here is fitted or chosen.
# The independent-station run (`--independent`) is read only for the comparison table.

# %%
import os

os.environ["POLARS_MAX_THREADS"] = "6"

from datetime import date
from typing import cast
from pathlib import Path

import numpy as np
import polars as pl
from plotnine import (
    aes,
    annotate,
    element_text,
    facet_wrap,
    geom_area,
    geom_hline,
    geom_line,
    geom_path,
    geom_point,
    geom_text,
    geom_vline,
    ggplot,
    guide_legend,
    guides,
    labs,
    scale_color_gradient2,
    scale_color_manual,
    scale_linetype_manual,
    scale_size_area,
    scale_x_continuous,
    scale_x_date,
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
    MAP_THEME,
    MUTED,
    ORANGE,
    REPORT_THEME,
    on_map,
)
from lib.fetching import fetch_rebalanced_bikes
from lib.geography import land_outline, station_areas
from lib.rebalancing import SLOTS_PER_DAY, load_day_slots, simulate_slots

PROCESSED = Path("data/processed")
BOUNDARIES = Path("data/raw/boundaries")
# the schedule chosen on the development year, and its night budget alone
RECOMMENDED = "budget-3000-midday-14-100"
NIGHT_ONLY = "budget-3000"
NIGHT_BUDGET = f"{int(NIGHT_ONLY.split('-')[1]):,}"
MIDDAY_LABEL = f"budget {NIGHT_BUDGET} + 14:00 visits"

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

independent = pl.read_parquet(PROCESSED / "simulation-test-independent-summary.parquet")
with pl.Config(tbl_rows=30, float_precision=0, fmt_str_lengths=30):
    print(
        summary.select(
            "policy",
            "shortages_per_day",
            "empty_per_day",
            "full_per_day",
            "bikes_moved_per_day",
            "shortages_per_100_trips",
        ).join(
            independent.select("policy", independent_shortages="shortages_per_day"),
            on="policy",
            how="left",
        )
    )

# %% [markdown]
# ## Figure 9: shortages against bikes moved, every schedule on the test year

# %%
labels = {
    "half": "every station reset to half full",
    "band": "every station moved into its band (budget 9,000)",
    "oracle": "band known in advance (ceiling)",
}
points = summary.filter(pl.col("policy") != "none").with_columns(
    kind=pl.when(pl.col("family") == "budget")
    .then(pl.lit("nightly budget"))
    .when(pl.col("family").str.contains("midday"))
    .then(pl.lit(MIDDAY_LABEL))
    .otherwise(pl.lit("simple rule"))
)
# the chart stops a fifth above the half-full reset; schedules above that are named in a note
half_shortages = cast(
    float, summary.filter(pl.col("policy") == "half")["shortages_per_day"].item()
)
top = half_shortages * 1.2
off_chart = summary.filter(pl.col("shortages_per_day") > top).sort(
    "shortages_per_day", descending=True
)
off_chart_note = "above the chart:\n" + "\n".join(
    f"{'no rebalancing' if name == 'none' else name.replace('budget-', 'budget ')} {value:,.0f}"
    for name, value in off_chart.select("policy", "shortages_per_day").iter_rows()
)
points = points.filter(pl.col("shortages_per_day") <= top)
# what Citi Bike reports moving per day over the test-year months with a report
reported = fetch_rebalanced_bikes(Path("data/raw")).filter(pl.col("month") >= days[0])
reported_per_day = reported.select(
    pl.col("bikes_rebalanced").sum()
    / pl.col("month").dt.month_end().dt.day().cast(pl.Int64).sum()
).item()
budget_curve = points.filter(pl.col("kind") == "nightly budget").sort(
    "bikes_moved_per_day"
)
midday_curve = pl.concat(
    [
        points.filter(pl.col("policy") == NIGHT_ONLY),
        points.filter(pl.col("kind") == MIDDAY_LABEL).sort("bikes_moved_per_day"),
    ]
).with_columns(kind=pl.lit(MIDDAY_LABEL))
# where each rule's name sits relative to its point, so no label leaves the panel or hits a curve
label_place = {
    "half": ("right", -70, 0.05 * top),
    "band": ("left", 70, 0.05 * top),
    "oracle": ("left", -450, -0.08 * top),
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
budget_labels = budget_curve.filter(
    pl.col("policy").is_in(["budget-1000", "budget-2000", NIGHT_ONLY])
).with_columns(
    label=pl.col("policy")
    .str.replace("budget-", "")
    .cast(pl.Int32)
    .map_elements(lambda bikes: f"{bikes:,}", return_dtype=pl.String)
)
recommended = points.filter(pl.col("policy") == RECOMMENDED)

figure_8 = (
    ggplot()
    + geom_path(
        aes("bikes_moved_per_day", "shortages_per_day", color="kind"),
        data=budget_curve,
        size=0.8,
    )
    + geom_path(
        aes("bikes_moved_per_day", "shortages_per_day", color="kind"),
        data=midday_curve,
        size=0.8,
    )
    + geom_point(
        aes("bikes_moved_per_day", "shortages_per_day", color="kind"),
        data=budget_curve,
        size=1.4,
    )
    + geom_point(
        aes("bikes_moved_per_day", "shortages_per_day", color="kind"),
        data=midday_curve.tail(-1),
        size=1.4,
    )
    + geom_text(
        aes("bikes_moved_per_day", "shortages_per_day", label="label"),
        data=budget_labels,
        size=6,
        nudge_y=0.05 * top,
        color=MUTED,
        family=FONT,
    )
    + geom_point(
        aes("bikes_moved_per_day", "shortages_per_day"), data=simple, color=MUTED, size=2.2
    )
    + geom_text(
        aes("label_x", "label_y", label="label", ha="ha"),
        data=simple,
        size=6.5,
        color=MUTED,
        family=FONT,
    )
    + geom_point(
        aes("bikes_moved_per_day", "shortages_per_day"),
        data=recommended,
        color=DARK_BLUE,
        size=5.5,
        fill="white",
        stroke=1.2,
    )
    + geom_point(
        aes("bikes_moved_per_day", "shortages_per_day"),
        data=recommended,
        color=DARK_BLUE,
        size=2,
    )
    + annotate(
        "text",
        x=float(recommended["bikes_moved_per_day"].item()) + 60,
        y=float(recommended["shortages_per_day"].item()) - 0.12 * top,
        label=f"recommended: budget {NIGHT_BUDGET}\n+ 100 stations at 14:00",
        ha="left",
        size=7,
        color=INK,
        fontweight="bold",
        family=FONT,
    )
    + annotate(
        "text",
        x=30,
        y=top * 0.99,
        label=off_chart_note,
        ha="left",
        va="top",
        size=6,
        color=MUTED,
        family=FONT,
    )
    + geom_vline(
        xintercept=reported_per_day, color=CONTEXT, linetype="dashed", size=0.4
    )
    + annotate(
        "text",
        x=reported_per_day + 50,
        y=top * 0.62,
        label=f"Citi Bike's reported moves,\n{reported_per_day:,.0f} a day",
        ha="left",
        size=6.5,
        color=MUTED,
        family=FONT,
    )
    + scale_color_manual(values={"nightly budget": BLUE, MIDDAY_LABEL: DARK_BLUE})
    + scale_x_continuous(
        labels=lambda values: [f"{float(value):,.0f}" for value in values]
    )
    + scale_y_continuous(
        labels=lambda values: [f"{float(value):,.0f}" for value in values],
        limits=(0, top),
    )
    + labs(
        title="Moving fewer bikes, to the right stations, prevents more shortages than moving many",
        subtitle="Test year, October 2025 to September 2026. Numbers on the curve: night budget in bikes loaded or unloaded",
        x="bikes moved per day",
        y="riders turned away per day",
        color="",
    )
    + REPORT_THEME
    + theme(figure_size=(6.7, 3.5))
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
        alpha=0.85,
        stroke=0,
    )
    + scale_size_area(max_size=4, breaks=[2, 10, 20])
    + scale_color_gradient2(
        low=LOSING_RED,
        mid=CONTEXT,
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
    NIGHT_ONLY: "budget, nights only",
    RECOMMENDED: "recommended",
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
    ggplot(by_hour, aes("hour", "shortages", color="schedule", linetype="schedule"))
    + geom_area(
        data=by_hour.filter(pl.col("schedule") == "recommended"),
        fill=BLUE,
        alpha=0.12,
        color="none",
        show_legend=False,
    )
    + geom_line(size=0.8)
    + scale_linetype_manual(
        values={
            "reset to half": "solid",
            "budget, nights only": "solid",
            "recommended": "solid",
            "band known in advance": "dashed",
        }
    )
    + scale_color_manual(
        values={
            "reset to half": CONTEXT,
            "budget, nights only": ORANGE,
            "recommended": BLUE,
            "band known in advance": INK,
        }
    )
    + guides(color=guide_legend(ncol=2), linetype=guide_legend(ncol=2))
    + scale_x_continuous(
        breaks=range(0, 24, 6), labels=[f"{hour:02d}:00" for hour in range(0, 24, 6)]
    )
    + labs(
        title="Half full fails in the morning rush",
        subtitle="Riders turned away per hour, test-year average",
        x="",
        y="per hour",
        color="",
        linetype="",
    )
    + REPORT_THEME
    + theme(figure_size=(3.35, 2.9), plot_title=element_text(size=8.5))
)
figure_10.save(FIGURES / "fig12-shortages-by-hour.png", verbose=False)

# %% [markdown]
# ## Figure 13: bikes moved per month against what Citi Bike reports it moved

# %%
moved_by_day = (
    np.maximum(simulation["pickups_by_day"], simulation["dropoffs_by_day"])
    + simulation["midday_moves_by_day"] / 2
)
months = pl.Series("month", days).dt.truncate("1mo")
simulated = pl.concat(
    [
        pl.DataFrame(
            {"month": months, "bikes": moved_by_day[position[name]], "source": label}
        )
        .group_by("month", "source")
        .agg(pl.col("bikes").mean())
        for name, label in (
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
print(comparison.sort("month"))
recommended_in_reported_months = pl.DataFrame(
    {"month": months, "bikes": moved_by_day[position[RECOMMENDED]]}
).filter(pl.col("month").is_in(reported["month"].implode()))
print(
    "test year, months with a report: Citi Bike moved",
    round(reported_per_day),
    "a day; recommended",
    round(cast(float, recommended_in_reported_months["bikes"].mean())),
    "; correlation across months",
    round(
        comparison.select(
            pl.corr("Citi Bike, reported", "recommended (simulated)")
        ).item(),
        2,
    ),
)
figure_13 = (
    ggplot(monthly_moves.sort("month"), aes("month", "bikes", color="source"))
    + geom_line(size=0.8)
    + geom_point(size=1.6, fill="white", stroke=0.8, shape="o")
    + scale_color_manual(
        values={
            "Citi Bike, reported": INK,
            "recommended (simulated)": BLUE,
            "reset to half (simulated)": CONTEXT,
        }
    )
    + scale_x_date(date_labels="%b %y", date_breaks="3 months")
    + scale_y_continuous(
        labels=lambda values: [f"{float(value):,.0f}" for value in values],
        limits=(0, cast(float, monthly_moves["bikes"].max()) * 1.08),
    )
    + guides(color=guide_legend(ncol=1))
    + labs(
        title="Our moves follow Citi Bike's own through the year",
        subtitle="Bikes moved per day; May 2026 report not posted",
        x="",
        y="per day",
        color="",
    )
    + REPORT_THEME
    + theme(figure_size=(3.35, 2.9), plot_title=element_text(size=8.5))
)
figure_13.save(FIGURES / "fig13-moves-vs-reported.png", verbose=False)

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
    "swing beats its docks": "9 Ave & W 33 St",
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
                    "stock": stock_path[:, k].astype(np.float64),
                    "schedule": schedule,
                    "station": f"{station_name}\n{kind}, {capacity[rows[k]]} docks",
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
    + geom_area(
        data=trace.filter(pl.col("schedule") == "recommended"),
        fill=BLUE,
        alpha=0.1,
        color="none",
        show_legend=False,
    )
    + geom_line(size=0.8)
    + facet_wrap("station", ncol=3, scales="free_y")
    + scale_color_manual(values={"reset to half": CONTEXT, "recommended": BLUE})
    + scale_x_continuous(
        breaks=[0, 4, 8, 12, 16, 20],
        labels=["04:00", "08:00", "12:00", "16:00", "20:00", "00:00"],
    )
    + labs(
        title="Half full is the wrong start at a commuter station, and some stations no start can save",
        subtitle="Bikes docked through Tuesday 12 May 2026. Dashed: the station's docks; a line flat at the dashes or at zero is turning riders away",
        x="",
        y="bikes in the station",
        color="",
    )
    + REPORT_THEME
    + theme(figure_size=(6.7, 2.9), strip_text=element_text(size=6.8))
)
figure_11.save(FIGURES / "fig8-one-day.png", verbose=False)
