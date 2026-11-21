#!/usr/bin/env python3
"""
Declarative rule repository + 100 natural-language business questions for BPIC19
(3-way match, invoice before GR), following the approach of "Querying Business
Process Execution Data":

   question --identify--> constraints C (subset of the repository) [+ condition, measure]
   C --execute--> activated cases -> satisfied cases (L_conform) -> requested measure

Run in this order:
   python declare_workload.py prep      --csv process_execution_data.csv
   python declare_workload.py repo
   python declare_workload.py questions --n 100 --seed 1
See workload_semantics.md for the exact activation / satisfaction semantics.
"""
import argparse, csv, json, os, random, time
from bisect import bisect_left, bisect_right
from collections import Counter
from itertools import permutations

import numpy as np

# ----------------------------------------------------------------------------
# Templates: name -> (Declare/RuM name, has_partner, activation argument index)
# ----------------------------------------------------------------------------
TEMPLATES = {
    "response":            ("Response",            True,  0),
    "alt_response":        ("Alternate Response",  True,  0),
    "chain_response":      ("Chain Response",      True,  0),
    "precedence":          ("Precedence",          True,  1),
    "alt_precedence":      ("Alternate Precedence", True, 1),
    "chain_precedence":    ("Chain Precedence",    True,  1),
    "responded_existence": ("Responded Existence", False, 0),
    "not_co_existence":    ("Not Co-Existence",    False, 0),
    "not_succession":      ("Not Succession",      False, 0),
}
PARTNER = [t for t, v in TEMPLATES.items() if v[1]]
SEMANTICS = {
    "response": "every A is eventually followed by B",
    "alt_response": "every A is followed by B, with no other A in between",
    "chain_response": "every A is immediately followed by B",
    "precedence": "every B is preceded by an earlier A",
    "alt_precedence": "every B is preceded by A, with no other B in between",
    "chain_precedence": "every B is immediately preceded by A",
    "responded_existence": "if A occurs, B occurs in the same case (any order)",
    "not_co_existence": "if A occurs, B does not occur in the same case",
    "not_succession": "B never occurs after A",
}
# NL phrasings of the control-flow part, {A}/{B} = 1st/2nd argument
import os
COND_TEXT = os.environ.get("DW_COND_TEXT", "the cumulative net worth at {X} exceeds \u20ac{v}")   # data-condition phrasing (override per log)

CLAUSES = {
    "response": ["{A} is eventually followed by {B}", "every {A} is later followed by {B}"],
    "alt_response": ["every {A} is followed by {B} before {A} occurs again",
                     "{A} is followed by {B} with no other {A} in between"],
    "chain_response": ["{A} is immediately followed by {B}", "every {A} is directly followed by {B}"],
    "precedence": ["every {B} is preceded by an earlier {A}", "{B} only occurs after {A} has occurred"],
    "alt_precedence": ["every {B} is preceded by {A}, with no other {B} in between",
                       "each {B} is preceded by {A} without another {B} occurring in between"],
    "chain_precedence": ["{B} is immediately preceded by {A}", "every {B} comes directly after {A}"],
    "responded_existence": ["{B} also occurs whenever {A} occurs, before or after it",
                            "{B} occurs somewhere in every case in which {A} occurs"],
    "not_co_existence": ["{A} and {B} never occur together in the same case",
                         "{B} does not occur in cases where {A} occurs"],
    "not_succession": ["{B} never occurs after {A}", "{A} is never followed by {B}"],
}
MEASURES = {
    "count_cases": ["What is the total number of cases where {c}?", "How many cases are there where {c}?"],
    "avg_waiting_time": ["What is the average waiting time between {A} and {B} in cases where {c}?",
                         "On average, how long is the waiting time between {A} and {B} when {c}?"],
    "avg_time_to_activation": ["How long does it take on average from the start of a case until {X} occurs, when {c}?",
                               "What is the average time from case start to {X} in cases where {c}?"],
    "top5_resources": ["Which are the top 5 resources that most frequently perform {X} in cases where {c}?",
                       "Who are the five resources performing {X} most often when {c}?"],
    "distinct_resources": ["How many distinct resources perform {X} in cases where {c}?",
                           "What is the number of different resources that perform {X} when {c}?"],
}

