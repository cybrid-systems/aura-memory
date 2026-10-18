"""Store-size scaling: write N distinct facts (each followed by a query on a random existing key) into one Aura
control-plane process and report per-block p50 write / query latency and RSS. Learning is off and ttl is 0, so the
store grows to N items; this isolates how the store representation and Aura scale with memory size.
--steady M then issues M more queries against the fixed-size store, so RSS growth there is per-request, not per-item.
  python3 scripts/scale.py --n 20000 --block 2000 --steady 20000 --out runs/scale.json
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--block", type=int, default=2000)
    ap.add_argument("--out", default="runs/scale.json")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--steady", type=int, default=0, help="extra queries on the fixed-size store")
    a = ap.parse_args()
    r = random.Random(a.seed)
    m = AuraMemory(policy="seed", learn=False)
    rows, w, q = [], [], []
    t0 = time.perf_counter()
    for i in range(1, a.n + 1):
        t = time.perf_counter(); m.obs(f"k{i}", f"v{i}", "fact", "user"); w.append(time.perf_counter() - t)
        k = r.randint(1, i)
        t = time.perf_counter(); res = m.query(f"k{k}", "fact"); q.append(time.perf_counter() - t)
        assert res.get("answer") == f"v{k}", (k, res)
        if i % a.block == 0:
            st = m.stats()
            row = {"items": st["size"], "write_ms_p50": round(1000 * statistics.median(w), 3),
                   "query_ms_p50": round(1000 * statistics.median(q), 3), "rss_mb": rss_mb(m.p.pid),
                   "wall_s": round(time.perf_counter() - t0, 1), "events": st["events"], "provenance": st["provenance"]}
            rows.append(row); print(json.dumps(row), flush=True)
            w, q = [], []
    steady = []
    for j in range(1, a.steady + 1):
        k = r.randint(1, a.n)
        t = time.perf_counter(); res = m.query(f"k{k}", "fact"); q.append(time.perf_counter() - t)
        assert res.get("answer") == f"v{k}", (k, res)
        if j % a.block == 0:
            row = {"steady_queries": j, "items": a.n, "query_ms_p50": round(1000 * statistics.median(q), 3),
                   "rss_mb": rss_mb(m.p.pid), "wall_s": round(time.perf_counter() - t0, 1)}
            steady.append(row); print(json.dumps(row), flush=True)
            q = []
    m.close()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"n": a.n, "rows": rows, "steady": steady}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
