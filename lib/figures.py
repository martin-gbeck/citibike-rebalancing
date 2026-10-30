"""The report's 13 figures. Each function takes the table the notebook computed and returns the
chart; the analysis behind each table is in `walkthrough.py`, the look in `chart_style.py`."""

from typing import cast

import polars as pl
from plotnine import (
    aes,
    annotate,
    coord_fixed,
    coord_flip,
    element_blank,
    element_line,
    element_text,
    facet_wrap,
    geom_abline,
    geom_area,
    geom_bin_2d,
    geom_col,
    geom_hline,
    geom_label,
    geom_line,
    geom_point,
    geom_ribbon,
    geom_segment,
    geom_text,
    geom_tile,
    geom_vline,
    ggplot,
    guide_legend,
    guides,
    labs,
    scale_color_gradient2,
    scale_color_manual,
    scale_fill_gradient,
    scale_fill_gradient2,
    scale_fill_manual,
    scale_linetype_manual,
    scale_size_area,
    scale_size_continuous,
    scale_x_continuous,
    scale_x_date,
    scale_x_discrete,
    scale_y_continuous,
    theme,
)

from lib.chart_style import (
    BLUE,
    CONTEXT,
    DARK_BLUE,
    FONT,
    INK,
    LIGHT_CONTEXT,
    LOSING_RED,
    MAP_THEME,
    MUTED,
    NEUTRAL,
    ORANGE,
    PALE_BLUE,
    REPORT_THEME,
    SHADE,
    on_map,
)

# the maps all frame the same box: Manhattan, Brooklyn, western Queens and Jersey City
MAP_LNG = (-74.07, -73.87)
MAP_LAT = (40.64, 40.86)