# ----------------------------------------------------------------------------
# Variant-level evaluation of one constraint
# ----------------------------------------------------------------------------
def var_table(tpl, a, b, seq):
    """Per position of a variant: is_act, ok (control flow satisfied), partner position (-1 if none)."""
    n = len(seq)
    pa = [i for i, x in enumerate(seq) if x == a]
    pb = [i for i, x in enumerate(seq) if x == b]
    act, ok, par = [False] * n, [False] * n, [-1] * n
    if tpl in ("response", "alt_response", "chain_response"):
        for k, i in enumerate(pa):
            act[i] = True
            jk = bisect_right(pb, i)
            j = pb[jk] if jk < len(pb) else -1
            if tpl == "response":
                good = j >= 0
            elif tpl == "alt_response":
                nxt = pa[k + 1] if k + 1 < len(pa) else n + 1
                good = j >= 0 and nxt > j
            else:
                j = i + 1 if i + 1 < n and seq[i + 1] == b else -1
                good = j >= 0
            if good:
                ok[i], par[i] = True, j
    elif tpl in ("precedence", "alt_precedence", "chain_precedence"):
        for k, j in enumerate(pb):
            act[j] = True
            ik = bisect_left(pa, j) - 1
            i = pa[ik] if ik >= 0 else -1
            if tpl == "precedence":
                good = i >= 0
            elif tpl == "alt_precedence":
                prev_b = pb[k - 1] if k > 0 else -1
                good = i >= 0 and prev_b < i
            else:
                i = j - 1 if j > 0 and seq[j - 1] == a else -1
                good = i >= 0
            if good:
                ok[j], par[j] = True, i
    elif tpl == "responded_existence":
        for i in pa:
            act[i], ok[i] = True, len(pb) > 0
    elif tpl == "not_co_existence":
        for i in pa:
            act[i], ok[i] = True, len(pb) == 0
    elif tpl == "not_succession":
        for i in pa:
            act[i], ok[i] = True, not (pb and pb[-1] > i)
    return act, ok, par

def fmt_dur(sec):
    sec = int(round(sec)); d, r = divmod(sec, 86400); h, r = divmod(r, 3600); m = r // 60
    return f"{d} days, {h} hours, {m} minutes"

# ----------------------------------------------------------------------------
# Event data + reference executor
# ----------------------------------------------------------------------------
class Log:
    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.act, self.ts, self.res, self.nw = z["act"], z["ts"], z["res"], z["nw"]
        self.offs, self.var_of_trace = z["offs"], z["var_of_trace"]
        self.activities = list(z["activities"]); self.resources = list(z["resources"])
        lens, flat = z["vlens"], z["vflat"]
        ends = np.cumsum(lens); starts = ends - lens
        self.variants = [tuple(flat[s:e].tolist()) for s, e in zip(starts, ends)]
        self.voff = starts
        self.N, self.T = len(self.act), len(self.offs) - 1
        self.tr = np.repeat(np.arange(self.T), np.diff(self.offs))
        self.ev = np.arange(self.N)
        self.pos = self.ev - self.offs[self.tr]
        self.vidx = self.voff[self.var_of_trace[self.tr]] + self.pos
        self.aid = {a: i for i, a in enumerate(self.activities)}
        self.rid = {r: i for i, r in enumerate(self.resources)}
        self._cache = {}

    def tables(self, tpl, a, b):
        key = (tpl, a, b)
        if key not in self._cache:
            A, O, P = [], [], []
            for seq in self.variants:
                x, y, z = var_table(tpl, a, b, seq); A += x; O += y; P += z
            self._cache[key] = (np.array(A), np.array(O), np.array(P, dtype=np.int64))
        av, ov, pv = self._cache[key]
        is_act, ok, p = av[self.vidx], ov[self.vidx], pv[self.vidx]
        pf = np.where(p >= 0, self.ev - self.pos + p, -1)
        return is_act, ok, pf

    def _tr(self, mask):
        return np.bincount(self.tr[mask], minlength=self.T) > 0

    def execute(self, cons, conds=(), measure="count_cases"):
        """cons: [(template, a_id, b_id), ...] (first = primary); conds apply to the primary."""
        st = {"tables": 0.0, "filter": 0.0, "measure": 0.0}; mark = [time.perf_counter()]
        def lap(k):
            now = time.perf_counter(); st[k] += now - mark[0]; mark[0] = now
        tpl, a, b = cons[0]
        is_act, ok, pf = self.tables(tpl, a, b)
        lap("tables")
        cm = np.ones(self.N, bool)
        for c in conds:
            if c["type"] == "net_worth_gt": cm &= self.nw > c["value"]
            elif c["type"] == "resource_eq": cm &= self.res == self.rid[c["value"]]
            elif c["type"] == "within_days":
                gap = np.abs(self.ts[np.maximum(pf, 0)] - self.ts)
                ok = ok & (pf >= 0) & (gap <= c["value"] * 86400)
        act1 = is_act & cm
        activated = self._tr(act1)
        violated = self._tr(act1 & ~ok)
        lap("filter")
        for (t2, a2, b2) in cons[1:]:
            ia, ok2, _ = self.tables(t2, a2, b2)
            lap("tables")
            activated &= self._tr(ia)
            violated |= self._tr(ia & ~ok2)
            lap("filter")
        sat = activated & ~violated
        res = {"activated": int(activated.sum()), "satisfied": int(sat.sum())}
        res["coverage"] = res["activated"] / self.T
        res["support"] = res["satisfied"] / res["activated"] if res["activated"] else 0.0
        lap("filter")
        idx = np.nonzero(act1 & sat[self.tr])[0]
        trs = self.tr[idx]
        first = idx[np.r_[True, trs[1:] != trs[:-1]]] if len(idx) else idx
        if measure == "count_cases":
            res["value"] = res["satisfied"]; res["answer"] = f"{res['satisfied']} cases"
        elif measure == "avg_waiting_time":
            v = float(np.mean(np.abs(self.ts[pf[first]] - self.ts[first]))) if len(first) else float("nan")
            res["value"] = v; res["answer"] = fmt_dur(v) if len(first) else "n/a"
        elif measure == "avg_time_to_activation":
            v = float(np.mean(self.ts[first] - self.ts[self.offs[self.tr[first]]])) if len(first) else float("nan")
            res["value"] = v; res["answer"] = fmt_dur(v) if len(first) else "n/a"
        else:
            R = len(self.resources)
            pairs = np.unique(trs.astype(np.int64) * R + self.res[idx])
            cnt = np.bincount(pairs % R, minlength=R)
            if measure == "distinct_resources":
                res["value"] = int((cnt > 0).sum()); res["answer"] = f"{res['value']} resources"
            else:
                top = sorted(np.nonzero(cnt)[0], key=lambda r: (-cnt[r], self.resources[r]))[:5]
                res["value"] = [(self.resources[r], int(cnt[r])) for r in top]
                res["answer"] = "; ".join(f"{n} ({c} cases)" for n, c in res["value"])
        lap("measure"); res["stages"] = st
        return res

