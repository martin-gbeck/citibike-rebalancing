"""Station stock rebuilt from 5-minute trip counts, and the rules that decide how many bikes to move.

A service day runs from 04:00, the quietest hour, to 04:00 the next morning, in 288 slots of five
minutes. Arrays are indexed [station, day, slot], or [policy, station] for the stock under several
rebalancing policies simulated side by side.
"""

from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import polars as pl

SLOTS_PER_DAY = 288
DAY_START_HOUR = 4

# US federal holidays in the two years, plus the Friday after Thanksgiving; offices close, so these
# days ride like weekends
HOLIDAYS = [
    date(2024, 10, 14), date(2024, 11, 11), date(2024, 11, 28), date(2024, 11, 29),
    date(2024, 12, 25), date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17),
    date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1),
    date(2025, 10, 13), date(2025, 11, 11), date(2025, 11, 27), date(2025, 11, 28),
    date(2025, 12, 25), date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
]  # fmt: skip


def slot_of_hour(hour: int) -> int:
    """The slot of the service day that starts at `hour` o'clock (4 is slot 0, 3 the next night is 276)."""
    return (hour - DAY_START_HOUR) % 24 * 12


def load_day_slots(
    bins_dir: Path, station_ids: list[str], first_day: date, days: int
) -> tuple[np.ndarray, np.ndarray]:
    """Starts and ends as int16 arrays [station, day, slot] for `days` service days from `first_day`.

    Stations follow the order of `station_ids`; trips at stations not in the list are left out.
    """
    window_start = datetime.combine(first_day, time(DAY_START_HOUR))
    window_end = window_start + timedelta(days=days)
    rows = pl.DataFrame(
        {"station_id": station_ids, "row": np.arange(len(station_ids), dtype=np.int32)}
    )
    counts = (
        pl.scan_parquet(bins_dir / "*.parquet")
        .filter(pl.col("slot").is_between(window_start, window_end, closed="left"))
        .join(rows.lazy(), on="station_id")
        .select(
            "row",
            "starts",
            "ends",
            offset=((pl.col("slot") - window_start).dt.total_minutes() // 5).cast(
                pl.Int32
            ),
        )
        .collect()
    )
    shape = (len(station_ids), days, SLOTS_PER_DAY)
    starts = np.zeros(shape, dtype=np.int16)
    ends = np.zeros(shape, dtype=np.int16)
    row = counts["row"].to_numpy()
    offset = counts["offset"].to_numpy()
    day, slot = offset // SLOTS_PER_DAY, offset % SLOTS_PER_DAY
    starts[row, day, slot] = counts["starts"].to_numpy()
    ends[row, day, slot] = counts["ends"].to_numpy()
    return starts, ends


def simulate_slots(
    stock: np.ndarray, capacity: np.ndarray, starts: np.ndarray, ends: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Replay trips through stations slot by slot, from `stock` [policy, station].

    `starts` and `ends` are [station, slot]. In each slot the station gains its ends and loses its
    starts; a rider who would take it below 0 finds it empty and a rider who would take it above
    `capacity` finds it full, and both are counted as shortages and dropped. Returns the stock
    after the last slot, and the empty and full shortages as [policy, station, slot].
    """
    stock = stock.astype(np.int32)
    net = (ends.astype(np.int32) - starts).T
    empty = np.zeros((*stock.shape, net.shape[0]), dtype=np.int16)
    full = np.zeros_like(empty)
    for slot, slot_net in enumerate(net):
        stock = stock + slot_net
        empty[:, :, slot] = np.maximum(-stock, 0)
        full[:, :, slot] = np.maximum(stock - capacity, 0)
        stock = np.clip(stock, 0, capacity)
    return stock, empty, full


def target_band(need: np.ndarray, room: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The range of starting stock that would have left the fewest shortages over past days.

    `need` [station, day] is the bikes a station needed at the start of each past day never to run
    empty, `room` the most it could hold never to fill; nan where the station has no history that
    day. On a past day, starting at x leaves max(0, need - x) + max(0, x - room) shortages, so the
    total over n days is lowest between the n-th and (n+1)-th smallest of the 2n values. Returns
    that range, rounded inward to whole bikes and nan where a station has no history.
    """
    values = np.sort(np.concatenate([need, room], axis=1), axis=1)  # nan sorts last
    days_seen = np.sum(~np.isnan(need), axis=1)
    middle = np.clip(days_seen - 1, 0, None)[:, None]
    low = np.take_along_axis(values, middle, axis=1)[:, 0]
    high = np.take_along_axis(values, middle + 1, axis=1)[:, 0]
    low, high = np.ceil(low), np.floor(high)
    # with fractional values the two can cross; the minimum then sits at one whole bike
    high = np.maximum(high, low)
    no_history = days_seen == 0
    low[no_history] = np.nan
    high[no_history] = np.nan
    return low, high


def expected_shortages(
    need: np.ndarray, room: np.ndarray, levels: np.ndarray
) -> np.ndarray:
    """Average shortages over the past days if each station started at each of `levels`.

    `need` and `room` are [station, day] as in `target_band`; `levels` is [station, level] or
    [station]. Returns one value per entry of `levels`.
    """
    levels_3d = levels[..., None] if levels.ndim == 2 else levels[:, None, None]
    shortfall = np.maximum(need[:, None, :] - levels_3d, 0) + np.maximum(
        levels_3d - room[:, None, :], 0
    )
    result = np.nanmean(shortfall, axis=2)
    return result if levels.ndim == 2 else result[:, 0]


def shortage_table(need: np.ndarray, room: np.ndarray, max_level: int) -> np.ndarray:
    """`expected_shortages` for every whole stock level from 0 to `max_level`, as [station, level]."""
    levels = np.arange(max_level + 1, dtype=np.float32)[None, :].repeat(len(need), 0)
    return expected_shortages(need, room, levels)


def spend_budget(
    stock: np.ndarray,
    low: np.ndarray,
    high: np.ndarray,
    table: np.ndarray,
    budget: int,
) -> np.ndarray:
    """New stock per station after moving at most `budget` bikes where each prevents the most.

    `table` is `shortage_table` for these stations. Each bike moved one step toward a station's
    band prevents some expected shortages, and the saving shrinks as the station nears its band,
    so taking the `budget` largest single-bike savings across all stations is the best use of
    the budget. Stations without history (nan band) stay put.
    """
    up_saving = table[:, :-1] - table[:, 1:]  # from level x to x + 1
    down_saving = up_saving  # the same pair of levels, walked from x + 1 down to x
    position = np.arange(table.shape[1] - 1)[None, :]
    up_step = (position >= stock[:, None]) & (position < low[:, None])
    down_step = (position + 1 <= stock[:, None]) & (position + 1 > high[:, None])
    savings = np.concatenate(
        [np.where(up_step, up_saving, 0), np.where(down_step, -down_saving, 0)], axis=1
    )
    flat = np.nan_to_num(savings).ravel()
    chosen = min(budget, int(np.sum(flat > 0)))
    if chosen == 0:
        return stock.copy()
    picks = np.argpartition(-flat, chosen - 1)[:chosen]
    station, column = np.divmod(picks, savings.shape[1])
    is_up = column < position.shape[1]
    ups = np.bincount(station[is_up], minlength=len(stock))
    downs = np.bincount(station[~is_up], minlength=len(stock))
    return stock + ups - downs
