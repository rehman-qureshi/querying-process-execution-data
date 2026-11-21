#!/usr/bin/env python3
"""
Generate nested rule-repository subsets and, for each subset, the file with the 100 questions and their identified constraints.

    python make_workload.py --arrays log_arrays.npz --support rule_support.csv --repo-all rule_repository_v2.json \
                            --out workload_draw1 --draw 1

Design
  * Full repository DR = rules that hold in the log (support >= --min-support, >= --min-activated activated cases).
  * 100 questions. Each question has: a primary constraint (distinct per question), data conditions on the primary,
    a measure, and an activity set (2-6 activities). The activity sets are chosen greedily so that (almost) every rule
    of DR is relevant to at least one question.
  * Matched set C(q, DR_k) = primary constraint + every rule of the subset DR_k whose two activities both lie in the
    activity set of q. It is executed as ONE conjunction (activated -> satisfied -> measure).
  * Subsets are nested: DR_100 (the primaries) < DR_250 < ... < DR_full. Every subset contains the primary constraint of
    every question. Fewer rules weaken the conjunction, so a question that has >= --min-cases satisfied cases with the
    full repository has at least that many with every subset.
  * Question text, primary constraint, conditions and measure are identical in all question files; only the matched
    constraints differ.
Per level k:  repo_<k>.json/.csv/.decl, questions_<k>.json/.csv, answers_<k>.csv (reference answers on the full log).
Also: manifest.csv, workload_report.md
"""
import argparse, csv, json, os, random, sys, time
from collections import Counter, defaultdict
from itertools import combinations
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import declare_workload as dw

SIZE_PROPS = {2: .05, 3: .25, 4: .30, 5: .25, 6: .15}               # activities per question
MEASURE_PROPS = {"count_cases": .25, "avg_waiting_time": .25, "avg_time_to_activation": .15,
                 "top5_resources": .20, "distinct_resources": .15}


