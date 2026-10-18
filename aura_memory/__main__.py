"""aura-memory CLI.

  python3 -m aura_memory bench [--seeds 0 1 2 3 4] [--n 600] [--jobs 3] [--noise 0.0] [--out runs]
  python3 -m aura_memory run --mode adaptive --seed 0          # one stream, print every policy verdict
  python3 -m aura_memory inspect --seed 0 --upto 400           # white-box tour: list / get / edit / pin / delete / versions
  python3 -m aura_memory latency                               # in-process micro-benchmark (aura/closed_loop_bench.aura)
  python3 -m aura_memory acceptance                            # Aura issue repros + aura-memory's own rebind/rollback cycle
"""
from __future__ import annotations

import argparse
import os
import json
import subprocess
import sys

from . import acceptance
from .agent import MODES, run
from .bench import bench, report
from .control import ROOT, AuraMemory, aura_env
from .stream import stream


def cmd_inspect(a):
    m = AuraMemory(policy="seed", learn=True)
    try:
        for e in stream(a.seed, a.n)[: a.upto]:
            if e.kind == "OBS":
                r = m.obs(e.key, e.val, e.cat, e.src)
            elif e.kind == "PIN":
                r = m.pin_key(e.key, e.cat)
            else:
                r = m.query(e.key, e.cat)
                if r["answer"] != e.truth:
                    r = m.correct(e.key, e.truth, e.cat)
            if r.get("propose"):
                m.gate()
        st = m.stats()
        print(f"== STATS after {a.upto} events: size {st['size']}, by category {st['by_cat']}, policy v{st['version']}")
        items = m.list("pref")
        print(f"== LIST pref ({len(items)} items)")
        for it in items:
            print(f"   #{it['id']:<4} {it['key']:<14} = {it['val']:<12} src={it['src']:<10} tier={it['tier']} "
                  f"pinned={it['pinned']} hits={it['hits']} written-by={it['by']} under policy v{it['policy_version']}")
        key = a.key
        g = m.get(key)
        print(f"== GET {key}: {len(g['observations'])} observations, {len(g['provenance'])} provenance entries")
        for o in g["observations"][:6]:
            print(f"   obs t={o['ts']:<4} {o['val']:<12} from {o['src']:<10} -> {o['outcome']}")
        for p in g["provenance"][:6]:
            print(f"   prov t={p['ts']:<4} {p['op']:<13} {p['val']:<12} actor={p['actor']:<10} policy v{p['policy_version']}")
        if g["items"]:
            it = g["items"][0]
            print(f"== EDIT #{it['id']} -> 'edited-by-user'", m.edit(it["id"], "edited-by-user")["item"]["by"])
            print(f"== PIN  #{it['id']}", m.pin(it["id"])["item"]["pinned"])
            print(f"== DELETE #{it['id']}", m.delete(it["id"])["ok"], "| remaining for key:", len(m.get(key)["items"]))
        print("== VERSIONS (every policy mutation, kept or rolled back)")
        for v in m.versions():
            sc = " ".join(f"{s['correct']}/{s['labeled']}:{s['size']}" for s in v["scores"])
            print(f"   t={v['ts']:<4} {v['verdict']:<9} v{v['version']} chosen={v['chosen']} why='{v['why']}' "
                  f"[base, cand...] correct/labeled:size = {sc}  ({v['ms']} ms)")
        print("== POLICY (current workspace source)")
        print("  ", m.policy()["source"])
    finally:
        m.close()


def cmd_latency(a):
    aura, env = aura_env()
    env["N"] = str(a.n)
    p = subprocess.run([aura, str(ROOT / "aura" / "closed_loop_bench.aura")], cwd=str(ROOT), env=env,
                       capture_output=True, text=True, timeout=600)
    line = next((l for l in p.stdout.splitlines() if l.startswith("BENCH ")), None)
    if not line:
        print(p.stdout[-2000:], p.stderr[-2000:])
        return 1
    d = json.loads(line[6:])
    print(f"inside Aura (µs per op, current-time-ms clock, N={d.pop('n')})")
    for k, v in d.items():
        print(f"  {k:28s} {v:10.1f}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aura_memory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench")
    b.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    b.add_argument("--n", type=int, default=600)
    b.add_argument("--jobs", type=int, default=3)
    b.add_argument("--noise", type=float, default=0.0)
    b.add_argument("--recall", type=int, default=None, help="recall-regime block length in phase B (sets AURA_MEMORY_RECALL)")
    b.add_argument("--modes", nargs="+", default=list(MODES))
    b.add_argument("--out", default="runs")
    r = sub.add_parser("run")
    r.add_argument("--mode", default="adaptive", choices=MODES)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--n", type=int, default=600)
    r.add_argument("--noise", type=float, default=0.0)
    i = sub.add_parser("inspect")
    i.add_argument("--seed", type=int, default=0)
    i.add_argument("--n", type=int, default=600)
    i.add_argument("--upto", type=int, default=400)
    i.add_argument("--key", default="user.coffee")
    l = sub.add_parser("latency")
    l.add_argument("--n", type=int, default=100)
    sub.add_parser("acceptance")
    a = ap.parse_args(argv)
    if a.cmd == "bench":
        if a.recall is not None:
            os.environ["AURA_MEMORY_RECALL"] = str(a.recall)
        res = bench(a.modes, a.seeds, a.n, a.out, a.jobs, a.noise)
        print(report(res))
    elif a.cmd == "run":
        res = run(a.mode, a.seed, a.n, noise=a.noise)
        q = res["queries"]
        print(f"{a.mode} seed {a.seed}: accuracy {sum(x[3] for x in q) / len(q):.1%}, corrections {res['corrections']}, "
              f"final size {res['sizes'][-1]}")
        for v in res["verdicts"]:
            print(f"  t={v['ts']:<4} {v['verdict']:<9} {v['chosen']}  <- {v['why']}  candidates={v['candidates']}")
    elif a.cmd == "inspect":
        cmd_inspect(a)
    elif a.cmd == "latency":
        return cmd_latency(a)
    elif a.cmd == "acceptance":
        return acceptance.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
