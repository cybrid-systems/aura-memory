#!/usr/bin/env python3
"""Render results/evo/report.json as results/evo/summary.md (tables only, no prose)."""
import json
import statistics
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
r = json.loads((root / "results/evo/report.json").read_text())
D = ["clean", "recall80", "recall120"]
L = []
w = L.append
w("# #4946 aura-memory: EoH-S policy set (machine summary)\n")
w("aura: %s | n=%d | dev seeds %s | held-out seeds %s | k=%d\n" %
  (r["aura"], r["n"], r["dev_seeds"], r["heldout_seeds"], r["k"]))
w("selected: %s (coverage %.3f)" % (r["selection"]["selected"], r["selection"]["coverage"]))
w("assignment: %s" % r["portfolio"]["assign"])
w("single best: %s (%s)" % (r["single"]["id"], r["single"]["note"]))
w("acceptance: ratio %.4f, pass %s\n" % (r["acceptance"]["ratio"], r["acceptance"]["pass"]))
w("## Held-out means per distribution\n")
w("| policy | " + " | ".join(D) + " | worst |")
w("|---|" + "---:|" * (len(D) + 1))
w("| single best %s | %s | %.4f |" % (r["single"]["id"],
    " | ".join("%.4f" % r["single"]["heldout_by_dist"][d] for d in D), r["single"]["worst"]))
w("| portfolio | %s | %.4f |" % (
    " | ".join("%.4f" % r["portfolio"]["heldout_by_dist"][d] for d in D), r["portfolio"]["worst"]))
w("| set oracle | %s | %.4f |" % (
    " | ".join("%.4f" % r["portfolio"]["oracle_by_dist"][d] for d in D), r["portfolio"]["oracle_worst"]))
w("| pool oracle (all %d policies) | %s | %.4f |\n" % (
    len(r["candidates"]), 
    " | ".join("%.4f" % r["portfolio"]["pool_oracle_by_dist"][d] for d in D), r["portfolio"]["pool_oracle_worst"]))
w("## Per held-out seed (score; worst = min over distributions)\n")
w("| seed | single clean/recall80/recall120 | worst | portfolio clean/recall80/recall120 | worst | delta worst |")
w("|---|---|---:|---|---|---:|")
for s in r["heldout_seeds"]:
    p = r["per_seed"][str(s)]
    w("| %d | %s | %.4f | %s | %.4f | %+.4f |" % (
        s, " / ".join("%.3f" % p["single"][d] for d in D), p["single"]["worst"],
        " / ".join("%.3f" % p["portfolio"][d] for d in D), p["portfolio"]["worst"],
        p["portfolio"]["worst"] - p["single"]["worst"]))
w("\n## Score-weight sensitivity (size objective weight)\n")
w("| size weight | single worst | portfolio worst | pool oracle worst | portfolio ratio | passes 5% |")
w("|---:|---:|---:|---:|---:|---|")
for k, v in sorted(r["acceptance"]["sensitivity"].items()):
    w("| %s | %.4f | %.4f | %.4f | %.4f | %s |" % (k, v["single_worst"], v["portfolio_worst"],
        v["pool_oracle_worst"], v["ratio"], v["pass"]))
w("\n## Selected policies, held-out metrics\n")
w("| policy | dist | score | accuracy | correction-recall | stale | size |")
w("|---|---|---:|---:|---:|---:|---:|")
for cid, m in sorted(r["metrics"].items()):
    for d in D:
        v = m[d]
        w("| %s | %s | %.4f | %.4f | %.4f | %.4f | %.1f |" % (
            cid, d, v["score"], v["accuracy"], v["recall"], v["stale_rate"], v["size"]))
w("\n## Single best, held-out metrics\n")
w("| dist | score | accuracy | correction-recall | stale | size |")
w("|---|---:|---:|---:|---:|---:|")
for d in D:
    v = r["single_metrics"][d]
    w("| %s | %.4f | %.4f | %.4f | %.4f | %.1f |" % (
        d, v["score"], v["accuracy"], v["recall"], v["stale_rate"], v["size"]))
(root / "results/evo/summary.md").write_text("\n".join(L) + "\n")
print("wrote results/evo/summary.md")
