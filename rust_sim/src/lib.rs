//! The network simulation from `lib/rebalancing.py` (`simulate_network_slots`), in Rust.
//!
//! Python still loads the trips and decides every move; this replays one stretch of the day
//! slot by slot through every station, once per schedule, with the schedules on separate cores.
//! Same rules as the Python version: in each slot riders leave first, a rider who finds the
//! station empty is turned away and their trip is struck from the destination's arrivals, then
//! the slot's arrivals come in and anything above the docks is counted as full.

use numpy::ndarray::{Array2, Array3};
use numpy::{
    IntoPyArray, PyArray2, PyArray3, PyReadonlyArray1, PyReadonlyArray2, PyReadwriteArray3,
    PyUntypedArrayMethods,
};
use pyo3::prelude::*;
use rayon::prelude::*;

const SLOTS_PER_DAY: usize = 288;

/// The trips of one block of days, as `TripSlots` in Python holds them.
struct Trips<'a> {
    origin: &'a [i32],
    destination: &'a [i32],
    end_slot: &'a [i64],
    rank: &'a [i64],
    arrives: &'a [bool],
    bounds: &'a [i64],
    first_slot: i64,
}

/// One schedule's stock through `slots` slots. `stock` is [station], `cancelled` is
/// [station, slot of the day], `empty` and `full` are [station, slot]; all for this schedule only.
#[allow(clippy::too_many_arguments)]
fn run_schedule(
    stock: &mut [i32],
    cancelled: &mut [i32],
    empty: &mut [i16],
    full: &mut [i16],
    capacity: &[i32],
    starts: &[i16],
    ends: &[i16],
    slots: usize,
    trips: &Trips,
    first_slot: i64,
) {
    let stations = stock.len();
    let mut lost = vec![0i32; stations];
    for k in 0..slots {
        let slot = first_slot + k as i64;

        // riders leave; those the station cannot serve are turned away
        let mut any_lost = false;
        for s in 0..stations {
            let leaving = starts[s * slots + k] as i32;
            let short = (leaving - stock[s]).max(0);
            stock[s] -= leaving - short;
            lost[s] = short;
            empty[s * slots + k] = short as i16;
            any_lost |= short > 0;
        }

        // the first `lost` riders in each station's queue never ride, so their arrivals are struck
        let low = trips.bounds[(slot - trips.first_slot) as usize] as usize;
        let high = trips.bounds[(slot - trips.first_slot + 1) as usize] as usize;
        if any_lost {
            for t in low..high {
                if trips.arrives[t] && trips.rank[t] < lost[trips.origin[t] as usize] as i64 {
                    let column = trips.end_slot[t] as usize % SLOTS_PER_DAY;
                    cancelled[trips.destination[t] as usize * SLOTS_PER_DAY + column] += 1;
                }
            }
        }

        // arrivals come in, minus the struck ones; above the docks is full
        let column = slot as usize % SLOTS_PER_DAY;
        for s in 0..stations {
            let cell = &mut cancelled[s * SLOTS_PER_DAY + column];
            stock[s] += (ends[s * slots + k] as i32 - *cell).max(0);
            *cell = 0;
            full[s * slots + k] = (stock[s] - capacity[s]).max(0) as i16;
            stock[s] = stock[s].min(capacity[s]);
        }
    }
}

/// `simulate_network_slots` with the trips passed as plain arrays. `stock` is [policy, station],
/// `starts` and `ends` [station, slot] and contiguous, `cancelled_arrivals` [policy, station,
/// slot of the day], updated in place. Returns the stock after the last slot, and the empty and
/// full shortages as [policy, station, slot].
#[pyfunction]
#[allow(clippy::too_many_arguments, clippy::type_complexity)]
fn simulate_network_slots<'py>(
    py: Python<'py>,
    stock: PyReadonlyArray2<'py, i32>,
    capacity: PyReadonlyArray1<'py, i32>,
    starts: PyReadonlyArray2<'py, i16>,
    ends: PyReadonlyArray2<'py, i16>,
    origin: PyReadonlyArray1<'py, i32>,
    destination: PyReadonlyArray1<'py, i32>,
    end_slot: PyReadonlyArray1<'py, i64>,
    rank: PyReadonlyArray1<'py, i64>,
    arrives: PyReadonlyArray1<'py, bool>,
    bounds: PyReadonlyArray1<'py, i64>,
    trips_first_slot: i64,
    mut cancelled_arrivals: PyReadwriteArray3<'py, i32>,
    first_slot: i64,
) -> PyResult<(
    Bound<'py, PyArray2<i32>>,
    Bound<'py, PyArray3<i16>>,
    Bound<'py, PyArray3<i16>>,
)> {
    let (policies, stations) = (stock.shape()[0], stock.shape()[1]);
    let slots = starts.shape()[1];
    let mut new_stock = stock.as_slice()?.to_vec();
    let mut empty = vec![0i16; policies * stations * slots];
    let mut full = vec![0i16; policies * stations * slots];
    let capacity = capacity.as_slice()?;
    let (starts, ends) = (starts.as_slice()?, ends.as_slice()?);
    let trips = Trips {
        origin: origin.as_slice()?,
        destination: destination.as_slice()?,
        end_slot: end_slot.as_slice()?,
        rank: rank.as_slice()?,
        arrives: arrives.as_slice()?,
        bounds: bounds.as_slice()?,
        first_slot: trips_first_slot,
    };
    let cancelled = cancelled_arrivals.as_slice_mut()?;

    // schedules never touch each other's stations, so each runs on its own core
    py.allow_threads(|| {
        new_stock
            .par_chunks_mut(stations)
            .zip(cancelled.par_chunks_mut(stations * SLOTS_PER_DAY))
            .zip(empty.par_chunks_mut(stations * slots))
            .zip(full.par_chunks_mut(stations * slots))
            .for_each(|(((stock, cancelled), empty), full)| {
                run_schedule(
                    stock, cancelled, empty, full, capacity, starts, ends, slots, &trips,
                    first_slot,
                )
            });
    });

    let shape = (policies, stations, slots);
    Ok((
        Array2::from_shape_vec((policies, stations), new_stock)
            .expect("shape matches")
            .into_pyarray(py),
        Array3::from_shape_vec(shape, empty)
            .expect("shape matches")
            .into_pyarray(py),
        Array3::from_shape_vec(shape, full)
            .expect("shape matches")
            .into_pyarray(py),
    ))
}

#[pymodule]
fn citibike_sim(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(simulate_network_slots, module)?)
}
