#!/usr/bin/env python3
"""
Stand-alone runtime evaluation (E1 log size, E2 repository size). Needs only this file, the workload folders
(questions_<k>.json carry the identified constraints in full) and process_execution_data.csv. Python 3 + numpy, pandas, matplotlib.

  python runner.py e2 --workload workload_draw1 workload_draw2 workload_draw3 --csv process_execution_data.csv   (E2 only, writes PDF)
  python runner.py e1 --questions workload_draw1/questions_1104.json --csv process_execution_data.csv   (E1 only, writes PDF)
  python runner_standalone.py run  --csv process_execution_data.csv --workload workload_draw1 workload_draw2 workload_draw3 --reps 3
  python runner_standalone.py plot --prefix runtime        -> runtime_figE1_logsize.pdf, runtime_figE2_repository.pdf (+ .png)

The first run converts the CSV once into log_cache.npz. Each measurement cell runs in a fresh process.
E1: question file of the full repository, log = random nested sample of N traces. E2: full log, question file of each repository subset.
"""
import argparse, csv, glob, json, os, platform, re, subprocess, sys, time
import numpy as np, tracemalloc

ACT_ARG = {"response": 0, "alt_response": 0, "chain_response": 0, "precedence": 1, "alt_precedence": 1, "chain_precedence": 1,
           "responded_existence": 0, "not_co_existence": 0, "not_succession": 0}   # activation argument: 0 = A, 1 = B

def fmt_dur(sec):
    sec = int(round(sec)); d, r = divmod(sec, 86400); h, r = divmod(r, 3600); m = r // 60
    return f"{d} days, {h} hours, {m} minutes"

# ---------------------------------------------------------------- log: CSV -> compact cache -> per-case tuples
def build_cache(csv_path, out, case="case:concept:name", activity="concept:name", timestamp="time:timestamp",
                resource="org:resource", networth="Cumulative net worth (EUR)", keep_col=None, keep_val=None):
    import pandas as pd
    cols = [case, activity, timestamp, resource, networth] + ([keep_col] if keep_col else [])
    df = pd.read_csv(csv_path, usecols=list(dict.fromkeys(cols)), low_memory=False)
    if keep_col:                                    # e.g. BPIC17: keep only lifecycle:transition == complete
        n0 = len(df); df = df[df[keep_col] == keep_val].reset_index(drop=True); print(f"kept {len(df)} of {n0} events with {keep_col} == {keep_val}")
    ts = (pd.to_datetime(df[timestamp], utc=True, format="ISO8601") - pd.Timestamp("1970-01-01", tz="UTC")) / pd.Timedelta(seconds=1)
    cc, _ = pd.factorize(df[case]); act, activities = pd.factorize(df[activity], sort=True)
    res, resources = pd.factorize(df[resource].fillna("unknown"), sort=True)
    order = np.lexsort((np.arange(len(df)), ts.to_numpy(), cc))
    cc, act, res = cc[order], act[order], res[order]; ts = ts.to_numpy()[order]; nw = df[networth].fillna(0).to_numpy()[order]
    offs = np.concatenate([[0], np.cumsum(np.bincount(cc, minlength=cc.max() + 1))])
    np.savez(out, act=act.astype(np.int16), ts=ts, res=res.astype(np.int32), nw=nw, offs=offs,
             activities=np.array(list(activities)), resources=np.array(list(resources)))
    print(f"{len(df)} events, {len(offs) - 1} cases, {len(activities)} activities -> {out}")


class Traces:
    """Event log as one tuple per case: (activity ids, timestamps, resource ids, net worth)."""
    def __init__(self, cache, tids=None):
        z = np.load(cache, allow_pickle=False); offs = z["offs"]; T = len(offs) - 1
        self.activities, self.resources = list(z["activities"]), list(z["resources"])
        self.aid = {a: i for i, a in enumerate(self.activities)}; self.rid = {r: i for i, r in enumerate(self.resources)}
        tids = np.arange(T) if tids is None else np.sort(tids)
        act, ts, res, nw = z["act"], z["ts"], z["res"], z["nw"]; self.cases = []
        for t in tids:
            s_, e_ = offs[t], offs[t + 1]
            self.cases.append((act[s_:e_].tolist(), ts[s_:e_].tolist(), res[s_:e_].tolist(), nw[s_:e_].tolist()))
        self.T = len(self.cases); self.N = sum(len(c[0]) for c in self.cases); self.total_T = T

