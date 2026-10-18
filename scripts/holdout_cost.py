"""Held-out gate cost at scale: fill N never-read episodic items (learning off), then 200 events where episodic notes
are read back ~10 events later, then 80 where they are not, then gate an overfit candidate (ttl episodic 5, added with
ADDCAND next to the learner's own) for each AURA_MEMORY_HOLDOUT in --ks. Each run is a fresh process.
  python3 scripts/holdout_cost.py --n 20000 --ks 0 1 2 4 --out results/scale/r8/holdout-cost-20000.json
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aura_memory.control import AuraMemory  # noqa: E402


def rss_mb(pid):
    for line in open(f"/proc/{pid}/status"):
        if line.startswith("VmRSS:"): return round(int(line.split()[1]) / 1024, 1)


def one(n, k):
    os.environ["AURA_MEMORY_HOLDOUT"] = str(k)
    m = AuraMemory(policy="seed", learn=False, min_evidence=1)
    try:
        for i in range(n): m.obs(f"e{i}", f"v{i}", "episodic", "user")
        m.call("LEARN", "1")
        m.obs("user.home", "oslo", "fact", "user")
        for i in range(20):
            m.obs(f"ep.{i}", f"note{i}", "episodic", "user")
            for _ in range(9): m.query("user.home", "fact")
            m.query(f"ep.{i}", "episodic")
        for i in range(20, 60):
            m.obs(f"ep.{i}", f"note{i}", "episodic", "user")
            m.query("user.home", "fact"); m.query("user.home", "fact")
        m.obs("user.theme", "dark", "pref", "user"); m.obs("user.theme", "light", "pref", "chatter")
        m.query("user.theme", "pref"); m.correct("user.theme", "light", "pref")
        m.call("ADDCAND", "ttl", "episodic", "5", "overfit")
        r0 = rss_mb(m.p.pid); t = time.perf_counter(); v = m.gate(); ms = round(1000 * (time.perf_counter() - t), 1)
        return {"n": n, "k": k, "gate_ms": ms, "verdict": v["verdict"], "chosen": v["chosen"], "scores": v["scores"],
                "rss_before_mb": r0, "rss_after_mb": rss_mb(m.p.pid), "size_after": m.stats()["size"]}
    finally:
        m.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--ks", type=int, nargs="+", default=[0, 1, 2, 4])
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rs = []
    for k in a.ks:
        rs.append(one(a.n, k)); print(json.dumps({x: rs[-1][x] for x in ("n", "k", "gate_ms", "verdict", "chosen", "rss_before_mb", "rss_after_mb", "size_after")}), flush=True)
    if a.out: Path(a.out).write_text(json.dumps(rs, indent=1))


if __name__ == "__main__":
    main()
