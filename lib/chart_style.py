"""One look for every report figure: palette, print-sized theme, and the land behind the maps."""

from pathlib import Path

import polars as pl
from plotnine import (
    aes,
    coord_fixed,
    element_blank,
    element_line,
    element_text,
    geom_polygon,
    ggplot,
    theme,
    theme_minimal,
)

FIGURES = Path("figures")

# blue is the commuter side and stations gaining bikes, red stations losing them, orange the leisure
# side (weekends, casual riders) and the midday van, grey is context
BLUE = "#2a78d6"
DARK_BLUE = "#174a8b"
ORANGE = "#eb6834"
LOSING_RED = "#e34948"
CONTEXT = "#9c9a92"
LIGHT_CONTEXT = "#d9d7d0"
NEUTRAL = "#f0efec"
LAND = "#efeee9"
INK = "#1d1d1b"

# the report's text block is 170 mm wide; figures are drawn at that width and printed unscaled
FULL_WIDTH = 6.7
REPORT_THEME = theme_minimal(base_size=8) + theme(
    figure_size=(FULL_WIDTH, 3.0),
    dpi=300,
    legend_position="top",
    legend_title=element_text(size=7.5),
    legend_text=element_text(size=7.5),
    plot_title=element_text(size=9, weight="bold", ha="left"),
    plot_subtitle=element_text(size=7.5, color="#55544f", ha="left"),
    text=element_text(color=INK),
    axis_text=element_text(color="#55544f"),
    panel_grid_minor=element_blank(),
    panel_grid_major=element_line(color="#e6e5e0", size=0.4),
    strip_text=element_text(size=8, weight="bold"),
)

# one degree of longitude is shorter than one of latitude at New York's 40.7 degrees north
LNG_PER_LAT = 1 / 0.758
MAP_THEME = theme(
    axis_text=element_blank(),
    axis_title=element_blank(),
    panel_grid_major=element_blank(),
    panel_grid_minor=element_blank(),
)


def on_map(
    plot: ggplot, land: pl.DataFrame, lng: tuple[float, float], lat: tuple[float, float]
) -> ggplot:
    """`plot` with the land drawn first, framed to the given box. Add `MAP_THEME` after the report theme."""
    return (
        plot
        + geom_polygon(
            aes("lng", "lat", group="ring"),
            data=land,
            fill=LAND,
            color="#cfcdc5",
            size=0.2,
        )
        + coord_fixed(ratio=LNG_PER_LAT, xlim=lng, ylim=lat, expand=False)
    )
