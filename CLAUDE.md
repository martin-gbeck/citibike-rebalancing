# citibike-rebalancing

- Running things (Martin's rule, 2026-10-23): run small scripts yourself. Anything that takes several GB or more than a few minutes, he runs himself so he can stop it: give him the command. The old notebook `citibike_rebalancing` (phase 1, superseded by the walkthrough notebook) is the 15-20 GB one; always ask before running it.
- Run order, all from this folder with `.venv/bin/python`. Each script reads what the one before wrote to `data/processed/` (about 300 MB, not in git, rebuilt by these scripts):
  1. `prepare_data.py`: raw trips to 5-minute station counts, the trip table, stations, dev-year routes. About 4 min, 2.8 GB peak, run at `nice`
  2. `station_days.py`: each station's daily stock swing. 6 s
  3. `demand_model.py`: fits the daily demand regression (`lib/demand.py`) and saves each day's forecast, which `rebalance.py` reads
  4. `rebalance.py dev`, then `rebalance.py test`: the schedule simulation, in which a rider turned away at an empty station never arrives. Dev about 3 min, test about 2 min, 1.6 GB. Every setting is chosen on dev; the test run only scores. `--independent` runs the simpler model (stations on their own) for the comparison in the report, about 30 s
     `--rust` runs the network replay in the Rust extension in `rust_sim/` (build once: `uvx maturin develop --release --uv` there, with `VIRTUAL_ENV` set to `.venv.nosync`; a plain `uv sync` removes it again, so rebuild after one). Same results to the last number; the test year takes 52 s instead of 96, the replay itself 6 s instead of 48. Not part of the hand-in.
  5. `walkthrough.py` / `.ipynb`: the report as code. Follows the report section by section, runs the analysis behind every number and draws all 13 figures by calling `lib/figures.py`, saving them to `figures/`. Under a minute. It is the main notebook in the submission
  6. `export_source.sh`: the source code as HTML for the submission zip, into `submission/source/`
- Figures land in `figures/`. The report is the Word file `report/final/citibike-report-editable.docx` (the group edits it; no Markdown or PDF copy is kept). To put redrawn figures in without touching its text: close it in Word, then `.venv/bin/python report/swap_figures.py report/final/citibike-report-editable.docx figures`.
- Memory: anything grouped by station and time runs one month at a time; a single pass over both years took 15 to 20 GB. Polars is capped at 6 threads.
- The trip Parquet files sit in `data/raw/tripdata.nosync/` and the venv in `.venv.nosync`, both out of iCloud sync on purpose; `.venv` is a link to it. Set it up with `ln -sfn .venv.nosync .venv && UV_PROJECT_ENVIRONMENT=.venv.nosync uv sync`. Library versions are pinned in `pyproject.toml` to the ones the report numbers came from.
- `examples/rank_over.py` and `examples/rank_diff.py` are not part of the pipeline: they show the old and new way `load_trip_slots` ranks riders within a slot, on a toy day and one real month.
- `walkthrough.ipynb` (paired with `walkthrough.py`) is also the readable tour for Martin and the group. Figure look lives in `lib/figures.py` and `lib/chart_style.py`; the analysis that feeds each figure stays in the notebook.