# ---------------------------------------------------------------- engine: 1 activate, 2 filter, 3 measure
def check(tpl, a, b, seq, i):
    """Does the activation at position i satisfy the control flow?  returns (satisfied, partner position or -1)."""
    n = len(seq)
    if tpl in ("response", "alt_response"):
        j = next((k for k in range(i + 1, n) if seq[k] == b), -1)
        if j < 0: return False, -1
        if tpl == "alt_response" and any(seq[k] == a for k in range(i + 1, j)): return False, j
        return True, j
    if tpl == "chain_response":
        return (i + 1 < n and seq[i + 1] == b), i + 1
    if tpl in ("precedence", "alt_precedence"):
        p = next((k for k in range(i - 1, -1, -1) if seq[k] == a), -1)
        if p < 0: return False, -1
        if tpl == "alt_precedence" and any(seq[k] == b for k in range(p + 1, i)): return False, p
        return True, p
    if tpl == "chain_precedence":
        return (i > 0 and seq[i - 1] == a), i - 1
    if tpl == "responded_existence": return (b in seq), -1
    if tpl == "not_co_existence": return (b not in seq), -1
    if tpl == "not_succession": return (not any(seq[k] == b for k in range(i + 1, n))), -1
    raise ValueError(tpl)


def execute(L, constraints, conditions, measure):
    """constraints: [(template, activity_a, activity_b)] by NAME (first = primary). Returns dict like the reference."""
    t0 = time.perf_counter()
    cons = [(t, L.aid[a], L.aid[b]) for t, a, b in constraints]
    tpl, a, b = cons[0]; ax = a if ACT_ARG[tpl] == 0 else b
    nw_min = max((c["value"] for c in conditions if c["type"] == "net_worth_gt"), default=None)
    users = {L.rid[c["value"]] for c in conditions if c["type"] == "resource_eq"}
    window = min((c["value"] * 86400 for c in conditions if c["type"] == "within_days"), default=None)

    # ---- 1. ACTIVATE: per trace, the activation events of the primary constraint that pass the data conditions
    activated = []                                                # (trace, [(position, partner, satisfied)])
    for case in L.cases:
        seq, ts, res, nw = case
        acts = []
        for i, x in enumerate(seq):
            if x != ax: continue
            if nw_min is not None and not nw[i] > nw_min: continue
            if users and res[i] not in users: continue
            ok, p = check(tpl, a, b, seq, i)
            if window is not None: ok = ok and p >= 0 and abs(ts[p] - ts[i]) <= window
            acts.append((i, p, ok))
        if not acts: continue
        # composite questions: every further constraint must be activated in the same trace
        extra_ok, all_activated = True, True
        for t2, a2, b2 in cons[1:]:
            ax2 = a2 if ACT_ARG[t2] == 0 else b2
            pos = [i for i, x in enumerate(seq) if x == ax2]
            if not pos: all_activated = False; break
            if not all(check(t2, a2, b2, seq, i)[0] for i in pos): extra_ok = False
        if all_activated:
            activated.append((case, acts, extra_ok))
    t1 = time.perf_counter()

    # ---- 2. FILTER: satisfied traces
    conform = [(case, acts) for case, acts, extra_ok in activated if extra_ok and all(ok for _, _, ok in acts)]
    t2_ = time.perf_counter()

    # ---- 3. MEASURE
    res = {"activated": len(activated), "satisfied": len(conform)}
    res["coverage"] = res["activated"] / L.T
    res["support"] = res["satisfied"] / res["activated"] if res["activated"] else 0.0
    if measure == "count_cases":
        res["value"] = len(conform); res["answer"] = f"{len(conform)} cases"
    elif measure in ("avg_waiting_time", "avg_time_to_activation"):
        vals = []
        for (seq, ts, _, _), acts in conform:
            i, p, _ = acts[0]
            if measure == "avg_waiting_time":
                if p >= 0: vals.append(abs(ts[p] - ts[i]))
            else:
                vals.append(ts[i] - ts[0])
        v = float(np.mean(vals)) if vals else float("nan")
        res["value"] = v; res["answer"] = fmt_dur(v) if vals else "n/a"
    else:
        cnt = {}
        for (_, _, rs, _), acts in conform:
            for r in {rs[i] for i, _, _ in acts}: cnt[r] = cnt.get(r, 0) + 1
        if measure == "distinct_resources":
            res["value"] = len(cnt); res["answer"] = f"{len(cnt)} resources"
        else:
            top = sorted(cnt.items(), key=lambda kv: (-kv[1], L.resources[kv[0]]))[:5]
            res["value"] = [(L.resources[r], c) for r, c in top]
            res["answer"] = "; ".join(f"{n} ({c} cases)" for n, c in res["value"])
    t3 = time.perf_counter()
    res["stages"] = {"tables": t1 - t0, "filter": t2_ - t1, "measure": t3 - t2_}
    return res


