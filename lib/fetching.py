"""Pulling Citi Bike trips, station capacities and New York weather, each cached under data/raw/."""

import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import polars as pl
import requests

TRIPDATA = "https://s3.amazonaws.com/tripdata"
STATION_INFORMATION = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
# Central Park, the weather station New York's forecasts are quoted for
CENTRAL_PARK = {"latitude": 40.7812, "longitude": -73.9665}
# zstd level 9 shrinks a month of CSV to about a sixth (754 MB to 114 MB for April 2026) in under a second;
# level 3 gives 118 MB, level 15 gives 111 MB at four times the time
PARQUET_COMPRESSION_LEVEL = 9

# station ids such as 7293.10 are text: read as numbers they would lose the trailing zero
TRIP_CSV_SCHEMA = {
    "ride_id": pl.String,
    "rideable_type": pl.String,
    "started_at": pl.String,
    "ended_at": pl.String,
    "start_station_name": pl.String,
    "start_station_id": pl.String,
    "end_station_name": pl.String,
    "end_station_id": pl.String,
    "start_lat": pl.String,
    "start_lng": pl.String,
    "end_lat": pl.String,
    "end_lng": pl.String,
    "member_casual": pl.String,
}


def parse_timestamp(column: str) -> pl.Expr:
    """A trip timestamp as a datetime in New York local time, the clock the files are written in.

    Some months carry milliseconds and some do not, so only the first 19 characters are read.
    """
    return (
        pl.col(column)
        .str.slice(0, 19)
        .str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
    )


def fetch_trip_month(month: date, trip_dir: Path) -> Path:
    """One month of trips as `<S3 zip name>.parquet` in `trip_dir`, downloaded and converted if missing.

    `202604-citibike-tripdata.zip` on S3 becomes `202604-citibike-tripdata.parquet`, holding every
    trip of its CSV parts, with timestamps parsed and coordinates as numbers. Each CSV part is read
    straight out of the zip in memory, so the only thing on disk besides the result is the zip itself,
    and only while the month is converted.
    """
    name = f"{month:%Y%m}-citibike-tripdata"
    target = trip_dir / f"{name}.parquet"
    if target.exists():
        return target
    trip_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix=f"{name}-"))
    try:
        archive = work_dir / f"{name}.zip"
        with requests.get(
            f"{TRIPDATA}/{archive.name}", stream=True, timeout=60
        ) as response:
            response.raise_for_status()
            with archive.open("wb") as file:
                shutil.copyfileobj(response.raw, file, length=1 << 22)
        with zipfile.ZipFile(archive) as zipped:
            # skip the __MACOSX copies some archives carry
            parts = sorted(
                part
                for part in zipped.namelist()
                if part.endswith(".csv") and not part.startswith("__MACOSX")
            )
            trips = pl.concat(
                pl.read_csv(
                    zipped.read(part),
                    schema_overrides=TRIP_CSV_SCHEMA,
                    infer_schema=False,
                ).select(list(TRIP_CSV_SCHEMA))
                for part in parts
            )
        trips = trips.with_columns(
            parse_timestamp("started_at"),
            parse_timestamp("ended_at"),
            pl.col("start_lat", "start_lng", "end_lat", "end_lng").cast(
                pl.Float64, strict=False
            ),
        )
        # write under a temporary name, so an interrupted run never leaves a half file that looks done
        trips.write_parquet(
            work_dir / target.name,
            compression="zstd",
            compression_level=PARQUET_COMPRESSION_LEVEL,
        )
        shutil.move(work_dir / target.name, target)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    return target


def fetch_station_capacity(raw_dir: Path) -> pl.DataFrame:
    """Each station's dock count from Citi Bike's live feed, saved on first call and read back after.

    The feed only describes the network on the day it is pulled, so stations that closed earlier are
    missing and capacities that changed show their current value. `station_id` is the feed's
    `short_name`, the id the trip files use.
    """
    saved = sorted(raw_dir.glob("station_information-*.json"))
    if saved:
        path = saved[-1]
    else:
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"station_information-{date.today():%Y-%m-%d}.json"
        response = requests.get(STATION_INFORMATION, timeout=60)
        response.raise_for_status()
        path.write_text(response.text)
    stations = json.loads(path.read_text())["data"]["stations"]
    return pl.DataFrame(
        [
            {
                "station_id": station["short_name"],
                "capacity": station["capacity"],
                "feed_name": station["name"],
            }
            for station in stations
        ]
    )


