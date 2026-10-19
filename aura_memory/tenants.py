"""Multi-tenant memory (R12): several users' streams interleaved through ONE Aura control plane.

Each tenant gets its own store, logs, learner state and policy workspace (`TENANT name` in server.aura: a child
workspace of the root, created from the seed policy). Switching tenants swaps the server's state vector and does
`workspace :switch` + `eval-current`. The differential check: every tenant's replies (answers, outcomes, sizes,
verdicts, version log, final policy) must equal a run of the same stream on a server of its own.

  python3 -m aura_memory tenants --seeds 0 1 2 3 --n 600 --order rr --check
"""
from __future__ import annotations

import json
import random
import time

from .agent import steps, run
from .control import AuraMemory

VOLATILE = {"ms", "snap"}          # wall-clock times and global snapshot ids differ between processes


class TenantView(AuraMemory):
    """AuraMemory interface for one tenant of a shared server; sends TENANT only when the tenant changes."""

    def __init__(self, shared: AuraMemory, name: str, learn: bool = True):
        self.shared, self.name, self.lat, self.startup_s, self.switch_s = shared, name, {}, shared.startup_s, []
        if not learn:
            self.call("LEARN", "0")

    def call(self, cmd, *fields, tag=None):
        if getattr(self.shared, "cur", "") != self.name:
            t0 = time.perf_counter()
            self.shared.call("TENANT", self.name, tag="TENANT")
            self.switch_s.append(time.perf_counter() - t0)
            self.shared.cur = self.name
        t0 = time.perf_counter()
        r = self.shared.call(cmd, *fields, tag=tag)
        self.lat.setdefault(tag or cmd, []).append(time.perf_counter() - t0)
        return r

    def close(self):
        pass


def rss_mb(pid: int) -> float:
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return -1.0


def run_tenants(mode: str, seeds, n: int = 600, noise: float = 0.0, order: str = "rr", block: int = 1,
                order_seed: int = 0) -> dict:
    """order rr: tenants take turns, `block` events each; random: a random live tenant runs `block` events."""
    policy = "append" if mode == "append" else "seed"
    learn = mode.startswith("adaptive")
    shared = AuraMemory(policy=policy, learn=True)
    shared.cur = ""
    views = {s: TenantView(shared, f"t{s}", learn) for s in seeds}
    gens = {s: steps(views[s], mode, s, n, noise) for s in seeds}
    res, rss, rng = {}, [], random.Random(order_seed)
    t0 = time.perf_counter()
    live = list(seeds)
    k, steps_done = 0, 0
    try:
        while live:
            s = live[k % len(live)] if order == "rr" else rng.choice(live)
            for _ in range(block):
                try:
                    next(gens[s])
                    steps_done += 1
                    if steps_done % 100 == 0:
                        rss.append(round(rss_mb(shared.p.pid)))
                except StopIteration as stop:
                    res[s] = stop.value
                    live.remove(s)
                    break
            else:
                k += 1
        wall = time.perf_counter() - t0
        info = shared.call("TENANTS")
    finally:
        shared.close()
    sw = [x for v in views.values() for x in v.switch_s]
    return {"mode": mode, "seeds": list(seeds), "n": n, "order": order, "block": block, "wall_s": wall,
            "results": res, "switches": len(sw), "switch_ms_p50": _pct(sw, 50) * 1e3, "switch_ms_p99": _pct(sw, 99) * 1e3,
            "rss_mb": rss, "server": info, "lat": shared.lat}


def _pct(xs, p):
    if not xs:
        return 0.0
    ys = sorted(xs)
    return ys[min(len(ys) - 1, int(len(ys) * p / 100))]


def strip(x):
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, (list, tuple)):
        return [strip(v) for v in x]
    return x


def diff(a: dict, b: dict) -> list[str]:
    """field-level differences between a tenant's result and its own-server reference"""
    out = []
    for f in ("queries", "corrections", "sizes", "verdicts", "versions"):
        x, y = strip(a[f]), strip(b[f])
        if x != y:
            if isinstance(x, list) and isinstance(y, list):
                i = next((i for i, (u, v) in enumerate(zip(x, y)) if u != v), min(len(x), len(y)))
                out.append(f"{f}[{i}]: {json.dumps(x[i] if i < len(x) else None)[:300]} != "
                           f"{json.dumps(y[i] if i < len(y) else None)[:300]}")
            else:
                out.append(f"{f}: {x} != {y}")
    if a["policy"].get("compiled") != b["policy"].get("compiled"):
        out.append("policy.compiled differs")
    if a["policy"].get("source") != b["policy"].get("source"):
        out.append("policy.source differs")
    return out


def check(mode: str, seeds, n: int, noise: float, multi: dict) -> dict:
    out, ref_s = {}, 0.0
    for s in seeds:
        t0 = time.perf_counter()
        ref = run(mode, s, n, noise=noise)
        ref_s += time.perf_counter() - t0
        out[s] = diff(multi["results"][s], ref)
    return {"diffs": out, "ref_wall_s": ref_s}