def allocate(props, n):
    raw = {k: v * n for k, v in props.items()}; base = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - base[k], reverse=True)[: n - sum(base.values())]: base[k] += 1
    return [k for k, c in base.items() for _ in range(c)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arrays", default="log_arrays.npz"); ap.add_argument("--support", default="rule_support.csv")
    ap.add_argument("--repo-all", default="rule_repository_v2.json"); ap.add_argument("--out", default="workload_draw1")
    ap.add_argument("--n", type=int, default=100); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--draw", type=int, default=1, help="seed of the random order in which non-primary rules enter the subsets")
    ap.add_argument("--levels", type=int, nargs="+", default=[100, 250, 500, 750, 1000, -1], help="-1 = full repository")
    ap.add_argument("--min-support", type=float, default=0.95); ap.add_argument("--min-activated", type=int, default=50)
    ap.add_argument("--min-cases", type=int, default=50, help="min. satisfied cases of every question with the full repository")
    ap.add_argument("--user-prefix", default="user_", help="resource names starting with this are used in resource conditions")
    ap.add_argument("--cond-values", type=int, nargs="+", default=[100, 250, 500, 1000, 2500, 5000, 10000], help="candidate thresholds of the data condition")
    ap.add_argument("--candidates", type=int, default=300, help="random activity sets compared per question")
    a = ap.parse_args()
    import pandas as pd
    os.makedirs(a.out, exist_ok=True); rnd = random.Random(a.seed); t_start = time.time()

    # ------------------------------------------------------------ 1. full normative repository
    L = dw.Log(a.arrays); acts = L.activities
    all_rules = {r["id"]: r for r in json.load(open(a.repo_all))["rules"]}
    sup = pd.read_csv(a.support)
    keep = sup[(sup.support >= a.min_support) & (sup.activated >= a.min_activated)]
    rules = sorted(({"id": r.rule_id, "template": all_rules[r.rule_id]["template"], "activities": all_rules[r.rule_id]["activities"],
                     "support": round(float(r.support), 4), "coverage": round(float(r.coverage), 4)} for r in keep.itertuples()),
                   key=lambda r: r["id"])
    rid = {r["id"]: r for r in rules}
    pair_rules = defaultdict(list)
    for r in rules: pair_rules[frozenset(r["activities"])].append(r["id"])
    print(f"full repository: {len(rules)} rules over {len({x for r in rules for x in r['activities']})} activities, "
          f"{len(pair_rules)} activity pairs", flush=True)

    def rules_in(A): return [i for x, y in combinations(sorted(A), 2) for i in pair_rules.get(frozenset((x, y)), [])]
    def act_of(r): return r["activities"][dw.TEMPLATES[r["template"]][2]]
    conv = lambda ids: [(rid[i]["template"], L.aid[rid[i]["activities"][0]], L.aid[rid[i]["activities"][1]]) for i in ids]
    P = np.zeros((L.T, len(acts)), bool); P[L.tr, L.act] = True                    # activity present in trace
    users = [str(L.resources[r]) for r, _ in Counter(L.res.tolist()).most_common() if str(L.resources[r]).lower().startswith(a.user_prefix.lower())][:8]
    nw_opts = [v for v in a.cond_values if np.quantile(L.nw, .10) <= v <= np.quantile(L.nw, .90)]

    # ------------------------------------------------------------ 2. questions: activity sets chosen for rule coverage
    sizes = sorted(allocate(SIZE_PROPS, a.n), reverse=True); meas = allocate(MEASURE_PROPS, a.n); rnd.shuffle(meas)
    covered, used, qs = set(), set(), []
    cache = {}
    def feasible(A):                                                              # satisfied cases of the full conjunction, no conditions
        key = frozenset(A)
        if key not in cache:
            ids = rules_in(A)
            cache[key] = L.execute(conv(ids), [], "count_cases")["satisfied"] if ids else 0
        return cache[key]
    pair_list = sorted(tuple(sorted(p)) for p in pair_rules)
    for slot, (k, m) in enumerate(zip(sizes, meas)):
        done = False; m0 = m
        for attempt in range(60):
            if attempt == 30 and m == "avg_waiting_time": m = "count_cases"; print(f"  slot {slot}: no unused partner-template primary, measure changed to count_cases", flush=True)
            # grow a feasible activity set: random pair, then add activities that keep >= min_cases satisfied cases
            cp = rnd.sample(pair_list, 12)
            cp = [p for p in cp if feasible(p) >= a.min_cases] or []
            if not cp: continue
            A = list(max(cp, key=lambda p: (len(set(rules_in(p)) - covered), rnd.random())))
            while len(A) < k:
                opts = []
                for x in rnd.sample([x for x in acts if x not in A], 10):
                    B = A + [x]
                    if rules_in(B) and feasible(B) >= a.min_cases: opts.append((len(set(rules_in(B)) - covered), rnd.random(), x))
                if not opts: break
                A.append(max(opts)[2])
            ids = rules_in(A)
            for _try in range(6):
                pool = defaultdict(list)
                for i in ids:
                    if i in used: continue
                    if m == "avg_waiting_time" and not dw.TEMPLATES[rid[i]["template"]][1]: continue
                    pool[rid[i]["template"]].append(i)
                if not pool: break
                prim = rnd.choice(pool[rnd.choice(sorted(pool))]); t0 = rid[prim]["template"]
                kinds = ["net_worth_gt", "resource_eq"] + (["within_days"] if dw.TEMPLATES[t0][1] else [])
                conds = []
                for kind in rnd.sample(kinds, rnd.choices([0, 1, 2], [40, 45, 15])[0]):
                    v = {"net_worth_gt": lambda: rnd.choice(nw_opts), "resource_eq": lambda: rnd.choice(users),
                         "within_days": lambda: rnd.choice([1, 3, 7, 14, 30])}[kind]()
                    conds.append({"type": kind, "value": v})
                res = L.execute(conv([prim] + [i for i in ids if i != prim]), conds, m)
                if res["satisfied"] >= a.min_cases:
                    qs.append(dict(measure=m, conditions=conds, activities=sorted(A), primary=prim, full_ids=ids, ref=res))
                    covered |= set(ids); used.add(prim); done = True; break
            if done: break
        if not done: raise SystemExit(f"no feasible question for slot {slot} (size {k}, {m}); lower --min-cases")
        if (slot + 1) % 10 == 0:
            print(f"  {slot + 1}/{a.n} questions, rules relevant so far {len(covered)}/{len(rules)}, {time.time() - t_start:.0f}s", flush=True)
    rnd.shuffle(qs)
    for n_, q in enumerate(qs, 1):
        p = rid[q["primary"]]; g = {"constraints": [{"template": p["template"], "activities": p["activities"]}],
                                    "conditions": q["conditions"], "measure": q["measure"]}
        text = dw.nl_question(g, rnd); extra = [x for x in q["activities"] if x not in p["activities"]]
        if extra:
            lst = ", ".join(extra[:-1]) + (" and " if len(extra) > 1 else "") + extra[-1]
            text = text.rstrip("?") + f", also taking into account the activities {lst}?"
        q["qid"], q["question"] = n_, text

    # ------------------------------------------------------------ 3. nested repository subsets
    prim_ids = {q["primary"] for q in qs}
    others = [r["id"] for r in rules if r["id"] not in prim_ids]
    others = [others[i] for i in np.random.RandomState(1000 + a.draw).permutation(len(others))]
    manifest, per_level = [], {}
    for lv in a.levels:
        n_rules = len(rules) if lv < 0 or lv >= len(rules) else lv
        if n_rules < len(prim_ids): raise SystemExit(f"level {lv} is smaller than the {len(prim_ids)} primary constraints")
        members = prim_ids | set(others[: n_rules - len(prim_ids)])
        tag = f"{n_rules:04d}"; sub = [r for r in rules if r["id"] in members]
        # repository files
        json.dump({"activities": acts, "min_support": a.min_support, "min_activated": a.min_activated, "level": n_rules, "draw": a.draw,
                   "rules": sub}, open(f"{a.out}/repo_{tag}.json", "w"), indent=1)
        with open(f"{a.out}/repo_{tag}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["rule_id", "template", "activity_1", "activity_2", "support", "coverage", "semantics"])
            for r in sub: w.writerow([r["id"], dw.TEMPLATES[r["template"]][0], *r["activities"], r["support"], r["coverage"], dw.SEMANTICS[r["template"]]])
        with open(f"{a.out}/repo_{tag}.decl", "w", encoding="utf-8") as f:
            f.writelines(f"activity {x}\n" for x in acts)
            f.writelines(f"{dw.TEMPLATES[r['template']][0]}[{', '.join(r['activities'])}] | | |\n" for r in sub)
        # question file
        qlev = []
        for q in qs:
            ids = [q["primary"]] + [i for i in q["full_ids"] if i in members and i != q["primary"]]
            qlev.append({"qid": q["qid"], "question": q["question"], "measure": q["measure"], "activities": q["activities"],
                         "primary_rule_id": q["primary"], "n_constraints": len(ids),
                         "gold": {"constraints": [{"rule_id": i, "template": rid[i]["template"], "activities": rid[i]["activities"]} for i in ids],
                                  "conditions": q["conditions"], "measure": q["measure"]}})
        json.dump(qlev, open(f"{a.out}/questions_{tag}.json", "w"), indent=1, ensure_ascii=False)
        with open(f"{a.out}/questions_{tag}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["qid", "question", "measure", "primary_constraint", "conditions", "n_activities", "n_constraints", "constraint_ids"])
            for q in qlev:
                c = q["gold"]["constraints"][0]
                w.writerow([q["qid"], q["question"], q["measure"], f"{dw.TEMPLATES[c['template']][0]}({c['activities'][0]}, {c['activities'][1]})",
                            json.dumps(q["gold"]["conditions"]), len(q["activities"]), q["n_constraints"], " ".join(x["rule_id"] for x in q["gold"]["constraints"])])
        # reference answers on the full log
        t0 = time.time(); ans = []
        for q in qlev:
            r = L.execute(conv([c["rule_id"] for c in q["gold"]["constraints"]]), q["gold"]["conditions"], q["measure"]); ans.append(r)
        with open(f"{a.out}/answers_{tag}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["qid", "n_constraints", "activated_cases", "satisfied_cases", "coverage", "support", "answer"])
            for q, r in zip(qlev, ans): w.writerow([q["qid"], q["n_constraints"], r["activated"], r["satisfied"], f"{r['coverage']:.4f}", f"{r['support']:.4f}", r["answer"]])
        nc = np.array([q["n_constraints"] for q in qlev]); per_level[n_rules] = (qlev, ans)
        manifest.append(dict(n_rules=n_rules, repo_file=f"repo_{tag}.json", questions_file=f"questions_{tag}.json", answers_file=f"answers_{tag}.csv",
                             mean_C=round(float(nc.mean()), 2), median_C=int(np.median(nc)), min_C=int(nc.min()), max_C=int(nc.max()), total_constraints=int(nc.sum())))
        print(f"level {n_rules:5d}: mean |C| {nc.mean():5.2f} (min {nc.min()}, median {int(np.median(nc))}, max {nc.max()}); answers {time.time() - t0:.0f}s", flush=True)
    with open(f"{a.out}/manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=manifest[0].keys()); w.writeheader(); w.writerows(manifest)

    # ------------------------------------------------------------ 4. checks + report
    lv_sorted = sorted(per_level); viol = 0
    for lo, hi in zip(lv_sorted, lv_sorted[1:]):                                  # more rules -> never more satisfied cases
        viol += sum(1 for x, y in zip(per_level[lo][1], per_level[hi][1]) if y["satisfied"] > x["satisfied"])
    full = per_level[lv_sorted[-1]][1]; sat = [r["satisfied"] for r in full]
    relevant = {i for q in qs for i in q["full_ids"]}; pairs_rel = {frozenset(rid[i]["activities"]) for i in relevant}
    act_use = Counter(x for q in qs for x in q["activities"])
    lines = [f"# Workload report (draw {a.draw}, seed {a.seed})", "",
             f"- Full repository: {len(rules)} rules with support >= {a.min_support} and >= {a.min_activated} activated cases, "
             f"over {len({x for r in rules for x in r['activities']})} of {len(acts)} activities; {len(pair_rules)} activity pairs.",
             f"- Questions: {len(qs)}; distinct primary constraints: {len(prim_ids)}; activities per question: {dict(sorted(Counter(len(q['activities']) for q in qs).items()))}.",
             f"- Rules relevant to at least one question: {len(relevant)} of {len(rules)} ({100 * len(relevant) / len(rules):.1f}%); "
             f"activity pairs covered: {len(pairs_rel)} of {len(pair_rules)}.",
             f"- Activities used by at least one question: {len(act_use)} of {len(acts)}.",
             f"- Measures: {dict(Counter(q['measure'] for q in qs))}",
             f"- Primary templates: {dict(Counter(rid[q['primary']]['template'] for q in qs))}",
             f"- Conditions: {dict(Counter(c['type'] for q in qs for c in q['conditions']))}; questions without condition: {sum(1 for q in qs if not q['conditions'])}",
             f"- Satisfied cases with the full repository: min {min(sat)}, median {int(np.median(sat))}, max {max(sat)}.",
             f"- Monotonicity check (more rules never give more satisfied cases): {viol} violations.", "",
             "| rules in repository | mean constraints per question | min | median | max |", "|---|---|---|---|---|"]
    lines += [f"| {m['n_rules']} | {m['mean_C']} | {m['min_C']} | {m['median_C']} | {m['max_C']} |" for m in manifest]
    open(f"{a.out}/workload_report.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[2:12])); print(f"done in {time.time() - t_start:.0f}s -> {a.out}/")


if __name__ == "__main__":
    main()
