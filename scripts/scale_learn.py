"""Learning at scale: does the learner / gate / forgetting machinery stay cheap when memory is big?

Fill N never-retrieved episodic items with learning off, then turn learning on and run --events of live traffic
(writes + queries on a small hot set, plus occasional reads of old items). The size check proposes a ttl for
episodic, the gate replays the window for each candidate, and once a ttl is kept the store sweeps expired items.
Reports per-block EV p50 / p99 / max, every GATE (ms, verdict, size), and the cost of STATS / LIST / GET at the end.
--old-every 0 drops the reads of old items, so a short ttl wins the gate and the live store bulk-expires most items.
  python3 scripts/scale_learn.py --n 4000 --events 600 --out runs/scale_learn.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aura_memory.control import AuraMemory  # noqa: E402


def rss_mb(pid: int) -> float:
    for line in open(f"/proc/{pid}/status"):
        if line.startswith("VmRSS:"):
            return round(int(line.split()[1]) / 1024, 1)
    return -1.0


def pct(xs, p):
    xs = sorted(xs)
    return round(1000 * xs[min(len(xs) - 1, int(p * len(xs)))], 2) if xs else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--events", type=int, default=600)
    ap.add_argument("--block", type=int, default=100)
    ap.add_argument("--hot", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--old-every", type=int, default=7, help="read an old episodic item every k-th event (0 = never: a ttl wins)")
    ap.add_argument("--out", default="runs/scale_learn.json")
    a = ap.parse_args()
    r = random.Random(a.seed)
    m = AuraMemory(policy="seed", learn=False)
    t0 = time.perf_counter()
    for i in range(1, a.n + 1):
        m.obs(f"e{i}", f"v{i}", "episodic", "user")
    fill_s = time.perf_counter() - t0
    m.call("LEARN", "1")
    rows, gates, ev = [], [], []
    t0 = time.perf_counter()
    for i in range(1, a.events + 1):
        h = r.randrange(a.hot)
        t = time.perf_counter()
        if i % 3 == 0:
            res = m.query(f"h{h}", "pref")
        elif a.old_every and i % a.old_every == 0:
            res = m.query(f"e{r.randint(1, a.n)}", "episodic")
        else:
            res = m.obs(f"h{h}", f"x{i}", "pref", "user")
        ev.append(time.perf_counter() - t)
        if res.get("propose"):
            t = time.perf_counter(); g = m.gate(); gms = time.perf_counter() - t
            gates.append({"event": i, "ms": round(1000 * gms, 1), "verdict": g["verdict"], "chosen": g.get("chosen"),
                          "scores": g.get("scores"), "size_before": res["size"]})
            print("  GATE", json.dumps(gates[-1]), flush=True)
        if i % a.block == 0:
            row = {"event": i, "size": res["size"], "ev_ms_p50": pct(ev, 0.5), "ev_ms_p99": pct(ev, 0.99),
                   "ev_ms_max": pct(ev, 1.0), "rss_mb": rss_mb(m.p.pid), "wall_s": round(time.perf_counter() - t0, 1)}
            rows.append(row); print(json.dumps(row), flush=True); ev = []
    final_stats = m.stats()
    probes = {k: m.get(k) for k in ("e1", "e2", f"e{a.n // 2}", f"e{a.n}", "h1")}
    ops = {}
    for name, f in (("STATS", m.stats), ("LIST", lambda: m.list("")), ("LIST_cat", lambda: m.list("pref")),
                    ("GET", lambda: m.get("h1"))):
        t = time.perf_counter(); f(); ops[name] = round(1000 * (time.perf_counter() - t), 1)
    print("ops ms", ops)
    m.close()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"n": a.n, "events": a.events, "fill_s": round(fill_s, 1), "rows": rows,
                                       "gates": gates, "ops_ms": ops,
                                       "old_every": a.old_every, "final_stats": final_stats, "probes": probes}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
