"""Turn the 24 months of raw trips into the small tables every analysis script reads.

Writes to data/processed/:
- bins/YYYYMM.parquet: starts and ends at each station in each 5-minute slot that had any
- stations.parquet: one row per public station, with name, coordinates and docks
- routes_dev.parquet: trips between each pair of stations in the development year, by time of day
- trips/YYYYMM.parquet: every trip from a public station, with its start and end slot, for the
  simulation in which a rider turned away at the start never arrives at the end

Runs one month at a time, so memory stays near one month of trips. Pass months as YYYYMM
(`python prepare_data.py 202510`) to build only those.
"""

import os

# six of the ten cores leave the machine usable while this runs; set before polars is imported
os.environ["POLARS_MAX_THREADS"] = "6"

import sys
from datetime import date, datetime
from itertools import pairwise
from pathlib import Path

import polars as pl

from lib.data_schemas import Station
from lib.fetching import fetch_station_capacity, fetch_trip_month

RAW = Path("data/raw")
PROCESSED = Path("data/processed")
TEST_START = datetime(2025, 10, 1)
# the depot's charging hub has an id shaped like a public dock's
CHARGING_HUB = "1234.56"


def public_station_id(column: str) -> pl.Expr:
    """The station's usual id, or null when the id belongs to one of Citi Bike's own sites.

    One-decimal ids get their trailing zero back (5980.1 is 5980.10), temporary `_` and `_old`
    endings are dropped, and depots, warehouses, labs and demo units become null.
    """
    station_id = pl.col(column).str.replace(r"_(old)?$", "")
    station_id = (
        pl.when(station_id.str.contains(r"^\d+\.\d$"))
        .then(station_id + "0")
        .otherwise(station_id)
    )
    is_public = station_id.str.contains(r"^(\d+\.\d{2}|JC\d+|HB\d+)$") & (
        station_id != CHARGING_HUB
    )
    return pl.when(is_public).then(station_id)


month_starts = pl.datetime_range(
    datetime(2024, 10, 1), datetime(2026, 10, 1), "1mo", eager=True
).to_list()
trip_files = [
    fetch_trip_month(month.date(), RAW / "tripdata.nosync")
    for month in month_starts[:-1]
]
# each file holds the trips that ended in its month; April 2026's also repeats 512 trips that
# ended in May, so a trip is kept only from the file of the month it ended
trips = (
    pl.scan_parquet(trip_files, include_file_paths="file")
    .filter(
        pl.col("file").str.extract(r"(\d{6})-citibike")
        == pl.col("ended_at").dt.strftime("%Y%m")
    )
    .drop("file")
    .with_columns(
        start_station_id=public_station_id("start_station_id"),
        end_station_id=public_station_id("end_station_id"),
    )
)

