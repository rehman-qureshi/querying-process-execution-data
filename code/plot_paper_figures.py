#!/usr/bin/env python3
"""
Paper figures from the runtime CSVs (no log, no questions needed). Python 3 with numpy, pandas, matplotlib.

  python plot_paper_figures.py --e1 runtime_e1.csv --e2 runtime_e2.csv [--e2 more_draws.csv ...] --out .

Writes three separate single-panel PDFs (and PNG previews):
  fig_E1a_time_vs_logsize.pdf      time per question vs log size (mean and median), linear fit
  fig_E1b_memory_vs_logsize.pdf    memory of the log vs log size, linear fit
  fig_E2_time_vs_repository.pdf    mean time per question vs repository size, linear fit
Several --e2 files are treated as several repository draws (the line is the mean over draws, the band is min-max).
"""
import argparse, os
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 8, "font.family": "serif", "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42, "axes.grid": True, "grid.alpha": .25, "grid.linewidth": .5})
INK, GREY = "#222222", "#8a8a8a"
STAGE = [("t_activate", "activation", "#4d4d4d"), ("t_filter", "filter", "#9a9a9a"), ("t_measure", "measure", "#d4d4d4")]


def linfit(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float); b, a = np.polyfit(x, y, 1)
    return a, b, 1 - ((y - (a + b * x)) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def per_question(df, keys):
    """median over repetitions for every (keys, question)"""
    return df.groupby(keys + ["qid"]).agg(t=("time_s", "median"), act=("t_activate", "median"), flt=("t_filter", "median"),
                                          mea=("t_measure", "median"), m=("data_mib", "first")).reset_index()


TICKS = "regular"          # "regular": evenly spaced tick labels (clearly linear axes); "measured": labels at the measured points


def set_ticks(ax, xs, kind):
    """kind: 'size' (traces, labels in K) or 'rules'. Markers always sit at the measured values."""
    if TICKS == "measured":
        ax.set_xticks(xs); lab = [f"{round(v / 1000):d}K" if kind == "size" else str(int(v)) for v in xs]
        ax.set_xticklabels(lab, rotation=45, ha="right", fontsize=7)
    else:                                           # evenly spaced "nice" ticks, chosen from the data range
        from matplotlib.ticker import MaxNLocator, FuncFormatter
        ax.xaxis.set_major_locator(MaxNLocator(nbins=3 if kind == "size" else 4, steps=[1, 2, 2.5, 5, 10], min_n_ticks=3))
        ax.xaxis.set_major_formatter(FuncFormatter((lambda v, _: "0" if v == 0 else (f"{v / 1000:g}K" if v >= 1000 else f"{v:g}")) if kind == "size" else (lambda v, _: f"{v:g}")))
        ax.set_xlim(-0.03 * max(xs), 1.04 * max(xs))


def save(fig, out, name):
    fig.tight_layout(); fig.savefig(os.path.join(out, name + ".pdf")); fig.savefig(os.path.join(out, name + ".png"), dpi=300); plt.close(fig)


def size_axis(ax, xs):
    ax.set_xlabel("Log size [traces]"); set_ticks(ax, xs, "size")
    ax.set_ylim(bottom=0); ax.legend(frameon=False, fontsize=6, loc="upper left")


def fig_e1(path, out):
    d = pd.read_csv(path); q = per_question(d, ["n_traces"]); xs = sorted(q.n_traces.unique())
    mean_t = q.groupby("n_traces").t.mean().reindex(xs).values; med_t = q.groupby("n_traces").t.median().reindex(xs).values
    mem = d.groupby("n_traces").data_mib.first().reindex(xs).values
    fig, ax = plt.subplots(figsize=(3.2, 2.5)); a, b, r2 = linfit(xs, mean_t)
    ax.plot(xs, a + b * np.array(xs), ":", color=GREY, lw=1, label=f"linear fit (mean), $R^2$={r2:.3f}")
    ax.plot(xs, mean_t, "o-", color=INK, ms=3.5, lw=1.1, label="mean over questions")
    ax.plot(xs, med_t, "s--", color=INK, mfc="white", ms=3.5, lw=.9, label="median over questions")
    ax.set_ylabel("Execution time per question [s]"); size_axis(ax, xs); save(fig, out, "fig_E1a_time_vs_logsize")
    fig, ax = plt.subplots(figsize=(3.2, 2.5)); a, b, r2 = linfit(xs, mem)
    ax.plot(xs, a + b * np.array(xs), ":", color=GREY, lw=1, label=f"linear fit, $R^2$={r2:.3f}")
    ax.plot(xs, mem, "o-", color=INK, ms=3.5, lw=1.1, label="log held in memory")
    ax.set_ylabel("Memory of the log [MiB]"); size_axis(ax, xs); save(fig, out, "fig_E1b_memory_vs_logsize")
    print(f"E1: {len(xs)} sizes; mean time {mean_t[0]:.3f} -> {mean_t[-1]:.3f} s; log memory {mem[0]:.1f} -> {mem[-1]:.1f} MiB")


def fig_e2(paths, out):
    parts = []
    for k, p in enumerate(paths):
        d = pd.read_csv(p); d["draw"] = k if len(paths) > 1 else d.get("draw", 0); parts.append(d)
    d = pd.concat(parts); q = per_question(d, ["repo_rules", "draw"])
    lv = q.groupby(["repo_rules", "draw"]).t.mean().reset_index(); xs = sorted(lv.repo_rules.unique()); g = lv.groupby("repo_rules").t
    tot = g.mean().reindex(xs).values; a, b, r2 = linfit(xs, tot)
    fig, ax = plt.subplots(figsize=(3.2, 2.5))
    if len(paths) > 1: ax.fill_between(xs, g.min().reindex(xs).values, g.max().reindex(xs).values, color=INK, alpha=.12, lw=0)
    ax.plot(xs, a + b * np.array(xs), ":", color=GREY, lw=1, label=f"linear fit, $R^2$={r2:.2f}")
    ax.plot(xs, tot, "o-", color=INK, ms=3.5, lw=1.1, label="mean over questions" + (" (draws: min-max)" if len(paths) > 1 else ""))
    ax.set_xlabel("Rules in repository $|DR|$"); ax.set_ylabel("Mean time per question [s]")
    set_ticks(ax, xs, "rules")
    ax.set_ylim(0, max(tot.max(), g.max().max()) * 1.15); ax.legend(frameon=False, fontsize=6, loc="lower right"); save(fig, out, "fig_E2_time_vs_repository")
    print(f"E2: mean time {tot[0]:.3f} -> {tot[-1]:.3f} s over {int(xs[0])} -> {int(xs[-1])} rules; fit {a:.3f} s + {b * 1e3:.3f} ms per rule, R2 {r2:.3f}")


def fig_lncs(e1_path, e2_paths, out, width=4.8, height=1.9):
    """One three-panel figure at LNCS text width (4.8 in): (a) time vs log size, (b) log memory vs log size, (c) time vs repository size."""
    plt.rcParams.update({"font.size": 6.5, "axes.labelsize": 6.5, "xtick.labelsize": 6, "ytick.labelsize": 6, "legend.fontsize": 5.5})
    d = pd.read_csv(e1_path); q = per_question(d, ["n_traces"]); xs = sorted(q.n_traces.unique())
    mean_t = q.groupby("n_traces").t.mean().reindex(xs).values; med_t = q.groupby("n_traces").t.median().reindex(xs).values
    mem = d.groupby("n_traces").data_mib.first().reindex(xs).values
    parts = []
    for k, p in enumerate(e2_paths):
        e = pd.read_csv(p); e["draw"] = k if len(e2_paths) > 1 else e.get("draw", 0); parts.append(e)
    e = pd.concat(parts); lv = per_question(e, ["repo_rules", "draw"]).groupby(["repo_rules", "draw"]).t.mean().reset_index()
    xr = sorted(lv.repo_rules.unique()); g = lv.groupby("repo_rules").t; tot = g.mean().reindex(xr).values
    fig, ax = plt.subplots(1, 3, figsize=(width, height))
    a, b, r2 = linfit(xs, mean_t)
    ax[0].plot(xs, a + b * np.array(xs), ":", color=GREY, lw=.9, label="fit, $R^2$>0.999" if r2 > .999 else f"fit, $R^2$={r2:.3f}")
    ax[0].plot(xs, mean_t, "o-", color=INK, ms=2.6, lw=.9, label="mean"); ax[0].plot(xs, med_t, "s--", color=INK, mfc="white", ms=2.6, lw=.8, label="median")
    ax[0].set_ylabel("Time per question [s]")
    a, b, r2 = linfit(xs, mem)
    ax[1].plot(xs, a + b * np.array(xs), ":", color=GREY, lw=.9, label="fit, $R^2$>0.999" if r2 > .999 else f"fit, $R^2$={r2:.3f}")
    ax[1].plot(xs, mem, "o-", color=INK, ms=2.6, lw=.9, label="measured"); ax[1].set_ylabel("Memory of the log [MiB]")
    for i in (0, 1):
        ax[i].set_xlabel("Log size [traces]"); set_ticks(ax[i], xs, "size")
        ax[i].set_ylim(bottom=0); ax[i].legend(frameon=False, loc="upper left")
    a, b, r2 = linfit(xr, tot)
    if len(e2_paths) > 1: ax[2].fill_between(xr, g.min().reindex(xr).values, g.max().reindex(xr).values, color=INK, alpha=.12, lw=0)
    ax[2].plot(xr, a + b * np.array(xr), ":", color=GREY, lw=.9, label=f"fit, $R^2$={r2:.2f}")
    ax[2].plot(xr, tot, "o-", color=INK, ms=2.6, lw=.9, label="mean"); ax[2].set_xlabel("Rules in repository $|DR|$"); ax[2].set_ylabel("Time per question [s]")
    set_ticks(ax[2], xr, "rules")
    ax[2].set_ylim(0, max(tot.max(), g.max().max()) * 1.15); ax[2].legend(frameon=False, loc="lower right")
    for i, t in enumerate("abc"): ax[i].set_title(f"({t})", loc="left", fontsize=7)
    save(fig, out, "fig_LNCS_three_panel")


def main():
    p = argparse.ArgumentParser(); p.add_argument("--e1", required=True); p.add_argument("--e2", nargs="+", action="extend", required=True)
    p.add_argument("--out", default="."); p.add_argument("--ticks", choices=["regular", "measured"], default="regular")
    a = p.parse_args(); global TICKS; TICKS = a.ticks; os.makedirs(a.out, exist_ok=True)
    fig_e1(a.e1, a.out); fig_e2(a.e2, a.out); fig_lncs(a.e1, a.e2, a.out)

if __name__ == "__main__":
    main()
