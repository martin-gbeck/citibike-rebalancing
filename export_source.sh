#!/usr/bin/env bash
# The source code as HTML for the submission zip (Appendix C asks for it), into submission/source/.
# First the walkthrough notebook, run so its numbers and figures show; then every script and module
# in run order, one page each, with their markdown cells as formatted text.
set -euo pipefail
cd "$(dirname "$0")"
VENV=.venv/bin
OUT=submission/source
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"

rm -f "$OUT"/*.html
# run where it lives, so it finds lib/ and data/
"$VENV/jupytext" --quiet --to ipynb walkthrough.py
"$VENV/jupyter-nbconvert" --log-level=ERROR --to html --execute --output 00-walkthrough --output-dir "$OUT" walkthrough.ipynb

files=(prepare_data.py station_days.py demand_model.py rebalance.py
  lib/fetching.py lib/data_schemas.py lib/rebalancing.py lib/demand.py lib/figures.py lib/geography.py
  lib/chart_style.py)
i=1
for file in "${files[@]}"; do
  name=$(printf "%02d-%s" "$i" "$(echo "$file" | tr '/' '-' | sed 's/\.py$//')")
  "$VENV/jupytext" --quiet --from py:percent --to ipynb --output "$WORK/$name.ipynb" "$file"
  "$VENV/jupyter-nbconvert" --log-level=ERROR --to html --output-dir "$OUT" "$WORK/$name.ipynb"
  i=$((i + 1))
done
ls "$OUT"
