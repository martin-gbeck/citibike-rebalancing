#!/usr/bin/env bash
# The source code as HTML for the submission zip (Appendix C asks for it), one page per file in
# run order, into submission/source/. Scripts keep their markdown cells as formatted text.
set -euo pipefail
cd "$(dirname "$0")"
VENV=.venv/bin
OUT=submission/source
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"

files=(prepare_data.py station_days.py explore.py demand_model.py rebalance.py rebalance_figures.py
  lib/fetching.py lib/data_schemas.py lib/rebalancing.py lib/geography.py lib/chart_style.py)
i=1
for file in "${files[@]}"; do
  name=$(printf "%02d-%s" "$i" "$(echo "$file" | tr '/' '-' | sed 's/\.py$//')")
  "$VENV/jupytext" --quiet --from py:percent --to ipynb --output "$WORK/$name.ipynb" "$file"
  "$VENV/jupyter-nbconvert" --log-level=ERROR --to html --output-dir "$OUT" "$WORK/$name.ipynb"
  i=$((i + 1))
done
ls "$OUT"
