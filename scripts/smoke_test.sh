#!/usr/bin/env bash
# Quick check that the setup works (a few minutes). Needs data/event_log_BPIC17.csv.
set -e
cd "$(dirname "$0")/.."
mkdir -p smoke && cd smoke
python ../code/runner.py e1 --questions ../workloads/bpic17/questions_0796.json --csv ../data/event_log_BPIC17.csv \
  --networth case:RequestedAmount --keep-col lifecycle:transition --keep-val complete \
  --reps 1 --mem-every 50 --sizes 2000 5000 --prefix smoke --cache smoke_cache.npz
echo "smoke test OK: see smoke/smoke_e1.csv"