def execute_question(L, q):
    """Entry point used by the benchmark: q is one entry of questions_v2.json (gold = identified constraints)."""
    g = q["gold"]
    cons = [(c["template"], c["activities"][0], c["activities"][1]) for c in g["constraints"]]
    return execute(L, cons, g["conditions"], g["measure"])



# ---------------------------------------------------------------- measurement cell (one fresh process)
def cell(a):
    t0 = time.perf_counter(); z = np.load(a.cache); T = len(z["offs"]) - 1; t_load = time.perf_counter() - t0
    qs = json.load(open(a.questions))
    tids = None if a.size >= T else np.random.RandomState(a.seed).permutation(T)[:a.size]
    tracemalloc.start(); S = Traces(a.cache, tids)
    data_mib = tracemalloc.get_traced_memory()[0] / 2**20; tracemalloc.stop()
    out = []
    for q in qs:
        reps = []
        for _ in range(a.reps):
            t0 = time.perf_counter(); r = execute_question(S, q); reps.append((time.perf_counter() - t0, r["stages"]))
        peak = float("nan")
        if q["qid"] % a.mem_every == 0:
            tracemalloc.start(); tracemalloc.reset_peak(); b = tracemalloc.get_traced_memory()[0]
            execute_question(S, q); peak = (tracemalloc.get_traced_memory()[1] - b) / 2**20; tracemalloc.stop()
        out.append(dict(qid=q["qid"], n_constraints=q["n_constraints"], measure=q["measure"], satisfied=r["satisfied"],
                        times=[x[0] for x in reps], stages=reps[len(reps) // 2][1], q_peak_mib=peak))
    print(json.dumps(dict(n_traces=S.T, n_events=S.N, t_load=t_load, data_mib=data_mib, results=out)))

def spawn(a, qfile, size):
    cmd = [sys.executable, os.path.abspath(__file__), "cell", "--cache", a.cache, "--questions", qfile, "--size", str(size),
           "--reps", str(a.reps), "--mem-every", str(a.mem_every), "--seed", str(a.seed)]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])


def rows_of(exp, w, n_rules, draw):
    rows = []
    for r in w["results"]:
        for rep, t in enumerate(r["times"]):
            rows.append(dict(exp=exp, n_traces=w["n_traces"], n_events=w["n_events"], repo_rules=n_rules, draw=draw, qid=r["qid"], measure=r["measure"],
                             n_constraints=r["n_constraints"], satisfied=r["satisfied"], rep=rep, time_s=t, t_activate=r["stages"]["tables"],
                             t_filter=r["stages"]["filter"], t_measure=r["stages"]["measure"], q_peak_mib=r["q_peak_mib"], data_mib=w["data_mib"], t_load_s=w["t_load"]))
    return rows


def say(w, n_rules):
    ts = [np.median(r["times"]) for r in w["results"]]; cs = [r["n_constraints"] for r in w["results"]]
    return (f"{w['n_traces']:7d} traces, |DR|={n_rules:5d}: mean |C| {np.mean(cs):5.1f}  time/question {np.mean(ts):.3f}s  "
            f"log in memory {w['data_mib']:.1f} MiB  working mem median {np.nanmedian([r['q_peak_mib'] for r in w['results']]):.2f} MiB")


def levels_of(d):
    return sorted((int(re.search(r"questions_(\d+)\.json", f).group(1)), f) for f in glob.glob(os.path.join(d, "questions_*.json")))


def linfit(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float); b, a0 = np.polyfit(x, y, 1)
    return a0, b, 1 - ((y - (a0 + b * x)) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-30)


def plot(a):
    if getattr(a, "merge", None):                                  # combine E2 results of separate single-workload runs
        import pandas as pd
        parts = []
        for k, fn in enumerate(a.merge):
            d = pd.read_csv(fn); d["draw"] = k; parts.append(d)
        pd.concat(parts).to_csv(f"{a.prefix}_e2.csv", index=False); print(f"merged {len(parts)} files -> {a.prefix}_e2.csv")
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt, pandas as pd
    plt.rcParams.update({"font.size": 8, "font.family": "serif", "axes.spines.top": False, "axes.spines.right": False})
    def sty(ax, t): ax.grid(alpha=.25, lw=.5); ax.set_title(t, loc="left"); ax.set_ylim(bottom=0)
    def panel(ax, x, g, ylab, xlab, loc="upper left"):
        med = g.median().reindex(x).values
        ax.fill_between(x, g.quantile(.25).reindex(x).values, g.quantile(.75).reindex(x).values, color="k", alpha=.12, lw=0)
        ax.plot(x, med, "ko-", ms=3, lw=1, label="median, IQR"); a0, b, r2 = linfit(x, med)
        ax.plot(x, a0 + b * np.array(x), "--", color="0.5", lw=.8, label=f"linear fit, $R^2$={r2:.3f}")
        ax.set_xlabel(xlab); ax.set_ylabel(ylab); ax.legend(frameon=False, fontsize=6, loc=loc); return b, r2
    if os.path.exists(f"{a.prefix}_e1.csv"):
        e1 = pd.read_csv(f"{a.prefix}_e1.csv")
        q = e1.groupby(["qid", "n_traces"]).agg(t=("time_s", "median"), m=("q_peak_mib", "median")).reset_index()
        xs = sorted(q.n_traces.unique()); fig, ax = plt.subplots(1, 3, figsize=(7.6, 2.5))
        b, r2 = panel(ax[0], xs, q.groupby("n_traces")["t"], "Time per question [s]", "Log size [traces]")
        d = e1.groupby("n_traces")["data_mib"].first().reindex(xs).values; a0, bb, r = linfit(xs, d)
        ax[1].plot(xs, d, "ko-", ms=3, lw=1, label="log held in memory"); ax[1].plot(xs, a0 + bb * np.array(xs), "--", color="0.5", lw=.8, label=f"linear fit, $R^2$={r:.3f}")
        ax[1].set_xlabel("Log size [traces]"); ax[1].set_ylabel("Memory of the log [MiB]"); ax[1].legend(frameon=False, fontsize=6, loc="upper left")
        panel(ax[2], xs, q.groupby("n_traces")["m"], "Working memory per question [MiB]", "Log size [traces]")
        for i, t in enumerate("abc"): sty(ax[i], f"({t})"); ax[i].set_xticks(xs); ax[i].set_xticklabels([f"{round(v/1000):d}K" for v in xs], fontsize=6.5, rotation=45, ha="right")
        fig.tight_layout(); fig.savefig(f"{a.prefix}_figE1_logsize.pdf"); fig.savefig(f"{a.prefix}_figE1_logsize.png", dpi=300)
        print(f"E1: {b*1e6:.2f} us per trace and question (median), R2 {r2:.3f}")
    if os.path.exists(f"{a.prefix}_e2.csv"):
        e2 = pd.read_csv(f"{a.prefix}_e2.csv")
        cell_ = e2.groupby(["repo_rules", "draw", "qid"]).agg(t=("time_s", "median"), m=("q_peak_mib", "median"), c=("n_constraints", "first")).reset_index()
        per = cell_.groupby(["repo_rules", "draw"]).agg(t=("t", "mean"), m=("m", "median"), c=("c", "mean")).reset_index()
        xr = sorted(per.repo_rules.unique()); g = per.groupby("repo_rules"); fig, ax = plt.subplots(1, 3, figsize=(7.6, 2.5))
        for i, (col, lab) in enumerate([("t", "Mean time per question [s]"), ("m", "Working memory [MiB]")]):
            med = g[col].median().reindex(xr).values
            multi = per.draw.nunique() > 1
            if multi: ax[i].fill_between(xr, g[col].min().reindex(xr).values, g[col].max().reindex(xr).values, color="k", alpha=.12, lw=0)
            ax[i].plot(xr, med, "ko-", ms=3, lw=1, label=("median over draws, min-max" if multi else ("mean over 100 questions" if col == "t" else "median over sampled questions"))); a0, b, r2 = linfit(xr, med)
            ax[i].plot(xr, a0 + b * np.array(xr), "--", color="0.5", lw=.8, label=f"linear fit, $R^2$={r2:.3f}")
            ax[i].set_xlabel("Rules in repository"); ax[i].set_ylabel(lab); ax[i].legend(frameon=False, fontsize=6, loc="lower right" if i == 0 else "lower left"); sty(ax[i], f"({'ab'[i]})")
            if i == 0: print(f"E2: {b*1e3:.3f} ms per rule, R2 {r2:.3f}")
        c = cell_.copy(); bins = np.unique(np.quantile(c.c, np.linspace(0, 1, 9)).round()); c["bin"] = pd.cut(c.c, bins, include_lowest=True)
        bb = c.groupby("bin", observed=True).agg(c=("c", "mean"), t=("t", "median"), lo=("t", lambda s: s.quantile(.25)), hi=("t", lambda s: s.quantile(.75))).reset_index()
        ax[2].fill_between(bb.c, bb.lo, bb.hi, color="k", alpha=.12, lw=0); ax[2].plot(bb.c, bb.t, "ko-", ms=3, lw=1, label="median per |C| bin, IQR")
        a0, b, r2 = linfit(bb.c, bb.t); ax[2].plot(bb.c, a0 + b * bb.c, "--", color="0.5", lw=.8, label=f"{b*1e3:.0f} ms per constraint, $R^2$={r2:.3f}")
        ax[2].set_xlabel("Executed constraints $|C|$"); ax[2].set_ylabel("Time per question [s]"); ax[2].legend(frameon=False, fontsize=6, loc="upper left"); sty(ax[2], "(c)")
        fig.tight_layout(); fig.savefig(f"{a.prefix}_figE2_repository.pdf"); fig.savefig(f"{a.prefix}_figE2_repository.png", dpi=300)
        print("E2 mean |C| per level:", {int(k): round(v, 1) for k, v in g["c"].mean().items()})


def run(a):
    if not os.path.exists(a.cache): build_cache(a.csv, a.cache, **colargs(a))
    e1, e2 = [], []
    if a.exp in ("e1", "all"):
        n, f = levels_of(a.workload[0])[-1]
        for size in a.sizes:
            w = spawn(a, f, size); e1 += rows_of("E1", w, n, 0); print("E1", say(w, n), flush=True)
    if a.exp in ("e2", "all"):
        for draw, d in enumerate(a.workload, start=getattr(a, "draw_id", 0)):
            for n, f in levels_of(d):
                w = spawn(a, f, 10**9); e2 += rows_of("E2", w, n, draw); print(f"E2 draw {draw}", say(w, n), flush=True)
    for k, rows in (("e1", e1), ("e2", e2)):
        if rows:
            with open(f"{a.prefix}_{k}.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    json.dump(dict(platform=platform.platform(), processor=platform.processor(), python=sys.version.split()[0], numpy=np.__version__,
                   reps=a.reps, workloads=a.workload, sizes=a.sizes, seed=a.seed), open(f"{a.prefix}_env.json", "w"), indent=1)

