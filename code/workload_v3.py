#!/usr/bin/env python3
"""
Normative rule repository + 100 questions whose matched constraints grow with the repository (workload v3).

  python workload_v3.py support   --arrays log_arrays.npz       # support/coverage of every rule of rule_repository_v2 (~4 min)
  python workload_v3.py normrepo  --min-support 0.95            # rule_repository_v3.*  (rules that hold in the log)
  python workload_v3.py questions --n 100 --seed 1               # questions_v3.*, reference_answers_v3.csv

Definitions
  repository DR      : rules with support >= theta and >= min_activated activated cases (normative repository).
  question q         : primary constraint + data conditions + measure + the set of activities it mentions.
  matched set C(q,DR): primary constraint  +  every rule of DR whose two activities both occur in the question.
  execution          : C(q,DR) is executed as ONE conjunction (activated -> satisfied -> measure), see workload_semantics.md.
Questions are generated so that the conjunction of the FULL matched set has >= min_cases satisfied cases. Because every
repository subset contains the primary constraint and fewer rules only weaken the conjunction, the answer is non-empty
for every subset.
"""
import argparse, csv, json, os, random, sys, time
from collections import Counter, defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import declare_workload as dw


def expand_question(q, ids, rules_by_id):
    """Question with its matched set C(q, DR_ids): primary constraint + relevant rules that are in the repository subset."""
    cons = list(q["gold"]["constraints"])
    for rid in q["relevant_rule_ids"]:
        if ids is None or rid in ids:
            r = rules_by_id[rid]
            cons.append({"rule_id": rid, "template": r["template"], "activities": r["activities"]})
    g = dict(q["gold"]); g["constraints"] = cons
    return {**q, "gold": g, "n_constraints": len(cons)}


def cmd_support(a):
    L = dw.Log(a.arrays); rules = json.load(open(a.repo_in))["rules"]; rows = []; t0 = time.time()
    for k, r in enumerate(rules):
        x, y = r["activities"]
        res = L.execute([(r["template"], L.aid[x], L.aid[y])], [], "count_cases")
        rows.append((r["id"], r["template"], x, y, res["activated"], res["satisfied"], res["coverage"], res["support"]))
        if (k + 1) % 1000 == 0: print(f"  {k + 1}/{len(rules)} rules, {time.time() - t0:.0f}s", flush=True)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["rule_id", "template", "activity_1", "activity_2", "activated", "satisfied", "coverage", "support"])
        w.writerows(rows)
    print("wrote", a.out)