# ----------------------------------------------------------------------------
# prep: CSV -> compact arrays
# ----------------------------------------------------------------------------
def cmd_prep(a):
    import pandas as pd
    cols = [a.case, a.activity, a.timestamp, a.resource, a.networth] + ([a.keep_col] if a.keep_col else [])
    df = pd.read_csv(a.csv, usecols=list(dict.fromkeys(cols)), low_memory=False)
    if a.keep_col:                                                       # e.g. --keep-col lifecycle:transition --keep-val complete
        n0 = len(df); df = df[df[a.keep_col] == a.keep_val].reset_index(drop=True); print(f"kept {len(df)} of {n0} events with {a.keep_col} == {a.keep_val}")
    print(df.shape, "NaN per column:", df.isna().sum().to_dict())
    ts = (pd.to_datetime(df[a.timestamp], utc=True, format="ISO8601") - pd.Timestamp("1970-01-01", tz="UTC")) / pd.Timedelta(seconds=1)
    cc, case_ids = pd.factorize(df[a.case])
    act, activities = pd.factorize(df[a.activity], sort=True)
    res, resources = pd.factorize(df[a.resource].fillna("unknown"), sort=True)
    order = np.lexsort((np.arange(len(df)), ts.to_numpy(), cc))        # case, time, original order
    cc, act, res = cc[order], act[order], res[order]
    ts = ts.to_numpy()[order]; nw = df[a.networth].fillna(0).to_numpy()[order]
    T = cc.max() + 1
    offs = np.concatenate([[0], np.cumsum(np.bincount(cc, minlength=T))])
    al = act.tolist(); vid, vmap, vseqs = np.zeros(T, np.int32), {}, []
    for t in range(T):
        s = tuple(al[offs[t]:offs[t + 1]])
        if s not in vmap:
            vmap[s] = len(vseqs); vseqs.append(s)
        vid[t] = vmap[s]
    vlens = np.array([len(s) for s in vseqs]); vflat = np.array([x for s in vseqs for x in s])
    np.savez(a.out, act=act.astype(np.int16), ts=ts, res=res.astype(np.int32), nw=nw, offs=offs,
             var_of_trace=vid, vlens=vlens, vflat=vflat.astype(np.int16),
             activities=np.array(list(activities)), resources=np.array(list(resources)),
             cases=np.array(list(case_ids)))
    print(f"{len(df)} events, {T} cases, {len(vseqs)} variants, {len(activities)} activities, "
          f"{len(resources)} resources -> {a.out}")