def fetch_weather(start: date, end: date, raw_dir: Path) -> pl.DataFrame:
    """Hourly Central Park weather in New York local time from the Open-Meteo archive, cached as CSV.

    Columns: hour, temperature_c, precipitation_mm, snowfall_cm, wind_kmh.
    """
    path = raw_dir / f"weather-central-park-{start:%Y%m%d}-{end:%Y%m%d}.csv"
    if not path.exists():
        raw_dir.mkdir(parents=True, exist_ok=True)
        response = requests.get(
            OPEN_METEO_ARCHIVE,
            params={
                **CENTRAL_PARK,
                "start_date": f"{start:%Y-%m-%d}",
                "end_date": f"{end:%Y-%m-%d}",
                "hourly": "temperature_2m,precipitation,snowfall,wind_speed_10m",
                "timezone": "America/New_York",
                "format": "csv",
            },
            timeout=120,
        )
        response.raise_for_status()
        # the CSV opens with three lines of location metadata and a blank line before the header
        path.write_text(response.text.split("\n\n", 1)[1])
    return pl.read_csv(path).select(
        pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M").alias("hour"),
        pl.col("temperature_2m (°C)").alias("temperature_c"),
        pl.col("precipitation (mm)").alias("precipitation_mm"),
        pl.col("snowfall (cm)").alias("snowfall_cm"),
        pl.col("wind_speed_10m (km/h)").alias("wind_kmh"),
    )


# Citi Bike's monthly reports to NYC DOT, listed at https://citibikenyc.com/system-data/operating-reports;
# the file names are not regular, so they are spelled out. May 2026 is not posted
OPERATING_REPORTS = (
    "https://mot-marketing-whitelabel-prod.s3.us-east-1.amazonaws.com/nyc"
)
OPERATING_REPORT_FILES = {
    date(2025, 1, 1): "JAN-2025", date(2025, 2, 1): "February-2025", date(2025, 3, 1): "March-2025",
    date(2025, 4, 1): "April-2025", date(2025, 5, 1): "May-2025", date(2025, 6, 1): "June-2025",
    date(2025, 7, 1): "July-2025", date(2025, 8, 1): "August-2025", date(2025, 9, 1): "September-2025",
    date(2025, 10, 1): "October-2025", date(2025, 11, 1): "November-2025",
    date(2025, 12, 1): "December-2025", date(2026, 1, 1): "January-2026",
    date(2026, 2, 1): "February-2026", date(2026, 3, 1): "March-2026", date(2026, 4, 1): "April-2026",
    date(2026, 6, 1): "June-2026", date(2026, 7, 1): "July-2026", date(2026, 8, 1): "August-2026",
    date(2026, 9, 1): "September-2026",
}  # fmt: skip


def fetch_rebalanced_bikes(raw_dir: Path) -> pl.DataFrame:
    """Bikes Citi Bike reports it rebalanced each month, by truck, van, valet and Bike Angels.

    Downloads each monthly report once to `raw_dir/operating-reports/` and reads the sentence
    "Citi Bike staff rebalanced a total of N bicycles" with poppler's `pdftotext`.
    Columns: month, bikes_rebalanced.
    """
    folder = raw_dir / "operating-reports"
    folder.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, date | int]] = []
    for month, stem in OPERATING_REPORT_FILES.items():
        path = folder / f"{stem}.pdf"
        if not path.exists():
            response = requests.get(
                f"{OPERATING_REPORTS}/{stem}-Citi-Bike-Monthly-Report.pdf", timeout=60
            )
            response.raise_for_status()
            path.write_bytes(response.content)
        text = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        found = re.search(
            r"rebalanced a total of\s+([\d,]+)\s+bicycles", " ".join(text.split())
        )
        if found:
            rows.append(
                {"month": month, "bikes_rebalanced": int(found[1].replace(",", ""))}
            )
    return pl.DataFrame(rows)
