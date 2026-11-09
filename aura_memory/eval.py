"""Evaluate one fixed memory policy on one stream (v0.2-evo #4946).

The learner (agent.steps) is off: the policy file is loaded, the stream runs, and every query is graded
against the stream's ground truth. The three #4946 objectives are measured here:

  correction-recall  after the user corrects a key, the share of later queries on that key that the policy
                     answers correctly (a policy that admits the correction but loses it to keep-first or a
                     ttl scores low). Corrections with no later query are skipped.
  stale-rate         share of queries answered with a value that used to be true (stream records it).
  size               final store size, in items.

score = (correction-recall + (1 - stale-rate) + size-term) / 3, size-term = 30 / (30 + size)
      a bounded, strictly decreasing size term: 15 items -> 0.67, 30 -> 0.50, 60 -> 0.33, 93 -> 0.24.
      Equal weight on the three objectives as #4946 lists them; the overall accuracy is reported next to
      it, not folded in again. The report also gives the weight sensitivity (size at 0 / 1/3 / correctness
      as a tie-break only).
"""
from __future__ import annotations

import random

from .control import AuraMemory
from .stream import stream


def size_term(size: int) -> float:
    return 30.0 / (30.0 + float(size))


def score_w(recall: float, stale: float, size: int, w: float = 1.0 / 3.0) -> float:
    """Correctness (correction-recall and freshness, half each) against the size term with weight w.
    w = 0 is correctness only; w = 1/3 is the pre-registered equal-weight score of #4946."""
    correctness = 0.5 * recall + 0.5 * (1.0 - stale)
    return (1.0 - w) * correctness + w * size_term(size)


def score(recall: float, stale: float, size: int) -> float:
    return score_w(recall, stale, size, 1.0 / 3.0)


def eval_policy(policy_path: str, seed: int, n: int = 600, noise: float = 0.0, p_correct: float = 0.7,
                shift: float = 0.5, recall: int = 0) -> dict:
    m = AuraMemory(policy=policy_path, learn=False)
    try:
        evs = stream(seed, n, shift=shift, recall=recall)
        q = []                 # (ts, key, phase, cat, ok, stale, empty)
        corrections = 0
        corrected = []         # (key, ts), one per user correction
        for e in evs:
            urng = random.Random(seed * 1_000_003 + e.ts)
            if e.kind == "OBS":
                m.obs(e.key, e.val, e.cat, e.src)
            elif e.kind == "PIN":
                m.pin_key(e.key, e.cat)
            else:
                r = m.query(e.key, e.cat)
                ans = r["answer"]
                ok = ans == e.truth
                q.append((e.ts, e.key, e.phase, e.cat, ok, (not ok) and ans in e.stale, ans == ""))
                if not ok and urng.random() < p_correct:
                    corrections += 1
                    corrected.append((e.key, e.ts))
                    m.correct(e.key, e.truth, e.cat, noisy=urng.random() < noise)
        size = m.stats()["size"]
    finally:
        m.close()

    # correction-recall: for each corrected key, the share of later queries on the same key that are
    # answered correctly. A correction with no later query is skipped (it carries no evidence).
    per_corr = []
    for key, t0 in corrected:
        later = [ok for (ts, k, _p, _c, ok, _s, _e) in q if k == key and ts > t0]
        if later:
            per_corr.append(sum(1 for x in later if x) / len(later))
    recall = sum(per_corr) / len(per_corr) if per_corr else 1.0

    stale = sum(1 for x in q if x[5]) / max(1, len(q))
    return {
        "seed": seed, "n": n, "noise": noise, "p_correct": p_correct, "shift": shift, "recall": recall,
        "queries": len(q), "accuracy": sum(1 for x in q if x[4]) / max(1, len(q)),
        "stale_rate": stale, "size": size, "corrections": corrections,
        "recall": recall, "score": score(recall, stale, size),
    }
