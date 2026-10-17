"""Synthetic long-horizon user/assistant memory stream (seeded, offline).

Each event is what an extractor would hand the memory system: an offered write (key, value, category, source),
a pin, or a query whose correct answer is the *current* ground truth for that key. Ground truth only changes
through the user (pref / fact / episodic) or through teammates (project).

Phase A (first half): stable facts, preferences that drift slowly, chatter and assistant guesses that mention the
user's keys with wrong values (extraction errors), short-lived episodic notes.
Phase B (second half, distribution shift): preferences drift 3x faster, a new `project` category appears whose
updates arrive from teammates, and episodic volume doubles (memory-size pressure).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

PREF = {
    "user.theme": ["dark", "light", "solarized", "high-contrast"],
    "user.editor": ["vim", "emacs", "vscode", "helix", "zed"],
    "user.coffee": ["espresso", "latte", "americano", "flat-white", "none"],
    "user.lang": ["python", "rust", "go", "ocaml", "zig"],
    "user.meeting": ["morning", "noon", "afternoon", "never-friday"],
    "user.music": ["jazz", "lofi", "silence", "classical", "techno"],
}
FACT = {
    "user.hometown": ["Hangzhou", "Chengdu", "Xi'an", "Harbin", "Kunming", "Lhasa"],
    "user.birthday": ["03-14", "07-01", "11-30", "01-09", "05-20"],
    "user.employer": ["Cybrid", "Orbital", "Larch Labs", "Northwind"],
    "user.allergy": ["peanuts", "shellfish", "pollen", "none"],
    "user.pet": ["cat:Mochi", "dog:Doudou", "none", "parrot:Kiwi"],
}
PROJECT = {
    "proj.alpha.status": ["design", "build", "review", "blocked", "shipped"],
    "proj.alpha.owner": ["li", "wang", "zhao", "chen"],
    "proj.beta.deadline": ["W12", "W14", "W15", "W18", "W20"],
    "proj.beta.status": ["design", "build", "review", "blocked", "shipped"],
}
EP_SLOTS = ["mood", "lunch", "errand", "plan", "weather"]
EP_VALS = ["tired", "noodles", "pharmacy", "gym", "rain", "sunny", "dumplings", "bank", "focused", "meetings"]


@dataclass
class Event:
    ts: int
    kind: str           # OBS | PIN | QUERY
    key: str
    val: str = ""
    cat: str = ""
    src: str = ""
    truth: str = ""     # QUERY only: current ground truth
    stale: tuple = ()   # QUERY only: earlier truths of this key (an answer in here is a stale answer)
    phase: str = "A"


@dataclass
class World:
    truth: dict = field(default_factory=dict)
    history: dict = field(default_factory=dict)   # key -> earlier values
    cat: dict = field(default_factory=dict)
    ep_seen: list = field(default_factory=list)   # (ts, key)

    def set(self, k, v, cat):
        if k in self.truth and self.truth[k] != v:
            self.history.setdefault(k, []).append(self.truth[k])
        self.truth[k] = v
        self.cat[k] = cat


def _other(rng, pool, v):
    xs = [x for x in pool if x != v]
    return rng.choice(xs)


def stream(seed: int, n: int = 600, shift: float = 0.5) -> list[Event]:
    rng = random.Random(seed)
    w = World()
    out: list[Event] = []
    t_shift = int(n * shift)
    ep_n = 0
    other_n = 0
    # warm-up: the user introduces themselves (facts + preferences)
    intro = [(k, "fact", FACT) for k in FACT] + [(k, "pref", PREF) for k in PREF]
    rng.shuffle(intro)
    for k, cat, pool in intro:
        v = rng.choice(pool[k])
        w.set(k, v, cat)
        out.append(Event(len(out), "OBS", k, v, cat, "user"))
    while len(out) < n:
        ts = len(out)
        B = ts >= t_shift
        ph = "B" if B else "A"
        drift = 0.6 if B else 0.2
        # event mix
        mix = [("pref", 0.12), ("fact", 0.04), ("ep", 0.16 if B else 0.08), ("chatter", 0.12),
               ("assistant", 0.07), ("pin", 0.02), ("query", 0.30), ("proj", 0.10 if B else 0.0)]
        tot = sum(p for _, p in mix)
        r = rng.random() * tot
        for kind, p in mix:
            r -= p
            if r <= 0:
                break
        if kind == "pref":
            k = rng.choice(list(PREF))
            v = _other(rng, PREF[k], w.truth[k]) if rng.random() < drift else w.truth[k]
            w.set(k, v, "pref")
            out.append(Event(ts, "OBS", k, v, "pref", "user", phase=ph))
        elif kind == "fact":
            k = rng.choice(list(FACT))
            out.append(Event(ts, "OBS", k, w.truth[k], "fact", "user", phase=ph))
        elif kind == "ep":
            ep_n += 1
            k = f"ep.{ep_n}.{rng.choice(EP_SLOTS)}"
            v = rng.choice(EP_VALS)
            w.set(k, v, "episodic")
            w.ep_seen.append((ts, k))
            out.append(Event(ts, "OBS", k, v, "episodic", "user", phase=ph))
        elif kind == "chatter":
            if rng.random() < 0.5:     # extraction error: someone else's preference/fact attributed to the user
                if rng.random() < 0.5:
                    k = rng.choice(list(FACT)); cat = "fact"; pool = FACT
                else:
                    k = rng.choice(list(PREF)); cat = "pref"; pool = PREF
                out.append(Event(ts, "OBS", k, _other(rng, pool[k], w.truth[k]), cat, "chatter", phase=ph))
            else:                       # unrelated chatter about other people: never queried
                other_n += 1
                out.append(Event(ts, "OBS", f"other.{other_n}.{rng.choice(['coffee', 'city', 'pet'])}",
                                 rng.choice(EP_VALS), "episodic", "chatter", phase=ph))
        elif kind == "assistant":       # assistant's own inference about a preference, right half the time
            k = rng.choice(list(PREF))
            v = w.truth[k] if rng.random() < 0.5 else _other(rng, PREF[k], w.truth[k])
            out.append(Event(ts, "OBS", k, v, "pref", "assistant", phase=ph))
        elif kind == "pin":
            k = rng.choice(list(FACT) + list(PREF))
            out.append(Event(ts, "PIN", k, "", w.cat[k], "user", phase=ph))
        elif kind == "proj":
            k = rng.choice(list(PROJECT))
            cur = w.truth.get(k)
            v = rng.choice(PROJECT[k]) if cur is None else _other(rng, PROJECT[k], cur)
            w.set(k, v, "project")
            src = "user" if rng.random() < 0.1 else "teammate"
            out.append(Event(ts, "OBS", k, v, "project", src, phase=ph))
        else:   # query
            recent_ep = [k for (t, k) in w.ep_seen if ts - t <= 15]
            proj_known = [k for k in PROJECT if k in w.truth]
            choices = [("pref", 0.5), ("fact", 0.25), ("ep", 0.12 if recent_ep else 0.0),
                       ("proj", 0.3 if proj_known else 0.0)]
            tot = sum(p for _, p in choices)
            r = rng.random() * tot
            for qk, p in choices:
                r -= p
                if r <= 0:
                    break
            if qk == "pref":
                k = rng.choice(list(PREF))
            elif qk == "fact":
                k = rng.choice(list(FACT))
            elif qk == "ep":
                k = rng.choice(recent_ep)
            else:
                k = rng.choice(proj_known)
            out.append(Event(ts, "QUERY", k, "", w.cat[k], "", truth=w.truth[k],
                             stale=tuple(w.history.get(k, ())), phase=ph))
    return out