wanted = set(sys.argv[1:])
(PROCESSED / "bins").mkdir(parents=True, exist_ok=True)
(PROCESSED / "trips").mkdir(parents=True, exist_ok=True)
station_points: list[pl.DataFrame] = []
route_months: list[pl.DataFrame] = []
for month_start, next_month_start in pairwise(month_starts):
    label = f"{month_start:%Y%m}"
    if wanted and label not in wanted:
        continue
    started_in_month = pl.col("started_at").is_between(
        month_start, next_month_start, closed="left"
    )
    ended_in_month = pl.col("ended_at").is_between(
        month_start, next_month_start, closed="left"
    )
    starts = (
        trips.filter(started_in_month)
        .drop_nulls("start_station_id")
        .group_by(
            station_id="start_station_id", slot=pl.col("started_at").dt.truncate("5m")
        )
        .agg(
            pl.len().alias("starts"),
            (pl.col("member_casual") == "member").sum().alias("member_starts"),
            (pl.col("rideable_type") == "electric_bike").sum().alias("ebike_starts"),
        )
    )
    ends = (
        trips.filter(ended_in_month)
        .drop_nulls("end_station_id")
        .group_by(
            station_id="end_station_id", slot=pl.col("ended_at").dt.truncate("5m")
        )
        .agg(pl.len().alias("ends"))
    )
    (
        starts.join(ends, on=["station_id", "slot"], how="full", coalesce=True)
        # counts come out unsigned, and ends - starts would wrap around instead of going negative
        .with_columns(
            pl.col("starts", "member_starts", "ebike_starts", "ends")
            .fill_null(0)
            .cast(pl.Int16)
        )
        .sort("station_id", "slot")
        .collect(engine="streaming")
        .write_parquet(PROCESSED / "bins" / f"{label}.parquet")
    )

    # every trip end is a sighting of its station: name and coordinates, for the station table
    month_trips = trips.filter(ended_in_month)
    station_points.append(
        pl.concat(
            [
                month_trips.select(
                    station_id="start_station_id",
                    name="start_station_name",
                    lat="start_lat",
                    lng="start_lng",
                ),
                month_trips.select(
                    station_id="end_station_id",
                    name="end_station_name",
                    lat="end_lat",
                    lng="end_lng",
                ),
            ]
        )
        .drop_nulls("station_id")
        .group_by("station_id", "name")
        .agg(
            pl.len().alias("sightings"),
            pl.col("lat").median(),
            pl.col("lng").median(),
        )
        .collect(engine="streaming")
    )

    (
        trips.filter(started_in_month)
        .drop_nulls("start_station_id")
        .select(
            "start_station_id",
            "end_station_id",
            start_slot=pl.col("started_at").dt.truncate("5m"),
            end_slot=pl.col("ended_at").dt.truncate("5m"),
        )
        .collect(engine="streaming")
        .write_parquet(PROCESSED / "trips" / f"{label}.parquet")
    )

    if month_start < TEST_START:
        hour_of_day = pl.col("started_at").dt.hour()
        route_months.append(
            trips.filter(started_in_month)
            .drop_nulls(["start_station_id", "end_station_id"])
            .filter(pl.col("start_station_id") != pl.col("end_station_id"))
            .with_columns(
                period=pl.when(pl.col("started_at").dt.weekday() > 5)
                .then(pl.lit("weekend"))
                .when(hour_of_day.is_between(7, 9))
                .then(pl.lit("weekday-morning-rush"))
                .when(hour_of_day.is_between(16, 18))
                .then(pl.lit("weekday-evening-rush"))
                .otherwise(pl.lit("weekday-other"))
            )
            .group_by("start_station_id", "end_station_id", "period")
            .agg(pl.len().alias("trips"))
            .collect(engine="streaming")
        )
    print(f"{label} done", flush=True)

if wanted:
    sys.exit()

# a station's name is the one most of its trips used, its position the median over those trips
points = pl.concat(station_points)
names = (
    points.group_by("station_id", "name")
    .agg(pl.col("sightings").sum())
    .sort("sightings", descending=True)
    .group_by("station_id")
    .agg(pl.col("name").first())
)
positions = points.group_by("station_id").agg(
    # weighted medians are not built in, so take the sighting-weighted mean of monthly medians
    (pl.col("lat") * pl.col("sightings")).sum() / pl.col("sightings").sum(),
    (pl.col("lng") * pl.col("sightings")).sum() / pl.col("sightings").sum(),
    pl.col("sightings").sum().alias("trip_ends"),
)
# 35 feed stations list 0 docks, which on the day of the pull means out of service
feed = fetch_station_capacity(RAW).with_columns(
    capacity=pl.when(pl.col("capacity") > 0).then(pl.col("capacity"))
)
# renumbered stations keep their name, so a name held by exactly one feed station also matches
feed_by_name = feed.filter(pl.col("feed_name").is_unique()).select(
    name="feed_name", capacity_by_name="capacity"
)
stations = (
    names.join(positions, on="station_id")
    .join(feed.select("station_id", "capacity"), on="station_id", how="left")
    .join(feed_by_name, on="name", how="left")
    .with_columns(capacity=pl.coalesce("capacity", "capacity_by_name"))
)
Station.validate(stations.with_columns(pl.col("station_id").cast(pl.Categorical)))
stations.drop("capacity_by_name").write_parquet(PROCESSED / "stations.parquet")

pl.concat(route_months).group_by("start_station_id", "end_station_id", "period").agg(
    pl.col("trips").sum()
).write_parquet(PROCESSED / "routes_dev.parquet")
print(f"done {date.today()}")
