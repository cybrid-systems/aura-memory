"""One run over the stream: the assistant answers queries from memory, the user sometimes corrects wrong answers,
and (adaptive modes) the Aura learner mutates the memory-management policy, gated by worldline replay.

modes:
  append          RAG-style append-only memory (keep everything, newest mention wins); no learning
  fixed           PilotDeck-like fixed white-box policy (policy_seed.aura) + user corrections; no learning
  adaptive        seed policy + learner + multi-worldline replay gate (KEEP or ast:restore rollback)
  adaptive-nogate seed policy + learner, every proposal kept
"""
from __future__ import annotations

import random

from .control import AuraMemory
from .proposer import get_proposer
from .stream import stream

MODES = ("append", "fixed", "adaptive", "adaptive-nogate")


def run(mode: str, seed: int, n: int = 600, noise: float = 0.0, p_correct: float = 0.7,
        min_evidence: int = 2, window: int = 100) -> dict:
    policy = "append" if mode == "append" else "seed"
    m = AuraMemory(policy=policy, learn=mode.startswith("adaptive"), min_evidence=min_evidence, window=window)
    try:
        g = steps(m, mode, seed, n, noise, p_correct)
        while True:
            try:
                next(g)
            except StopIteration as stop:
                return stop.value
    finally:
        m.close()


def steps(m, mode: str, seed: int, n: int = 600, noise: float = 0.0, p_correct: float = 0.7):
    """One stream against memory `m` (an AuraMemory, or a tenant view of a shared one); yields after each event and
    returns the run's result. Several of these interleave in `tenants.run_tenants`."""
    proposer = get_proposer()
    evs = stream(seed, n)
    q = []          # per query: (ts, phase, cat, correct, stale, empty)
    corrections = 0
    sizes = []
    verdicts = []
    for e in evs:
        # user behaviour must not depend on the mode's RNG state: one RNG per (seed, event)
        urng = random.Random(seed * 1_000_003 + e.ts)
        if e.kind == "OBS":
            r = m.obs(e.key, e.val, e.cat, e.src)
        elif e.kind == "PIN":
            r = m.pin_key(e.key, e.cat)
        else:
            r = m.query(e.key, e.cat)
            ans = r["answer"]
            ok = ans == e.truth
            q.append((e.ts, e.phase, e.cat, ok, (not ok) and ans in e.stale, ans == ""))
            if not ok and urng.random() < p_correct:
                corrections += 1
                r = m.correct(e.key, e.truth, e.cat, noisy=urng.random() < noise)
        sizes.append(r["size"])
        if r.get("propose"):
            src = m.policy()["source"] if type(proposer).__name__ != "Proposer" else ""
            for c in proposer.propose(r["propose"]["why"], r["propose"]["candidates"], src):
                m.call("ADDCAND", *c)
            v = m.gate() if mode == "adaptive" else m.apply()
            verdicts.append({"ts": e.ts, "verdict": v["verdict"], "chosen": v.get("chosen"),
                             "why": r["propose"]["why"], "candidates": r["propose"]["candidates"],
                             "scores": v.get("scores")})
        yield e
    final_policy = m.policy()
    versions = m.versions()
    return {"mode": mode, "seed": seed, "n": n, "noise": noise, "queries": q, "corrections": corrections,
            "sizes": sizes, "verdicts": verdicts, "versions": versions, "policy": final_policy,
            "lat": m.lat, "startup_s": m.startup_s}