def colargs(a):
    return dict(case=a.case, activity=a.activity, timestamp=a.timestamp, resource=a.resource, networth=a.networth, keep_col=a.keep_col, keep_val=a.keep_val)


def e1(a):
    """E1 only: one question file (full repository) + the CSV; log size varies; writes CSV and PDF/PNG figure."""
    if not os.path.exists(a.cache): build_cache(a.csv, a.cache, **colargs(a))
    rows = []; m = re.search(r"questions_(\d+)", os.path.basename(a.questions)); n = int(m.group(1)) if m else 0
    for size in a.sizes:
        w = spawn(a, a.questions, size); rows += rows_of("E1", w, n, 0); print("E1", say(w, n), flush=True)
    with open(f"{a.prefix}_e1.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    json.dump(dict(platform=platform.platform(), processor=platform.processor(), python=sys.version.split()[0], numpy=np.__version__,
                   reps=a.reps, questions=a.questions, sizes=a.sizes, seed=a.seed), open(f"{a.prefix}_env.json", "w"), indent=1)
    plot(a)

def e2(a):
    """E2 only: full log; one question file per repository subset (every questions_<k>.json in each workload folder; folder = draw)."""
    a.exp = "e2"; a.sizes = []; run(a); plot(a)

def csv_options(s):
    s.add_argument("--csv", default="process_execution_data.csv")
    s.add_argument("--case", default="case:concept:name"); s.add_argument("--activity", default="concept:name")
    s.add_argument("--timestamp", default="time:timestamp"); s.add_argument("--resource", default="org:resource")
    s.add_argument("--networth", default="Cumulative net worth (EUR)", help="numeric column used by the data condition (BPIC17: case:RequestedAmount)")
    s.add_argument("--keep-col", default=None); s.add_argument("--keep-val", default=None, help="keep only rows with this value (BPIC17: lifecycle:transition = complete)")


