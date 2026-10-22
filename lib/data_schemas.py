"""The data model: one table of stations and one of station-hours, New York local time throughout.

Station-hours run to about 40 million rows, so counts are 32-bit integers and weather 32-bit floats.
"""

import pandera.polars as pa
import polars as pl
from pandera.api.polars.model_config import BaseConfig

# a box around New York City and Jersey City; a station outside it has broken coordinates
LAT_MIN, LAT_MAX = 40.45, 40.95
LNG_MIN, LNG_MAX = -74.30, -73.65


class Station(pa.DataFrameModel):
    # fmt: off
    station_id: pl.Categorical = pa.Field(unique=True)              # Citi Bike's station id as the trip files write it, e.g. 7293.10
    name: str                                                       # the name most trips used for it
    lat: float = pa.Field(ge=LAT_MIN, le=LAT_MAX)                   # latitude, median over its trips
    lng: float = pa.Field(ge=LNG_MIN, le=LNG_MAX)                   # longitude, median over its trips
    capacity: int = pa.Field(gt=0, nullable=True)                   # docks in the live feed of 2026-10-22, matched by id or else by name; null if not in the feed
    # fmt: on

    class Config(BaseConfig):  # ty: ignore[invalid-mutable-override]
        coerce = True
        strict = "filter"


class StationHour(pa.DataFrameModel):
    # fmt: off
    station_id: pl.Categorical                                      # station id, the key to Station
    hour: pl.Datetime = pa.Field()                                  # start of the hour, New York local time
    starts: pl.Int32 = pa.Field(ge=0)                               # bikes taken out: trips that started here in this hour
    ends: pl.Int32 = pa.Field(ge=0)                                 # bikes brought in: trips that ended here in this hour
    net_flow: pl.Int32                                              # ends - starts: bikes the station gained in the hour
    member_starts: pl.Int32 = pa.Field(ge=0)                        # starts by annual members, the commuters
    ebike_starts: pl.Int32 = pa.Field(ge=0)                         # starts on e-bikes
    temperature_c: pl.Float32 = pa.Field(nullable=True)             # Central Park air temperature, degrees C
    precipitation_mm: pl.Float32 = pa.Field(ge=0, nullable=True)    # Central Park rain and snow in the hour, mm of water
    # fmt: on

    class Config(BaseConfig):  # ty: ignore[invalid-mutable-override]
        coerce = True
        strict = "filter"
        unique = ["station_id", "hour"]  # noqa: RUF012

    @pa.dataframe_check
    def net_flow_is_ends_minus_starts(cls, data: pa.PolarsData) -> pl.LazyFrame:
        return data.lazyframe.select(
            pl.col("net_flow") == pl.col("ends") - pl.col("starts")
        )

    @pa.dataframe_check
    def subgroups_fit_inside_starts(cls, data: pa.PolarsData) -> pl.LazyFrame:
        return data.lazyframe.select(
            (pl.col("member_starts") <= pl.col("starts"))
            & (pl.col("ebike_starts") <= pl.col("starts"))
        )
