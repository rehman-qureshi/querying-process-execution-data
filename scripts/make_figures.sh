#!/usr/bin/env bash
# Rebuild the figures from the stored measurements (seconds, no event log needed).
set -e
cd "$(dirname "$0")/.."
python code/plot_paper_figures.py --e1 results/bpic19_e1.csv --e2 results/bpic19_e2.csv --out results/figures/bpic19
python code/plot_paper_figures.py --e1 results/bpic17_e1.csv --e2 results/bpic17_e2.csv --out results/figures/bpic17
