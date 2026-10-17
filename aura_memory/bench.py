"""Benchmark: append-only vs fixed white-box vs adaptive (gated) vs adaptive (ungated) over the shifted stream."""
from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .agent import MODES, run


def _pct(xs, q):
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def run_one(mode: str, seed: int, n: int, outroot: str, noise: float = 0.0) -> dict:
    t0 = time.perf_counter()
    r = run(mode, seed, n, noise=noise)
    q = r["queries"]
    w = [[x for x in q if i * n // 3 <= x[0] < (i + 1) * n // 3] for i in range(3)]
    lat = r["lat"]
    gates = lat.get("GATE", []) + lat.get("APPLY", [])
    res = {
        "mode": mode, "seed": seed, "n": n, "noise": noise,
        "queries": len(q), "accuracy": sum(x[3] for x in q) / len(q),
        "window_accuracy": [sum(x[3] for x in ws) / max(1, len(ws)) for ws in w],
        "stale_rate": sum(x[4] for x in q) / len(q),
        "empty_rate": sum(x[5] for x in q) / len(q),
        "by_cat": {c: sum(x[3] for x in q if x[2] == c) / max(1, sum(1 for x in q if x[2] == c))
                   for c in ("pref", "fact", "project", "episodic")},
        "corrections": r["corrections"],
        "size_final": r["sizes"][-1], "size_mean": statistics.mean(r["sizes"]),
        "proposals": len(r["verdicts"]),
        "keep": sum(v["verdict"] == "KEEP" for v in r["verdicts"]),
        "rollback": sum(v["verdict"] == "ROLLBACK" for v in r["verdicts"]),
        "kept": [v["chosen"] for v in r["verdicts"] if v["verdict"] == "KEEP"],
        "query_us_p50": _pct(lat.get("QUERY", []), .5) * 1e6, "query_us_p99": _pct(lat.get("QUERY", []), .99) * 1e6,
        "write_us_p50": _pct(lat.get("WRITE", []), .5) * 1e6,
        "mutation_ms_p50": _pct(gates, .5) * 1e3, "mutation_ms_max": max(gates, default=0) * 1e3,
        "startup_ms": r["startup_s"] * 1e3,
        "wall_s": time.perf_counter() - t0,
    }
    out = Path(outroot) / f"{mode}-seed{seed}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(res, indent=1))
    (out / "verdicts.json").write_text(json.dumps(r["verdicts"], indent=1))
    (out / "policy_versions.json").write_text(json.dumps(r["versions"], indent=1))
    (out / "final_policy.aura").write_text(r["policy"]["source"] + "\n")
    return res


def _m(rs, k):
    return statistics.mean(r[k] for r in rs)


def table(results: list[dict]) -> str:
    rows = ["| mode | accuracy (mean, min–max) | window 1 / 2 / 3 | stale-answer rate | user corrections | "
            "memory size (final / mean) | proposals | KEEP / ROLLBACK |",
            "|---|---|---|---|---|---|---|---|"]
    for mode in MODES:
        rs = [r for r in results if r["mode"] == mode]
        if not rs:
            continue
        a = [r["accuracy"] for r in rs]
        w = [statistics.mean(r["window_accuracy"][i] for r in rs) for i in range(3)]
        rows.append(f"| {mode} | {statistics.mean(a):.1%} ({min(a):.1%}–{max(a):.1%}) | "
                    f"{w[0]:.1%} / {w[1]:.1%} / {w[2]:.1%} | {_m(rs, 'stale_rate'):.1%} | {_m(rs, 'corrections'):.1f} | "
                    f"{_m(rs, 'size_final'):.0f} / {_m(rs, 'size_mean'):.0f} | {_m(rs, 'proposals'):.1f} | "
                    f"{_m(rs, 'keep'):.1f} / {_m(rs, 'rollback'):.1f} |")
    return "\n".join(rows)


def cat_table(results: list[dict]) -> str:
    cats = ("pref", "fact", "project", "episodic")
    rows = ["| mode | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
    for mode in MODES:
        rs = [r for r in results if r["mode"] == mode]
        if rs:
            rows.append(f"| {mode} | " + " | ".join(f"{statistics.mean(r['by_cat'][c] for r in rs):.1%}" for c in cats) + " |")
    return "\n".join(rows)


def latency_table(results: list[dict]) -> str:
    rows = ["| mode | query µs p50 / p99 | write µs p50 | policy mutation ms p50 / max (GATE or APPLY) | startup ms | wall s |",
            "|---|---|---|---|---|---|"]
    for mode in MODES:
        rs = [r for r in results if r["mode"] == mode]
        if not rs:
            continue
        mut = (f"{_m(rs, 'mutation_ms_p50'):.0f} / {max(r['mutation_ms_max'] for r in rs):.0f}"
               if _m(rs, 'proposals') else "–")
        rows.append(f"| {mode} | {_m(rs, 'query_us_p50'):.0f} / {_m(rs, 'query_us_p99'):.0f} | {_m(rs, 'write_us_p50'):.0f} | "
                    f"{mut} | {_m(rs, 'startup_ms'):.0f} | {_m(rs, 'wall_s'):.0f} |")
    return "\n".join(rows)


def report(results: list[dict]) -> str:
    seeds = sorted({r["seed"] for r in results})
    n = results[0]["n"]
    noise = results[0]["noise"]
    return (f"seeds {seeds}, {n} events per stream (shift at {n // 2}), diagnosis noise {noise}\n\n"
            + table(results) + "\n\naccuracy by category\n\n" + cat_table(results)
            + "\n\nlatency (host round trip over pipes)\n\n" + latency_table(results) + "\n")


def bench(modes, seeds, n, outroot="runs", jobs=1, noise=0.0) -> list[dict]:
    Path(outroot).mkdir(parents=True, exist_ok=True)
    work = [(m, s, n, outroot, noise) for s in seeds for m in modes]
    if jobs > 1:
        with ProcessPoolExecutor(jobs) as ex:
            results = list(ex.map(run_one, *zip(*work)))
    else:
        results = [run_one(*w) for w in work]
    (Path(outroot) / "results.json").write_text(json.dumps(results, indent=1))
    (Path(outroot) / "results.md").write_text(report(results))
    return results
