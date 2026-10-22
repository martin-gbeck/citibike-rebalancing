# citibike-rebalancing

- Running things (Martin's rule, 2026-10-23): run small scripts yourself. Anything that takes several GB or more than a few minutes, he runs himself so he can stop it: give him the command. The old notebook `citibike_rebalancing` is the 15-20 GB one; always ask before running it.
- Run order, all from this folder with `../.venv/bin/python`. Each script reads what the one before wrote to `data/processed/` (about 300 MB, not in git, rebuilt by these scripts):
  1. `prepare_data.py`: raw trips to 5-minute station counts, stations, dev-year routes. 3.5 min, 2.8 GB peak, run at `nice`
  2. `station_days.py`: each station's daily stock swing. 6 s
  3. `explore.py`: figures 1 to 5 (dev year only)
  4. `demand_model.py`: daily demand regression, figures 6 and 7
  5. `rebalance.py dev`, then `rebalance.py test`: the schedule simulation, about 30 s each. Every setting is chosen on dev; the test run only scores
  6. `rebalance_figures.py`: figures 8 to 12 from the test run
- Figures land in `figures/` and are copied into the report at `SecondBrain/output/nus/dao2702/citibike-report-draft/`.
- Memory: anything grouped by station and time runs one month at a time; a single pass over both years took 15 to 20 GB. Polars is capped at 6 threads.
- The trip Parquet files sit in `data/raw/tripdata.nosync/` and the venv in `../.venv.nosync`, both out of iCloud sync on purpose; `../.venv` is a link to it.