def daily_rhythm(by_hour: pl.DataFrame) -> ggplot:
    """Figure 1. `by_hour`: mean trips started per day type, hour of day and rider type."""
    # each line is named where it runs, in the workday panel, instead of in a legend
    rider_labels = pl.DataFrame(
        {
            "day_type": ["workday", "workday"],
            "hour_of_day": [9.4, 11.5],
            "starts": [9_000.0, 2_000.0],
            "rider": ["annual members", "casual riders"],
        }
    ).with_columns(pl.col("day_type").cast(by_hour.schema["day_type"]))
    return (
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
            labels=lambda values: [f"{value:,.0f}" for value in values],
            expand=(0, 0, 0.05, 0),
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


def rush_map(rush: pl.DataFrame, land: pl.DataFrame) -> ggplot:
    """Figure 2. `rush`: each station's `rush_net_flow` per workday rush, with its position."""
    return (
        on_map(ggplot(), land, lng=MAP_LNG, lat=MAP_LAT)
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


def neighbourhood_clock(clock: pl.DataFrame) -> ggplot:
    """Figure 3. `clock`: net flow per neighbourhood `label` and hour, rows already ordered."""
    return (
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


def habit(halves: pl.DataFrame, correlation: float) -> ggplot:
    """Figure 4. `halves`: each station's morning net flow per day in `odd` and `even` weeks."""
    return (
        ggplot(
            halves.with_columns(tint=pl.col("odd").clip(-30, 30)), aes("odd", "even")
        )
        + geom_abline(color=CONTEXT, linetype="dashed", size=0.4)
        + geom_point(aes(color="tint"), alpha=0.6, size=0.9, stroke=0)
        + annotate(
            "text",
            x=-75,
            y=95,
            label=f"r = {correlation:.3f}",
            ha="left",
            size=8,
            fontweight="bold",
            color=INK,
            family=FONT,
        )
        + scale_color_gradient2(
            low=LOSING_RED,
            mid=CONTEXT,
            high=BLUE,
            midpoint=0,
            limits=(-30, 30),
            guide=None,
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


def single_day(morning_days: pl.DataFrame, correlation: float) -> ggplot:
    """Figure 5. `morning_days`: each station-day's morning `net_flow` and its `last_10` average.
    Draws a fixed random 30,000 of them."""
    return (
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
            label=f"r = {correlation:.2f}",
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


def demand_fit(test_days: pl.DataFrame, r2: float, median_miss: float) -> ggplot:
    """Figure 6. `test_days`: predicted and actual trips per test day, with its `kind` of day.
    `median_miss` is a share, shaded as a band either side of a perfect forecast."""
    diagonal = pl.DataFrame({"trips": [0.0, 230_000.0]}).with_columns(
        low=pl.col("trips") * (1 - median_miss),
        high=pl.col("trips") * (1 + median_miss),
    )
    thousands = lambda values: [f"{float(value) / 1000:,.0f}k" for value in values]
    return (
        ggplot(test_days, aes("predicted", "trips"))
        + geom_ribbon(
            aes(x="trips", ymin="low", ymax="high"),
            data=diagonal,
            inherit_aes=False,
            fill=SHADE,
        )
        + geom_abline(intercept=0, slope=1, color=CONTEXT, size=0.4, linetype="dashed")
        + geom_point(aes(color="kind"), size=1.1, alpha=0.75, stroke=0)
        + annotate(
            "text",
            x=12_000,
            y=222_000,
            label=f"R² {r2:.2f}\nhalf of all days within {median_miss:.0%}",
            ha="left",
            va="top",
            size=6.5,
            color=INK,
            family=FONT,
        )
        + scale_color_manual(
            values={"workday": BLUE, "weekend": ORANGE, "Christmas week": INK},
            breaks=["workday", "weekend", "Christmas week"],
        )
        + scale_x_continuous(labels=thousands, limits=(0, 230_000), expand=(0, 0))
        + scale_y_continuous(labels=thousands, limits=(0, 230_000), expand=(0, 0))
        + coord_fixed()
        + labs(
            title="Half of all test days land within 11%",
            subtitle="Trips per day, test year; dashed: a perfect forecast",
            x="predicted",
            y="actual",
            color="",
        )
        + REPORT_THEME
        + theme(
            figure_size=(3.35, 3.0),
            plot_title=element_text(size=8.5),
            panel_grid_major_x=element_line(color="#ebe9e4", size=0.4),
            legend_text=element_text(size=6.5),
            legend_position="bottom",
            legend_box_spacing=0.02,
        )
    )


def demand_effects(effects: pl.DataFrame, order: list[str]) -> ggplot:
    """Figure 7. `effects`: each factor's `effect` on a day's trips in %, with `low` and `high`
    ends of its 95% interval. `order` lists the factors top to bottom."""
    effect_table = effects.with_columns(
        pl.col("factor").cast(pl.Enum(order[::-1])),
        direction=pl.when(pl.col("effect") >= 0)
        .then(pl.lit("more"))
        .otherwise(pl.lit("fewer")),
        value_label=pl.format(
            "{}%", pl.col("effect").round(0).cast(pl.Int32)
        ).str.replace(r"^(\d)", "+$1"),
        # the number sits just past the end of the interval, on the side away from zero
        label_x=pl.when(pl.col("effect") >= 0)
        .then(pl.col("high") + 3)
        .otherwise(pl.col("low") - 3),
        label_ha=pl.when(pl.col("effect") >= 0)
        .then(pl.lit("left"))
        .otherwise(pl.lit("right")),
    )
    return (
        ggplot(effect_table, aes("effect", "factor", color="direction"))
        + geom_vline(xintercept=0, color=CONTEXT, size=0.5)
        + geom_segment(aes(x=0, xend="effect", yend="factor"), size=2.2, alpha=0.25)
        + geom_segment(aes(x="low", xend="high", yend="factor"), size=0.7)
        + geom_point(size=2.4)
        + geom_text(
            aes(label="value_label", x="label_x", ha="label_ha"),
            size=6.5,
            fontweight="bold",
            color=INK,
            family=FONT,
        )
        + scale_color_manual(values={"more": BLUE, "fewer": LOSING_RED}, guide=None)
        + scale_x_continuous(
            limits=(-62, 36),
            labels=lambda values: [
                f"{value:+.0f}%" if value else "0" for value in values
            ],
        )
        + labs(
            title="What moves a day's riding",
            subtitle="Change in the day's trips, with 95% intervals",
            x="",
            y="",
        )
        + REPORT_THEME
        + theme(
            figure_size=(3.35, 2.6),
            plot_title=element_text(size=8.5),
            axis_text_y=element_text(color=INK),
            panel_grid_major_y=element_blank(),
            panel_grid_major_x=element_line(color="#ebe9e4", size=0.4),
            axis_line_x=element_blank(),
        )
    )


def one_day(trace: pl.DataFrame, docks: pl.DataFrame) -> ggplot:
    """Figure 8. `trace`: bikes in each example `station` every 5 minutes from 04:00, per
    `schedule`. `docks`: each station's dock count, drawn as its limit."""
    return (
        ggplot(trace, aes("hours_from_4", "stock", color="schedule"))
        + geom_hline(
            aes(yintercept="docks"),
            data=docks,
            color=CONTEXT,
            linetype="dashed",
            size=0.4,
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


def tradeoff(
    summary: pl.DataFrame,
    schedule_names: dict[str, str],
    recommended: str,
    reported_per_day: float,
) -> ggplot:
    """Figure 9. `summary`: the test-year result per policy. `schedule_names` picks the policies
    and names them, top to bottom; `reported_per_day` is Citi Bike's own figure, drawn as a line."""
    turned_away_label = "riders turned away per day"
    moved_label = "bikes moved per day"
    # the shortage panel stops just past the half-full reset; never moving a bike runs off it
    shortage_limit = 5_600
    schedules = (
        summary.filter(pl.col("policy").is_in(list(schedule_names)))
        .select(
            schedule=pl.col("policy").replace_strict(schedule_names),
            role=pl.when(pl.col("policy") == recommended)
            .then(pl.lit("recommended"))
            .when(pl.col("policy") == "oracle")
            .then(pl.lit("ceiling"))
            .otherwise(pl.lit("other")),
            turned_away=pl.col("shortages_per_day"),
            moved=pl.col("bikes_moved_per_day"),
        )
        .unpivot(
            index=["schedule", "role"], variable_name="measure", value_name="value"
        )
        .with_columns(
            measure=pl.col("measure")
            .replace_strict({"turned_away": turned_away_label, "moved": moved_label})
            .cast(pl.Enum([turned_away_label, moved_label])),
            # bottom to top on the chart, so the list reads top down in the order above
            schedule=pl.col("schedule").cast(
                pl.Enum(list(reversed(schedule_names.values())))
            ),
            shown=pl.when(pl.col("measure") == "turned_away")
            .then(pl.col("value").clip(upper_bound=shortage_limit))
            .otherwise(pl.col("value")),
            label=pl.col("value").map_elements(
                lambda value: f"{int(value + 0.5):,}", return_dtype=pl.String
            ),
        )
        .with_columns(
            label=pl.when(pl.col("value") > pl.col("shown"))
            .then(pl.col("label") + ", bar cut")
            .otherwise(pl.col("label")),
            label_y=pl.col("shown") + 120,
            cut=pl.col("value") > pl.col("shown"),
        )
    )
    reported_line = pl.DataFrame(
        {"measure": [moved_label], "value": [reported_per_day]}
    ).with_columns(pl.col("measure").cast(pl.Enum([turned_away_label, moved_label])))
    return (
        ggplot(schedules, aes("schedule", "shown", fill="role"))
        + geom_hline(
            aes(yintercept="value"),
            data=reported_line,
            color=INK,
            linetype="dashed",
            size=0.4,
        )
        + geom_col(width=0.68)
        + geom_label(
            aes(y="label_y", label="label"),
            data=schedules.filter(~pl.col("cut")),
            ha="left",
            size=6.5,
            color=INK,
            fill="white",
            label_size=0,
            label_padding=0.1,
            family=FONT,
        )
        + geom_text(
            aes(y="shown", label="label"),
            data=schedules.filter(pl.col("cut")),
            ha="right",
            nudge_y=-120,
            size=6.5,
            color="white",
            family=FONT,
        )
        + geom_text(
            aes(x=6.6, y="value", label="label"),
            data=reported_line.with_columns(
                label=pl.lit(f"Citi Bike today: {reported_per_day:,.0f}")
            ),
            inherit_aes=False,
            ha="left",
            nudge_y=90,
            size=6,
            color=MUTED,
            family=FONT,
        )
        + facet_wrap("measure")
        + coord_flip()
        + scale_fill_manual(
            values={"recommended": BLUE, "ceiling": LIGHT_CONTEXT, "other": CONTEXT},
            guide=None,
        )
        + scale_y_continuous(
            labels=lambda values: [f"{float(value):,.0f}" for value in values],
            limits=(0, 7_000),
            breaks=[0, 2_000, 4_000, 6_000],
            expand=(0, 0),
        )
        + scale_x_discrete(expand=(0, 0.6))
        + labs(
            title="Recommended: 62% fewer riders turned away than half full, with 57% fewer bikes moved",
            subtitle="Test-year averages. Band known in advance is a ceiling no real forecast reaches",
            x="",
            y="",
        )
        + REPORT_THEME
        + theme(
            figure_size=(6.7, 2.6),
            panel_grid_major_y=element_blank(),
            panel_grid_major_x=element_line(color="#ebe9e4", size=0.4),
            axis_line_x=element_blank(),
            axis_text_y=element_text(size=7.5, color=INK),
            panel_spacing_x=0.04,
        )
    )


def where_vans_go(per_night: pl.DataFrame, land: pl.DataFrame) -> ggplot:
    """Figure 10. `per_night`: bikes `dropped` and `picked` per day at each station, and their
    sum `handled`. Stations handling half a bike a day or less are drawn grey."""
    return (
        on_map(ggplot(), land, lng=MAP_LNG, lat=MAP_LAT)
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
            .with_columns(
                net_dropped=(pl.col("dropped") - pl.col("picked")).clip(-4, 4)
            )
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


def shortages_left(per_night: pl.DataFrame, land: pl.DataFrame) -> ggplot:
    """Figure 11. `per_night`: riders turned away per day at each station. Stations with half a
    rider a day or more get a dot sized by it."""
    leftover = per_night.filter(pl.col("shortages") >= 0.5).sort("shortages")
    return (
        on_map(ggplot(), land, lng=MAP_LNG, lat=MAP_LAT)
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


def shortages_by_hour(by_hour: pl.DataFrame) -> ggplot:
    """Figure 12. `by_hour`: riders turned away per hour of the day under each `schedule`."""
    return (
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
            breaks=range(0, 24, 6),
            labels=[f"{hour:02d}:00" for hour in range(0, 24, 6)],
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


def moves_vs_reported(monthly_moves: pl.DataFrame) -> ggplot:
    """Figure 13. `monthly_moves`: bikes moved per day in each month, per `source`."""
    return (
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
