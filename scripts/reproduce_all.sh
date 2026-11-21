#!/usr/bin/env bash
# Full reproduction of all measurements and figures. Run the experiments one after another (not in parallel),
# otherwise the timings are disturbed. Expect several hours in total on a laptop (see README).
set -e
cd "$(dirname "$0")/.."
mkdir -p out && cd out
# ---- BPIC19 ----
python ../code/runner.py e1 --questions ../workloads/bpic19/questions_1104.json --csv ../data/process_execution_data.csv \
  --reps 3 --prefix bpic19
python ../code/runner.py e2 --workload ../workloads/bpic19 --csv ../data/process_execution_data.csv --reps 3 --prefix bpic19
# ---- BPIC17 ----
python ../code/runner.py e1 --questions ../workloads/bpic17/questions_0796.json --csv ../data/event_log_BPIC17.csv \
  --networth case:RequestedAmount --keep-col lifecycle:transition --keep-val complete \
  --reps 3 --sizes 2000 5000 10000 20000 31509 --prefix bpic17
python ../code/runner.py e2 --workload ../workloads/bpic17 --csv ../data/event_log_BPIC17.csv \
  --networth case:RequestedAmount --keep-col lifecycle:transition --keep-val complete --reps 3 --prefix bpic17
# ---- figures ----
python ../code/plot_paper_figures.py --e1 bpic19_e1.csv --e2 bpic19_e2.csv --out figures_bpic19
python ../code/plot_paper_figures.py --e1 bpic17_e1.csv --e2 bpic17_e2.csv --out figures_bpic17