# ----------------------------------------------------------------------------
# repo: all binary constraints over all activities
# ----------------------------------------------------------------------------
def cmd_repo(a):
    L = Log(a.arrays); acts = L.activities
    rules = []
    for t in TEMPLATES:
        for x, y in permutations(acts, 2):
            rules.append({"id": f"R{len(rules):05d}", "template": t, "activities": [x, y]})
    json.dump({"activities": acts, "templates": {t: v[0] for t, v in TEMPLATES.items()},
               "rules": rules}, open(a.repo + ".json", "w"), indent=1)
    with open(a.repo + ".csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["rule_id", "template", "activity_1", "activity_2", "semantics"])
        for r in rules:
            w.writerow([r["id"], TEMPLATES[r["template"]][0], *r["activities"], SEMANTICS[r["template"]]])
    with open(a.repo + ".decl", "w", encoding="utf-8") as f:
        f.writelines(f"activity {x}\n" for x in acts)
        f.writelines(f"{TEMPLATES[r['template']][0]}[{', '.join(r['activities'])}] | | |\n" for r in rules)
    print(f"{len(rules)} rules ({len(TEMPLATES)} templates x {len(acts)}*{len(acts)-1} ordered pairs) -> {a.repo}.*")

# ----------------------------------------------------------------------------
# questions
# ----------------------------------------------------------------------------
def nl_question(g, rnd):
    cons = g["constraints"]; t0 = cons[0]["template"]; A, B = cons[0]["activities"]
    X = A if TEMPLATES[t0][2] == 0 else B
    parts = []
    c1 = rnd.choice(CLAUSES[t0]).format(A=A, B=B)
    for c in g["conditions"]:
        if c["type"] == "within_days":
            c1 += f", with at most {c['value']} {'day' if c['value'] == 1 else 'days'} between {A} and {B}"
    parts.append(c1)
    for c in cons[1:]:
        parts.append(rnd.choice(CLAUSES[c["template"]]).format(A=c["activities"][0], B=c["activities"][1]))
    for c in g["conditions"]:
        if c["type"] == "net_worth_gt": parts.append(COND_TEXT.format(X=X, v=c["value"]))
        if c["type"] == "resource_eq": parts.append(f"{X} is performed by {c['value']}")
    return rnd.choice(MEASURES[g["measure"]]).format(c=", and ".join(parts), A=A, B=B, X=X)

def cmd_questions(a):
    rnd = random.Random(a.seed)
    L = Log(a.arrays); repo = json.load(open(a.repo + ".json"))
    rid = {(r["template"], *r["activities"]): r["id"] for r in repo["rules"]}
    pres = np.zeros(len(L.activities))
    for ai in range(len(L.activities)):
        pres[ai] = len(np.unique(L.tr[L.act == ai]))
    freq = [L.activities[i] for i in range(len(L.activities)) if pres[i] / L.T >= a.min_support]
    users = Counter(L.res.tolist())
    users = [L.resources[r] for r, _ in users.most_common() if str(L.resources[r]).startswith("user_")][:8]
    nw_opts = [v for v in (100, 250, 500, 1000, 2500, 5000, 10000)
               if np.quantile(L.nw, 0.10) <= v <= np.quantile(L.nw, 0.90)]
    print(f"{len(freq)} frequent activities; net worth thresholds {nw_opts}; resources {users}")

    n = a.n
    sizes = ([1] * 55 + [2] * 25 + [3] * 15 + [4] * 5)[:n]; rnd.shuffle(sizes)
    meas = (["count_cases"] * 25 + ["avg_waiting_time"] * 25 + ["avg_time_to_activation"] * 15 +
            ["top5_resources"] * 20 + ["distinct_resources"] * 15)[:n]; rnd.shuffle(meas)
    tpls = list(TEMPLATES)
    out, seen, nw_i = [], set(), 0
    for i in range(n):
        m, k = meas[i], sizes[i]
        for attempt in range(400):
            pool = PARTNER if m == "avg_waiting_time" else tpls
            if attempt < 150:                       # balanced round-robin over templates, random fallback
                t0 = pool[(nw_i if m == "avg_waiting_time" else i) % len(pool)]
            else:
                t0 = rnd.choice(pool)
            x, y = (str(v) for v in rnd.sample(freq, 2))
            conds, kinds = [], ["net_worth_gt", "resource_eq"] + (["within_days"] if TEMPLATES[t0][1] else [])
            for kind in rnd.sample(kinds, rnd.choices([0, 1, 2], [40, 45, 15])[0]):
                v = {"net_worth_gt": lambda: rnd.choice(nw_opts), "resource_eq": lambda: str(rnd.choice(users)),
                     "within_days": lambda: rnd.choice([1, 3, 7, 14, 30])}[kind]()
                conds.append({"type": kind, "value": v})
            cons = [(t0, x, y)]
            r = L.execute([(t0, L.aid[x], L.aid[y])], conds, m)
            if r["satisfied"] < a.min_cases:
                continue
            good = True
            for _ in range(k - 1):                                   # add secondary constraints
                for _try in range(40):
                    t2 = rnd.choice(tpls); x2, y2 = rnd.sample(freq, 2)
                    if (t2, x2, y2) in cons or {x2, y2} == {x, y}:
                        continue
                    cand = cons + [(t2, x2, y2)]
                    r2 = L.execute([(t, L.aid[p], L.aid[q]) for t, p, q in cand], conds, m)
                    if r2["satisfied"] >= a.min_cases:
                        cons, r = cand, r2; break
                else:
                    good = False; break
            if not good:
                continue
            gold = {"constraints": [{"rule_id": rid[c], "template": c[0], "activities": [c[1], c[2]]} for c in cons],
                    "conditions": conds, "measure": m}
            key = json.dumps(gold, sort_keys=True)
            if key in seen:
                continue
            seen.add(key); nw_i += (m == "avg_waiting_time")
            out.append({"qid": i + 1, "question": nl_question(gold, rnd), "gold": gold, "ref": r}); break
        else:
            raise SystemExit(f"could not build question {i + 1} ({m}, {k} constraints); lower --min-cases")
        if (i + 1) % 20 == 0: print(f"  {i + 1}/{n} questions built")

    qs = [{"qid": q["qid"], "question": q["question"], "gold": q["gold"],
           "n_constraints": len(q["gold"]["constraints"]), "measure": q["gold"]["measure"]} for q in out]
    json.dump(qs, open(a.questions + ".json", "w"), indent=1, ensure_ascii=False)
    with open(a.questions + ".csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["qid", "question", "n_constraints", "constraints", "conditions", "measure"])
        for q in qs:
            g = q["gold"]
            w.writerow([q["qid"], q["question"], q["n_constraints"],
                        "; ".join(f"{TEMPLATES[c['template']][0]}({c['activities'][0]}, {c['activities'][1]})"
                                  for c in g["constraints"]),
                        json.dumps(g["conditions"]), g["measure"]])
    with open(a.answers, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["qid", "activated_cases", "satisfied_cases", "coverage", "support", "answer"])
        for q in out:
            r = q["ref"]; w.writerow([q["qid"], r["activated"], r["satisfied"], f"{r['coverage']:.4f}",
                                      f"{r['support']:.4f}", r["answer"]])
    c = lambda f: dict(Counter(f(q) for q in qs))
    print("constraints per question:", c(lambda q: q["n_constraints"]))
    print("measures:", c(lambda q: q["measure"]))
    print("primary templates:", c(lambda q: q["gold"]["constraints"][0]["template"]))
    print("conditions:", dict(Counter(x["type"] for q in qs for x in q["gold"]["conditions"])))
    sat = [q["ref"]["satisfied"] for q in out]; print("satisfied cases: min", min(sat), "median", int(np.median(sat)), "max", max(sat))

def main():
    p = argparse.ArgumentParser(); sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("prep"); s.add_argument("--csv", required=True); s.add_argument("--out", default="log_arrays.npz")
    s.add_argument("--case", default="case:concept:name"); s.add_argument("--activity", default="concept:name")
    s.add_argument("--timestamp", default="time:timestamp"); s.add_argument("--resource", default="org:resource")
    s.add_argument("--networth", default="Cumulative net worth (EUR)")
    s.add_argument("--keep-col", default=None); s.add_argument("--keep-val", default=None); s.set_defaults(f=cmd_prep)
    s = sp.add_parser("repo"); s.add_argument("--arrays", default="log_arrays.npz")
    s.add_argument("--repo", default="rule_repository_v2"); s.set_defaults(f=cmd_repo)
    s = sp.add_parser("questions"); s.add_argument("--arrays", default="log_arrays.npz")
    s.add_argument("--repo", default="rule_repository_v2"); s.add_argument("--questions", default="questions_v2")
    s.add_argument("--answers", default="reference_answers_v2.csv"); s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=1); s.add_argument("--min-support", type=float, default=0.005)
    s.add_argument("--min-cases", type=int, default=50); s.set_defaults(f=cmd_questions)
    a = p.parse_args(); a.f(a)

if __name__ == "__main__":
    main()
