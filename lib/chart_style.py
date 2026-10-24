"""One look for every report figure: palette, print-sized theme, and the land and water behind the maps."""

from pathlib import Path

import polars as pl
from plotnine import (
    aes,
    coord_fixed,
    element_blank,
    element_line,
    element_rect,
    element_text,
    geom_polygon,
    ggplot,
    theme,
    theme_minimal,
)

FIGURES = Path("figures")

# blue is the commuter side and stations gaining bikes, red stations losing them, orange the leisure
# side (weekends, casual riders), grey is context. Blue, dark blue, orange and red pass the dataviz
# validator's colour-blind and contrast checks against white.
BLUE = "#3b7dd8"
DARK_BLUE = "#1f4f99"
PALE_BLUE = "#e3ecf8"
ORANGE = "#d4692a"
LOSING_RED = "#c9403a"
CONTEXT = "#9a978f"
LIGHT_CONTEXT = "#d6d3cc"
NEUTRAL = "#eeece7"
LAND = "#f7f5f0"
WATER = "#dde7ef"
SHADE = "#f3f1ec"
INK = "#22252a"
MUTED = "#6b6e75"
FONT = "Avenir Next"

# the report's text block is 170 mm wide; figures are drawn at that width and printed unscaled
FULL_WIDTH = 6.7
REPORT_THEME = theme_minimal(base_size=8, base_family=FONT) + theme(
    figure_size=(FULL_WIDTH, 3.0),
    dpi=300,
    plot_background=element_rect(fill="white", color="none"),
    plot_title=element_text(size=9.5, weight="bold", ha="left", color=INK),
    plot_subtitle=element_text(size=7.5, color=MUTED, ha="left"),
    plot_title_position="plot",
    text=element_text(color=INK, family=FONT),
    axis_title=element_text(size=7.5, color=MUTED),
    axis_text=element_text(size=7, color=MUTED),
    axis_line_x=element_line(color="#b9b6ae", size=0.5),
    axis_ticks=element_blank(),
    panel_grid_minor=element_blank(),
    panel_grid_major_x=element_blank(),
    panel_grid_major_y=element_line(color="#ebe9e4", size=0.4),
    legend_position="top",
    legend_justification="left",
    legend_title=element_text(size=7.5, color=MUTED),
    legend_text=element_text(size=7.5, color=INK),
    legend_key=element_blank(),
    strip_text=element_text(size=8, weight="bold", ha="left", color=INK),
    strip_background=element_blank(),
)

# one degree of longitude is shorter than one of latitude at New York's 40.7 degrees north
LNG_PER_LAT = 1 / 0.758
MAP_THEME = theme(
    axis_text=element_blank(),
    axis_title=element_blank(),
    axis_line_x=element_blank(),
    panel_grid_major_y=element_blank(),
    panel_background=element_rect(fill=WATER, color="none"),
    legend_key=element_rect(fill="white", color="none"),
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
            color="#d9d5cc",
            size=0.15,
        )
        + coord_fixed(ratio=LNG_PER_LAT, xlim=lng, ylim=lat, expand=False)
    )