def cmd_normrepo(a):
    import pandas as pd
    full = json.load(open(a.repo_in)); d = pd.read_csv(a.support)
    keep = d[(d.support >= a.min_support) & (d.activated >= a.min_activated)]
    info = {r.rule_id: r for r in keep.itertuples()}
    rules = [{**r, "support": round(float(info[r["id"]].support), 4), "coverage": round(float(info[r["id"]].coverage), 4)}
             for r in full["rules"] if r["id"] in info]
    json.dump({"activities": full["activities"], "templates": full["templates"], "min_support": a.min_support,
               "min_activated": a.min_activated, "rules": rules}, open(a.repo_out + ".json", "w"), indent=1)
    with open(a.repo_out + ".csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["rule_id", "template", "activity_1", "activity_2", "support", "coverage", "semantics"])
        for r in rules: w.writerow([r["id"], dw.TEMPLATES[r["template"]][0], *r["activities"], r["support"], r["coverage"], dw.SEMANTICS[r["template"]]])
    with open(a.repo_out + ".decl", "w", encoding="utf-8") as f:
        f.writelines(f"activity {x}\n" for x in full["activities"])
        f.writelines(f"{dw.TEMPLATES[r['template']][0]}[{', '.join(r['activities'])}] | | |\n" for r in rules)
    print(f"{len(rules)} rules (support >= {a.min_support}, activated >= {a.min_activated}) -> {a.repo_out}.*")
    print(dict(Counter(r["template"] for r in rules)))


def cmd_questions(a):
    rnd = random.Random(a.seed)
    L = dw.Log(a.arrays); repo = json.load(open(a.repo)); rules = repo["rules"]
    by_tpl = defaultdict(list)
    for r in rules: by_tpl[r["template"]].append(r)
    pres = {L.activities[i]: len(np.unique(L.tr[L.act == i])) / L.T for i in range(len(L.activities))}
    freq = [x for x, p in pres.items() if p >= a.min_support]
    users = [L.resources[r] for r, _ in Counter(L.res.tolist()).most_common() if str(L.resources[r]).startswith("user_")][:8]
    nw_opts = [v for v in (100, 250, 500, 1000, 2500, 5000, 10000) if np.quantile(L.nw, .10) <= v <= np.quantile(L.nw, .90)]
    n = a.n
    meas = (["count_cases"] * 25 + ["avg_waiting_time"] * 25 + ["avg_time_to_activation"] * 15 +
            ["top5_resources"] * 20 + ["distinct_resources"] * 15)[:n]; rnd.shuffle(meas)
    extras = ([0] * 40 + [1] * 25 + [2] * 20 + [3] * 10 + [4] * 5)[:n]; rnd.shuffle(extras)
    tpls = [t for t in dw.TEMPLATES if by_tpl[t]]
    out, seen, rr, used = [], set(), 0, set()
    for i in range(n):
        m, ne = meas[i], extras[i]
        for attempt in range(3000):
            pool = [t for t in tpls if dw.TEMPLATES[t][1]] if m == "avg_waiting_time" else tpls
            t0 = pool[(rr + attempt) % len(pool)] if attempt < 300 else rnd.choice(pool)
            cand = [r for r in by_tpl[t0] if r["id"] not in used] if attempt < 2000 else by_tpl[t0]
            if not cand: continue                                    # template has no unused rule left
            prim = rnd.choice(cand); pa = set(prim["activities"])
            if not all(x in freq for x in pa): continue
            ex = rnd.sample([x for x in freq if x not in pa], ne) if ne else []
            acts = pa | set(ex)
            rel = [r for r in rules if r["id"] != prim["id"] and set(r["activities"]) <= acts]
            conds, kinds = [], ["net_worth_gt", "resource_eq"] + (["within_days"] if dw.TEMPLATES[t0][1] else [])
            for kind in rnd.sample(kinds, rnd.choices([0, 1, 2], [40, 45, 15])[0]):
                v = {"net_worth_gt": lambda: rnd.choice(nw_opts), "resource_eq": lambda: str(rnd.choice(users)),
                     "within_days": lambda: rnd.choice([1, 3, 7, 14, 30])}[kind]()
                conds.append({"type": kind, "value": v})
            cons = [(prim["template"], *prim["activities"])] + [(r["template"], *r["activities"]) for r in rel]
            res = L.execute([(t, L.aid[x], L.aid[y]) for t, x, y in cons], conds, m)
            if res["satisfied"] < a.min_cases: continue
            gold = {"constraints": [{"rule_id": prim["id"], "template": prim["template"], "activities": prim["activities"]}],
                    "conditions": conds, "measure": m}
            key = json.dumps([gold, sorted(ex)], sort_keys=True)
            if key in seen: continue
            seen.add(key); rr += 1; used.add(prim["id"])
            text = dw.nl_question(gold, rnd)
            if ex:
                lst = ", ".join(ex[:-1]) + (" and " if len(ex) > 1 else "") + ex[-1]
                text = text.rstrip("?") + f", also taking into account the activities {lst}?"
            out.append({"qid": i + 1, "question": text, "measure": m, "activities": sorted(acts), "extra_activities": ex,
                        "gold": gold, "relevant_rule_ids": [r["id"] for r in rel], "n_constraints_full": 1 + len(rel), "ref": res})
            break
        else:
            raise SystemExit(f"could not build question {i + 1} ({m}, {ne} extra activities); lower --min-cases")
        if (i + 1) % 20 == 0: print(f"  {i + 1}/{n} questions built", flush=True)

    qs = [{k: v for k, v in q.items() if k != "ref"} for q in out]
    json.dump(qs, open(a.questions + ".json", "w"), indent=1, ensure_ascii=False)
    with open(a.questions + ".csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["qid", "question", "measure", "primary_constraint", "conditions", "n_activities", "matched_rules_full_repo"])
        for q in qs:
            c = q["gold"]["constraints"][0]
            w.writerow([q["qid"], q["question"], q["measure"], f"{dw.TEMPLATES[c['template']][0]}({c['activities'][0]}, {c['activities'][1]})",
                        json.dumps(q["gold"]["conditions"]), len(q["activities"]), q["n_constraints_full"]])
    with open(a.answers, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["qid", "n_constraints_full", "activated_cases", "satisfied_cases", "coverage", "support", "answer"])
        for q in out:
            r = q["ref"]; w.writerow([q["qid"], q["n_constraints_full"], r["activated"], r["satisfied"], f"{r['coverage']:.4f}", f"{r['support']:.4f}", r["answer"]])
    nc = np.array([q["n_constraints_full"] for q in qs])
    print("matched constraints per question (full repo): min", nc.min(), "median", int(np.median(nc)), "max", nc.max(), "mean %.1f" % nc.mean())
    print("distinct primary rules:", len({q['gold']['constraints'][0]['rule_id'] for q in qs}))
    print("measures:", dict(Counter(q["measure"] for q in qs)))
    print("primary templates:", dict(Counter(q["gold"]["constraints"][0]["template"] for q in qs)))
    sat = [q["ref"]["satisfied"] for q in out]; print("satisfied cases (full conjunction): min", min(sat), "median", int(np.median(sat)), "max", max(sat))


def main():
    p = argparse.ArgumentParser(); sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("support"); s.add_argument("--arrays", default="log_arrays.npz")
    s.add_argument("--repo-in", default="rule_repository_v2.json"); s.add_argument("--out", default="rule_support.csv"); s.set_defaults(f=cmd_support)
    s = sp.add_parser("normrepo"); s.add_argument("--repo-in", default="rule_repository_v2.json"); s.add_argument("--support", default="rule_support.csv")
    s.add_argument("--repo-out", default="rule_repository_v3"); s.add_argument("--min-support", type=float, default=0.95)
    s.add_argument("--min-activated", type=int, default=50); s.set_defaults(f=cmd_normrepo)
    s = sp.add_parser("questions"); s.add_argument("--arrays", default="log_arrays.npz"); s.add_argument("--repo", default="rule_repository_v3.json")
    s.add_argument("--questions", default="questions_v3"); s.add_argument("--answers", default="reference_answers_v3.csv")
    s.add_argument("--n", type=int, default=100); s.add_argument("--seed", type=int, default=1)
    s.add_argument("--min-support", type=float, default=0.005); s.add_argument("--min-cases", type=int, default=50); s.set_defaults(f=cmd_questions)
    a = p.parse_args(); a.f(a)

if __name__ == "__main__":
    main()
