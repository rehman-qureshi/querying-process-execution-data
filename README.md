# Executing process data queries from natural-language rule retrieval: benchmark and results

Code, workloads and measurements for the experimental study (Section 5 of the paper *An Experimental Study of Executing
Process Data Queries from Natural-Language Rule Retrieval*). The study measures the execution step of the querying
workflow (activate, filter, measure) over two event logs, BPIC19 (procurement) and BPIC17 (finance), for
(E1) growing logs with a fixed repository and (E2) growing repository subsets with a fixed log.

**Scope.** Natural-language identification of constraints is not part of this repository and is not timed. The runtime
experiments execute the *gold constraints* matched to each question (see `docs/workload_semantics.md`).

## Contents

| Folder | Content |
|---|---|
| `code/runner.py` | Stand-alone benchmark runner: loads the log, executes the questions, measures time and memory (E1, E2). |
| `code/plot_paper_figures.py` | Figures for the paper from the result CSVs (single-panel PDFs and the three-panel figure). |
| `code/make_workload.py`, `code/declare_workload.py`, `code/workload_v3.py` | Generation of the rule repository subsets and the 100 questions per log, and the reference executor that computes the reference answers. |
| `workloads/bpic19/`, `workloads/bpic17/` | Repository subsets (`repo_<k>.json/.csv/.decl`), the 100 questions with their matched constraint sets (`questions_<k>.json/.csv`, field `gold`), reference answers (`answers_<k>.csv`), `manifest.csv`, `workload_report.md`. |
| `results/` | Raw measurements (`bpic19_e1.csv`, `bpic19_e2.csv`, `bpic17_e1.csv`, `bpic17_e2.csv`) and the figures built from them. |
| `data/` | Where to place the event logs (download instructions in `data/README.md`). |
| `scripts/` | `smoke_test.sh`, `make_figures.sh`, `check_results.py`, `reproduce_all.sh`. |

## Setup

    pip install -r requirements.txt          # numpy, pandas, matplotlib; tested with Python 3.12 and 3.13

## What can be checked at which cost

1. **Figures from stored measurements (seconds, no event log).**

       bash scripts/make_figures.sh

2. **Consistency of stored measurements (seconds, no event log).** For all 100 questions per log, the satisfied-case
   counts measured by the runner on the full log equal the reference answers of the workload.

       python scripts/check_results.py

3. **Smoke test (about a minute, needs the BPIC17 CSV in `data/`).** Runs E1 on 2,000 and 5,000 traces.

       bash scripts/smoke_test.sh

4. **Full reproduction (hours, needs both CSV files).** Runs E1 and E2 for both logs, one after another.

       bash scripts/reproduce_all.sh

   Do not run experiments in parallel; timings would be disturbed. Absolute times depend on the machine; the stored
   results come from a 13th Gen Intel Core at 1.60 GHz, 16 GB RAM, Python 3.12, Windows 10. On other hardware expect
   different absolute times but the same linear trends.

## Experimental design

* **Workload.** 100 questions per log, generated from the repository. Each has a primary constraint (distinct per
  question), optional data conditions (amount threshold, resource, time window), a measure (case count, average waiting
  time, average time to activation, top-5 resources, distinct resources) and an activity set of 2 to 6 activities.
  The generator keeps at least 50 satisfied cases per question on the full repository.
* **Repository.** Rules of nine Declare templates (response, alternate response, chain response, precedence, alternate
  precedence, chain precedence, responded existence, not co-existence, not succession) with support >= 0.95 and
  >= 50 activated cases: 1,104 rules for BPIC19 and 796 rules for BPIC17.
* **Interpretation policy.** For each question the *matched set* (the primary constraint plus every rule of the subset
  whose two activities both occur in the question) is executed as **one conjunction**, i.e. one interpretation per
  question (conjunctive reading). Subsets are nested and always contain the primary rule of every question.
* **E1 (log size).** Full repository; random nested samples of traces (seed 1) up to the full log
  (BPIC19: 5,000 to 217,406 traces; BPIC17: 2,000 to 31,509 traces).
* **E2 (repository size).** Full log; question files of the subsets (BPIC19: 100, 250, 500, 750, 1,000, 1,104 rules;
  BPIC17: 100, 200, 400, 600, 796 rules). One random draw of the non-primary rules (fixed seed).
* **Measurement.** Time per question covers activation, filtering of satisfied executions and the measure; every
  question is run 3 times, each measurement cell in a fresh process, and the median per question is used; figures show
  mean and median over the 100 questions. *Log memory* is the memory held by the engine for the loaded log; *working
  memory* is the peak memory of a question, measured on a separate run with `tracemalloc` for every 5th question
  (timing runs are without `tracemalloc`).
* **Engine.** A naive, single-threaded trace-by-trace reference implementation in Python, not an optimised system. The
  results show scaling behaviour, not best-case speed.
* **BPIC17.** Only events with `lifecycle:transition = complete` are used; the data condition is the requested loan amount
  (`case:RequestedAmount`).

## Result files

Columns of `results/*_e1.csv` and `*_e2.csv`: experiment, number of traces and events, repository size, draw, question id,
measure, number of constraints, satisfied cases, repetition, total time and times of the three stages (activate, filter,
measure) in seconds, peak working memory (MiB, only for some questions), log memory (MiB), load time.

## Limitations

One random draw of nested repository subsets; the workload is generated from the repository rather than collected from
process owners; gold constraints are executed (no identification output); BPIC17 is restricted to complete events.

## License and citation

