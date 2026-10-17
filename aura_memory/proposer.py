"""Optional external proposer hook (e.g. an LLM). Offline and inert by default; no numbers in the README use it.

The Aura learner already proposes candidates from provenance (server.aura `diagnose`). An external proposer can add
more candidates to a pending proposal with ADDCAND, but only in the same closed grammar the learner uses
(admit/resolve/ttl/promote on a known category). Each one is still compiled by server.aura, trialled in its own
worldline by the gate, and kept only if it beats the current policy on the replay window. Free-form code from a
model never reaches mutate:rebind.
"""
from __future__ import annotations

import json
import os
import urllib.request


class Proposer:
    def propose(self, why: str, candidates: list[str], policy_source: str) -> list[list[str]]:
        return []


class LLMProposer(Proposer):
    """OpenAI-compatible chat endpoint from AURA_MEMORY_LLM_URL / AURA_MEMORY_LLM_KEY / AURA_MEMORY_LLM_MODEL."""

    def __init__(self):
        self.url = os.environ["AURA_MEMORY_LLM_URL"]
        self.key = os.environ.get("AURA_MEMORY_LLM_KEY", "")
        self.model = os.environ.get("AURA_MEMORY_LLM_MODEL", "default")

    def propose(self, why, candidates, policy_source):
        prompt = ("You tune a memory-management policy. Reply with a JSON list of at most 2 candidates, each "
                  '["admit", cat, src, "0"|"1"] or ["resolve", cat, "latest"|"keep-first"|"keep-both"] or '
                  '["ttl", cat, events] or ["promote", cat, hits]; cat in pref|fact|project|episodic.\n'
                  f"Diagnosis: {why}\nLearner candidates: {candidates}\nCurrent policy:\n{policy_source}")
        req = urllib.request.Request(self.url, data=json.dumps({
            "model": self.model, "messages": [{"role": "user", "content": prompt}]}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            text = json.load(r)["choices"][0]["message"]["content"]
        try:
            out = json.loads(text[text.index("["):text.rindex("]") + 1])
            return [[str(x) for x in c] for c in out if isinstance(c, list)][:2]
        except ValueError:
            return []


def get_proposer() -> Proposer:
    return LLMProposer() if os.environ.get("AURA_MEMORY_LLM_URL") else Proposer()
