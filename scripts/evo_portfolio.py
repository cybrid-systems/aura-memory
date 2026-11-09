#!/usr/bin/env python3
"""#4946 aura-memory: held-out evaluation of a complementary policy set chosen by EoH-S.

Claim
  A single memory policy kept by the existing single-objective gate is not the best thing to deploy across a
  population of tenants/stream distributions: the worst distribution loses. A set of at most 3 policies,
  selected by std/proposer's EoH-S (prop:set-select) over per-stream scores, should raise the worst
  distribution's held-out score by >= 5% against the single best policy.

Method
  distributions  clean / recall80 / recall120: stream seeds are the tenant population; every other block of
                 P events is a recall block that asks about episodic notes 30..150 events old, so a short
                 episodic ttl looks free in a clean stream and loses here (P = 0 = clean)
  dev streams    seeds 0,1,2,3,4 per distribution (learning, candidate evaluation and selection)
  held-out       seeds 5,6,7,8,9 per distribution (never used above)
  candidates     the learner's own mutation vocabulary (aura_memory/policy_gen.py) + the final policy of one
                 adaptive (single-objective KEEP) run per dev stream
  search         aura/evo_select.aura: std/evo-core ask/tell + evo log, then prop:set-select (k=3)
  assignment     per distribution, the selected policy with the best mean dev score (a tenant's profile is
                 known from its own history, so this is deployable)

score = (correction-recall + (1 - stale-rate) + 30/(30+size)) / 3   (see aura_memory/eval.py);
  the report repeats the comparison for size weights 0, 1/3 and 1/2 so the verdict is not a weight choice.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aura_memory.agent import run                      # noqa: E402
from aura_memory.eval import eval_policy               # noqa: E402
from aura_memory.policy_gen import family, genome_id, source  # noqa: E402

DISTS = [
    {"id": "clean", "noise": 0.0, "p_correct": 0.7, "recall": 0},
    {"id": "recall80", "noise": 0.0, "p_correct": 0.7, "recall": 80},
    {"id": "recall120", "noise": 0.0, "p_correct": 0.7, "recall": 120},
]
DEV = [0, 1, 2, 3, 4]
HELDOUT = [5, 6, 7, 8, 9]
N = 600
K = 3


def load_json(p, default):
    if p.exists():
        return json.loads(p.read_text())
    return default


def save_json(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, indent=1, sort_keys=True) + "\n")


def cand_id(i):
    return "P%02d" % i



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", default="results/evo")
    args = ap.parse_args()
    out = ROOT / args.out
    pol = out / "policies"
    logs = out / "logs"
    pol.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    cache_eval = load_json(out / "cache_eval.json", {})
    cache_learn = load_json(out / "cache_learn.json", {})

    # candidates: the learner's closed grammar
    cands = []
    for i, g in enumerate(family()):
        cid = cand_id(i)
        p = pol / (cid + ".aura")
        p.write_text(source(g, i))
        cands.append({"id": cid, "file": str(p), "genome": genome_id(g), "note": g["note"], "kind": "grammar"})

    def ev(cand_file, dist, seed):
        key = "%s|%s|%d" % (Path(cand_file).stem, dist["id"], seed)
        if key not in cache_eval:
            cache_eval[key] = eval_policy(cand_file, seed, n=N, noise=dist["noise"],
                                          p_correct=dist["p_correct"], recall=dist["recall"])
        return cache_eval[key]

    # baseline learner: one adaptive (single-objective KEEP) run per dev stream
    print("== baseline: single-objective KEEP on dev streams", flush=True)
    for di, dist in enumerate(DISTS):
        for seed in DEV:
            key = "learn|%s|%d" % (dist["id"], seed)
            if key in cache_learn:
                continue
            log = logs / ("learn-%s-s%d.jsonl" % (dist["id"], seed))
            if log.exists():
                log.unlink()
            r = run("adaptive", seed, n=N, noise=dist["noise"], p_correct=dist["p_correct"],
                    recall=dist["recall"],
                    extra_env={"AURA_EVO_LOG": str(log), "AURA_EVO_RUN": "learn-%s-s%d" % (dist["id"], seed)})
            q = r["queries"]
            cache_learn[key] = {
                "mode": "adaptive", "seed": seed, "dist": dist["id"],
                "accuracy": sum(1 for x in q if x[3]) / max(1, len(q)),
                "stale_rate": sum(1 for x in q if x[4]) / max(1, len(q)),
                "size": r["sizes"][-1],
                "verdicts": [(v["ts"], v["verdict"], v["chosen"]) for v in r["verdicts"]],
                "source": r["policy"]["source"],
            }
            save_json(out / "cache_learn.json", cache_learn)
    seen = {}
    for dist in DISTS:
        for seed in DEV:
            src = cache_learn["learn|%s|%d" % (dist["id"], seed)]["source"]
            if src in seen:
                continue
            cid = "L%02d" % len(seen)
            p = pol / (cid + ".aura")
            p.write_text(src)
            seen[src] = {"id": cid, "file": str(p), "genome": "learned-%d" % abs(hash(src)),
                         "note": "learner KEEP (%s seed %d)" % (dist["id"], seed), "kind": "learned"}
    cands += list(seen.values())
    print("   %d candidates (%d learned)" % (len(cands), sum(1 for c in cands if c["kind"] == "learned")), flush=True)


    # dev matrix
    print("== dev evaluation (candidates x dev streams)", flush=True)
    jobs = [(c, d, s) for c in cands for d in DISTS for s in DEV]
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        vals = list(ex.map(lambda a: ev(a[0]["file"], a[1], a[2]), jobs))
    save_json(out / "cache_eval.json", cache_eval)
    rows = {}
    for (c, d, s), v in zip(jobs, vals):
        rows.setdefault((c["id"], d["id"]), []).append(v["score"])
    instances = ["%s-s%d" % (d["id"], s) for d in DISTS for s in DEV]
    matrix = {"k": K, "instances": instances, "candidates": []}
    for c in cands:
        r = [statistics.mean(rows[(c["id"], d["id"])]) for d in DISTS for s in DEV]
        matrix["candidates"].append({"id": c["id"], "genome": c["genome"], "note": c["note"], "rows": r})
    save_json(out / "matrix.json", matrix)

    # EoH-S selection through std/proposer + std/evo-core
    print("== EoH-S selection (aura/evo_select.aura)", flush=True)
    sel_log = logs / "select.jsonl"
    if sel_log.exists():
        sel_log.unlink()
    env = os.environ.copy()
    lib = os.environ.get("AURA_LIB")
    env["AURA_SANDBOX"] = "off"
    env["AURA_PIPELINE_STRICT"] = "0"
    if lib:
        env["AURA_PATH"] = lib + (":" + env["AURA_PATH"] if env.get("AURA_PATH") else "")
    env["MATRIX"] = str(out / "matrix.json")
    env["AURA_EVO_LOG"] = str(sel_log)
    env["AURA_EVO_RUN"] = "eohs-memory-set"
    aura = os.environ.get("AURA_BIN") or "aura"
    p = subprocess.run([aura, str(ROOT / "aura" / "evo_select.aura")], cwd=str(ROOT), env=env,
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        print(p.stdout[-3000:], p.stderr[-3000:])
        return 1
    sel = json.loads(p.stdout.strip().splitlines()[-1])
    save_json(out / "selection.json", sel)
    sel_cands = [c for c in cands if c["id"] in set(sel["selected"])]
    print("   selected %s coverage %.3f" % (sel["selected"], sel["coverage"]), flush=True)

    # per-distribution assignment and the single best policy
    devmean = {(c["id"], d["id"]): statistics.mean(rows[(c["id"], d["id"])]) for c in cands for d in DISTS}
    single = max(cands, key=lambda c: statistics.mean([devmean[(c["id"], d["id"])] for d in DISTS]))
    # Guard against picking a specialist on dev noise: a selected policy replaces the single best for a
    # distribution only if it beats it by more than 1 point on that distribution's dev streams.
    assign = {}
    for d in DISTS:
        best = max(sel_cands, key=lambda c: devmean[(c["id"], d["id"])])
        assign[d["id"]] = best["id"] if devmean[(best["id"], d["id"])] - devmean[(single["id"], d["id"])] > 0.01 \
            else single["id"]
    print("   single best %s (%s); assignment %s" % (single["id"], single["note"], assign), flush=True)


    # held-out
    print("== held-out evaluation", flush=True)
    # every candidate is evaluated held-out, so the report can also give the best possible per-tenant
    # choice from the whole 23-policy pool (an upper bound for any complementary set).
    need = {c["id"]: c for c in cands}
    jobs = [(c, d, s) for c in need.values() for d in DISTS for s in HELDOUT]
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        vals = list(ex.map(lambda a: ev(a[0]["file"], a[1], a[2]), jobs))
    save_json(out / "cache_eval.json", cache_eval)
    ho = {}
    for (c, d, s), v in zip(jobs, vals):
        ho[(c["id"], d["id"], s)] = v

    def mean_metric(cid, did, key):
        return statistics.mean([ho[(cid, did, s)][key] for s in HELDOUT])

    single_by = {d["id"]: mean_metric(single["id"], d["id"], "score") for d in DISTS}
    port_by = {d["id"]: mean_metric(assign[d["id"]], d["id"], "score") for d in DISTS}
    per_seed = {}
    for s in HELDOUT:
        per_seed[s] = {
            "single": {d["id"]: ho[(single["id"], d["id"], s)]["score"] for d in DISTS},
            "portfolio": {d["id"]: ho[(assign[d["id"]], d["id"], s)]["score"] for d in DISTS},
            "oracle": {d["id"]: max(ho[(c["id"], d["id"], s)]["score"] for c in sel_cands) for d in DISTS},
            "pool": {d["id"]: max(ho[(c["id"], d["id"], s)]["score"] for c in cands) for d in DISTS},
        }
        for k in ("single", "portfolio", "oracle", "pool"):
            per_seed[s][k]["worst"] = min(per_seed[s][k][d["id"]] for d in DISTS)

    single_worst = min(single_by.values())
    port_worst = min(port_by.values())
    # best fixed policy per distribution from the selected set (same rule as the deployed assignment, without
    # the 1-point guard): this is the set oracle a tenant could actually use
    oracle_by = {d["id"]: max(mean_metric(c["id"], d["id"], "score") for c in sel_cands) for d in DISTS}
    pool_oracle = {d["id"]: max(mean_metric(c["id"], d["id"], "score") for c in cands) for d in DISTS}
    try:
        aura_ver = subprocess.run([os.environ.get("AURA_BIN") or "aura", "--version"],
                                  capture_output=True, text=True).stdout.strip()
    except Exception:
        aura_ver = "?"

    # weight sensitivity: the acceptance must not depend on how much the size objective counts
    from aura_memory.eval import score_w
    sensitivity = {}
    for w in (0.0, 1.0 / 3.0, 0.5):
        def ho_mean(cid, did):
            return statistics.mean([score_w(ho[(cid, did, s)]["recall"], ho[(cid, did, s)]["stale_rate"],
                                            ho[(cid, did, s)]["size"], w) for s in HELDOUT])
        sw = min(ho_mean(single["id"], d["id"]) for d in DISTS)
        pw = min(ho_mean(assign[d["id"]], d["id"]) for d in DISTS)
        # best possible per-tenant choice from the whole pool: the upper bound for any set
        ow = min(max(ho_mean(c["id"], d["id"]) for c in cands) for d in DISTS)
        sensitivity["%.3f" % w] = {"single_worst": sw, "portfolio_worst": pw,
                                   "pool_oracle_worst": ow, "ratio": (pw / sw if sw else None),
                                   "pool_oracle_ratio": (ow / sw if sw else None),
                                   "pass": pw >= 1.05 * sw, "pool_oracle_pass": ow >= 1.05 * sw}
    result = {
        "aura": aura_ver,
        "n": N, "k": K, "dev_seeds": DEV, "heldout_seeds": HELDOUT,
        "candidates": [{"id": c["id"], "note": c["note"], "kind": c["kind"],
                        "dev_mean": statistics.mean([devmean[(c["id"], d["id"])] for d in DISTS])} for c in cands],
        "selection": sel,
        "single": {"id": single["id"], "note": single["note"],
                   "dev_mean": statistics.mean([devmean[(single["id"], d["id"])] for d in DISTS]),
                   "heldout_by_dist": single_by, "worst": single_worst},
        "portfolio": {"assign": assign, "heldout_by_dist": port_by, "worst": port_worst,
                      "oracle_by_dist": oracle_by, "oracle_worst": min(oracle_by.values()),
                      "pool_oracle_by_dist": pool_oracle, "pool_oracle_worst": min(pool_oracle.values())},
        "per_seed": per_seed,
        "acceptance": {"ratio": port_worst / single_worst if single_worst else None,
                        "pass": port_worst >= 1.05 * single_worst, "sensitivity": sensitivity},
        "metrics": {c["id"]: {d["id"]: {k: mean_metric(c["id"], d["id"], k)
                                       for k in ("score", "accuracy", "stale_rate", "recall", "size")}
                              for d in DISTS} for c in sel_cands},
        "single_metrics": {d["id"]: {k: mean_metric(single["id"], d["id"], k)
                                     for k in ("score", "accuracy", "stale_rate", "recall", "size")}
                           for d in DISTS},
    }
    save_json(out / "report.json", result)
    print(json.dumps({k: result[k] for k in ("single", "portfolio", "acceptance")}, indent=1))
    combined = out / "log.jsonl"
    with combined.open("w") as fh:
        for f in sorted(logs.glob("*.jsonl")):
            fh.write(f.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

