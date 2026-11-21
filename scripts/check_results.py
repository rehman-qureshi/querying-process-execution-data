#!/usr/bin/env python3
"""Consistency check without the event log: for every question, the number of satisfied cases measured by the runner
on the full log (E1, largest size) must equal the reference answer stored in the workload (computed by a separate,
vectorised reference executor, code/declare_workload.py)."""
import os, sys
import pandas as pd
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ok = True
for name, ans, e1 in [("BPIC19", "workloads/bpic19/answers_1104.csv", "results/bpic19_e1.csv"),
                      ("BPIC17", "workloads/bpic17/answers_0796.csv", "results/bpic17_e1.csv")]:
    a = pd.read_csv(os.path.join(root, ans)).set_index("qid"); e = pd.read_csv(os.path.join(root, e1))
    f = e[(e.n_traces == e.n_traces.max()) & (e.rep == 0)].set_index("qid")
    same = (a.satisfied_cases == f.satisfied) & (a.n_constraints == f.n_constraints)
    print(f"{name}: {int(same.sum())}/{len(a)} questions agree (satisfied cases and number of constraints)")
    ok &= bool(same.all())
sys.exit(0 if ok else 1)
