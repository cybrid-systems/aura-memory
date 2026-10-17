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
from .stream import stream

MODES = ("append", "fixed", "adaptive", "adaptive-nogate")


def run(mode: str, seed: int, n: int = 600, noise: float = 0.0, p_correct: float = 0.7,
        min_evidence: int = 2, window: int = 100) -> dict:
    policy = "append" if mode == "append" else "seed"
    learn = mode.startswith("adaptive")
    m = AuraMemory(policy=policy, learn=learn, min_evidence=min_evidence, window=window)
    evs = stream(seed, n)
    q = []          # per query: (ts, phase, cat, correct, stale, empty)
    corrections = 0
    sizes = []
    verdicts = []
    try:
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
                v = m.gate() if mode == "adaptive" else m.apply()
                verdicts.append({"ts": e.ts, "verdict": v["verdict"], "chosen": v.get("chosen"),
                                 "why": r["propose"]["why"], "candidates": r["propose"]["candidates"],
                                 "scores": v.get("scores")})
        final_policy = m.policy()
        versions = m.versions()
        lat = m.lat
        startup = m.startup_s
    finally:
        m.close()
    return {"mode": mode, "seed": seed, "n": n, "noise": noise, "queries": q, "corrections": corrections,
            "sizes": sizes, "verdicts": verdicts, "versions": versions, "policy": final_policy,
            "lat": lat, "startup_s": startup}