def main():
    p = argparse.ArgumentParser(); sp = p.add_subparsers(dest="cmd", required=True)
    def common(s):
        s.add_argument("--cache", default="log_cache.npz"); s.add_argument("--reps", type=int, default=3)
        s.add_argument("--mem-every", type=int, default=5); s.add_argument("--seed", type=int, default=1)
    s = sp.add_parser("run"); common(s); csv_options(s); s.add_argument("--workload", nargs="+", required=True)
    s.add_argument("--exp", choices=["e1", "e2", "all"], default="all"); s.add_argument("--sizes", type=int, nargs="+", default=[5000, 25000, 50000, 100000, 217406])
    s.add_argument("--prefix", default="runtime"); s.set_defaults(f=run)
    s = sp.add_parser("e1"); common(s); s.add_argument("--questions", required=True); csv_options(s)
    s.add_argument("--sizes", type=int, nargs="+", default=[5000, 25000, 50000, 100000, 217406]); s.add_argument("--prefix", default="runtime"); s.set_defaults(f=e1)
    s = sp.add_parser("e2"); common(s); s.add_argument("--workload", nargs="+", required=True); csv_options(s)
    s.add_argument("--draw-id", type=int, default=0, help="draw number of the first workload folder (for separate single-workload runs)")
    s.add_argument("--prefix", default="runtime"); s.set_defaults(f=e2)
    s = sp.add_parser("cell"); common(s); s.add_argument("--questions", required=True); s.add_argument("--size", type=int, default=10**9); s.set_defaults(f=cell)
    s = sp.add_parser("plot"); s.add_argument("--prefix", default="runtime"); s.add_argument("--merge", nargs="+", help="E2 csv files of separate runs (one per draw) to combine"); s.set_defaults(f=plot)
    a = p.parse_args(); a.f(a)

if __name__ == "__main__":
    main()
