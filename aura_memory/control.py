"""Host side of the Aura control plane: a long-lived `aura aura/server.aura` process spoken to over pipes.

The memory store, the memory-management policy, the learner and the replay gate all run inside that Aura process;
this module frames requests and times round trips (adapted from aura-coder's control.py).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACE = os.environ.get("AURA_MEMORY_TRACE")    # append every request line to this file (debug / repro)
POLICIES = {"seed": ROOT / "aura" / "policy_seed.aura", "append": ROOT / "aura" / "policy_append.aura"}


def aura_env() -> tuple[str, dict]:
    aura = os.environ.get("AURA_BIN") or "aura"
    env = os.environ.copy()
    lib = os.environ.get("AURA_LIB")
    if lib:
        env["AURA_PATH"] = lib + (":" + env["AURA_PATH"] if env.get("AURA_PATH") else "")
    # set-code / mutate:rebind from a local program still need the sandbox off: cybrid-systems/aura#4575
    env.setdefault("AURA_SANDBOX", "off")
    env.setdefault("AURA_PIPELINE_STRICT", "0")
    return aura, env


def _clean(s) -> str:
    return str(s).replace("\t", " ").replace("\n", " ")


class AuraMemory:
    def __init__(self, policy: str = "seed", learn: bool = True, min_evidence: int = 2, window: int = 100):
        aura, env = aura_env()
        env["AURA_MEMORY_POLICY"] = str(POLICIES[policy])
        env["AURA_MEMORY_MIN_EVIDENCE"] = str(min_evidence)
        env["AURA_MEMORY_WINDOW"] = str(window)
        t0 = time.perf_counter()
        self.p = subprocess.Popen([aura, str(ROOT / "aura" / "server.aura")], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
                                  env=env, cwd=str(ROOT))
        ready = self._read()
        self.startup_s = time.perf_counter() - t0
        if not ready.get("ready"):
            raise RuntimeError(f"aura control plane failed to start: {ready}")
        self.lat: dict[str, list[float]] = {}
        if not learn:
            self.call("LEARN", "0")

    def _read(self) -> dict:
        while True:
            line = self.p.stdout.readline()
            if not line:
                err = self.p.stderr.read()[-2000:] if self.p.stderr else ""
                raise RuntimeError(f"aura control plane exited (rc={self.p.poll()}): {err}")
            if line.startswith("R "):
                return json.loads(line[2:])

    def call(self, cmd: str, *fields, tag: str | None = None) -> dict:
        line = "\t".join([cmd, *[_clean(f) for f in fields]]) + "\n"
        if TRACE:
            with open(TRACE, "a") as fh:
                fh.write(line)
        t0 = time.perf_counter()
        self.p.stdin.write(line)
        self.p.stdin.flush()
        r = self._read()
        self.lat.setdefault(tag or cmd, []).append(time.perf_counter() - t0)
        if "error" in r:
            raise RuntimeError(f"aura control plane: {r['error']}")
        return r

    # stream events
    def obs(self, key, val, cat, src):
        return self.call("EV", "OBS", key, val, cat, src, "0", tag="WRITE")

    def correct(self, key, val, cat, noisy: bool = False):
        return self.call("EV", "CORRECT", key, val, cat, "correction", "1" if noisy else "0", tag="CORRECT")

    def pin_key(self, key, cat):
        return self.call("EV", "PIN", key, "", cat, "user", "0", tag="PINKEY")

    def query(self, key, cat):
        return self.call("EV", "QUERY", key, "", cat, "", "0", tag="QUERY")

    # learner verdicts
    def gate(self):
        return self.call("GATE", tag="GATE")

    def apply(self):
        return self.call("APPLY", tag="APPLY")

    # white-box ops
    def list(self, cat: str = ""):
        return self.call("LIST", cat)["items"]

    def get(self, key):
        return self.call("GET", key)

    def edit(self, item_id, val):
        return self.call("EDIT", item_id, val)

    def delete(self, item_id):
        return self.call("DELETE", item_id)

    def pin(self, item_id):
        return self.call("PIN", item_id)

    def unpin(self, item_id):
        return self.call("UNPIN", item_id)

    def policy(self):
        return self.call("POLICY")

    def versions(self):
        return self.call("VERSIONS")["versions"]

    def stats(self):
        return self.call("STATS")

    def close(self):
        try:
            self.p.stdin.write("QUIT\n")
            self.p.stdin.flush()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()
