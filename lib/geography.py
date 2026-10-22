"""Where stations are: the land outline for maps, and the neighbourhood each station sits in.

Boundaries come from NYC Open Data (2020 neighbourhood tabulation areas, borough boundaries) and
from New Jersey's municipal boundaries for Hudson County, all saved in data/raw/boundaries/.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from matplotlib.path import Path as Outline

# Hudson County's file names its towns in capitals with a suffix
NEW_JERSEY_NAMES = {"JERSEY CITY": "Jersey City", "HOBOKEN CITY": "Hoboken"}


def outer_rings(geometry: dict[str, Any]) -> list[list[list[float]]]:
    """The outer ring of each polygon in a GeoJSON Polygon or MultiPolygon, as [lng, lat] points."""
    polygons = (
        geometry["coordinates"]
        if geometry["type"] == "MultiPolygon"
        else [geometry["coordinates"]]
    )
    return [polygon[0] for polygon in polygons]


def land_outline(boundaries_dir: Path) -> pl.DataFrame:
    """The city's land as polygon rings: lng, lat, and a `ring` id per closed outline."""
    rings: list[pl.DataFrame] = []
    for file in ("nyc-boroughs.geojson", "hudson.geojson"):
        for feature in json.loads((boundaries_dir / file).read_text())["features"]:
            for ring in outer_rings(feature["geometry"]):
                points = np.array(ring)
                rings.append(
                    pl.DataFrame(
                        {
                            "lng": points[:, 0],
                            "lat": points[:, 1],
                            "ring": f"ring-{len(rings)}",
                        }
                    )
                )
    return pl.concat(rings)


def station_areas(stations: pl.DataFrame, boundaries_dir: Path) -> pl.DataFrame:
    """`stations` with its `neighbourhood` and `borough` added, null where a station is in neither file.

    New Jersey stations get their town (Jersey City, Hoboken) as both neighbourhood and borough.
    """
    points = stations.select("lng", "lat").to_numpy()
    neighbourhood = np.full(len(points), None, dtype=object)
    borough = np.full(len(points), None, dtype=object)
    areas = json.loads((boundaries_dir / "nyc-nta2020.geojson").read_text())["features"]
    towns = json.loads((boundaries_dir / "hudson.geojson").read_text())["features"]
    for feature in areas + towns:
        properties = feature["properties"]
        town = NEW_JERSEY_NAMES.get(properties.get("MUN", ""), properties.get("MUN"))
        name = properties.get("ntaname", town)
        for ring in outer_rings(feature["geometry"]):
            inside = Outline(np.array(ring)).contains_points(points)
            neighbourhood[inside] = name
            borough[inside] = properties.get("boroname", town)
    return stations.with_columns(
        neighbourhood=pl.Series(neighbourhood, dtype=pl.String),
        borough=pl.Series(borough, dtype=pl.String),
    )
