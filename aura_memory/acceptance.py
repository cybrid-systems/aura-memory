"""Acceptance checks for the Aura build in AURA_BIN.

Each acceptance/<name>/repro.aura runs from its own directory; the last non-empty stdout line must equal expect.txt.
A check may instead name a repo program in program.txt (e.g. the real server), feed it stdin.txt, and pass when
stdout contains expect-contains.txt.
Issue repros (#4583 #4584 copied from aura-coder; #4585 #4586) FAIL while the issue is open on that build;
memory-cycle is aura-memory's own snapshot / rebind / restore shape and must PASS.
"""
from __future__ import annotations

import subprocess
import sys

from .control import ROOT, aura_env

CHECKS = {
    "memory-cycle": "aura-memory: snapshot, rebind 2 policy defines, restore -> byte-identical source; rebind + keep",
    "4583": "10 rebinds next to a self-recursive define stay flat (no 4x-per-rebind blow-up)",
    "4584": "2nd call of a workspace define whose sibling uses filter runs the right define",
    "4585": "a host-program loop is not >3x slower after one set-code",
    "4586": "an error inside a map callback reaches try",
    "4611": "the released server's (52c90f4) first GATE (18-event trace) replays and answers KEEP (c6a18e8a5: list-ref out of bounds)",
    "4611-current": "the R10 server (frozen) + 103-request recall-stream trace: the first GATE answers KEEP resolve pref latest (c6a18e8a5..39595edd4: list-ref out of bounds, so a bench worker waits forever for the reply)",
    "4629": "2000 (i \"episodic\") pairs built by a tail loop: no element's car is a non-number (c6a18e8a5..39595edd4: 18 elements become self-referential); the store/index/replay build shape",
    "4625": "a frozen server (sweep-cat fold with set!) + 102-event trace: GET e10 keeps its provenance (c6a18e8a5: index bucket becomes a self-referential cons, provenance lost)",
}


def run_check(name: str) -> tuple[bool, str]:
    d = ROOT / "acceptance" / name
    aura, env = aura_env()
    if (d / "lib").exists():
        env["AURA_PATH"] = str(d / "lib") + ":" + env.get("AURA_PATH", "")
    prog = (d / "program.txt").read_text().strip() if (d / "program.txt").exists() else "repro.aura"
    stdin = (d / "stdin.txt").read_text() if (d / "stdin.txt").exists() else None
    env["AURA_MEMORY_POLICY"] = str(ROOT / "aura" / "policy_seed.aura")
    try:
        p = subprocess.run([aura, prog], cwd=str(d), env=env, input=stdin, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    if (d / "expect-contains.txt").exists():
        needle = (d / "expect-contains.txt").read_text().strip()
        hit = [l for l in p.stdout.splitlines() if needle in l]
        errs = [l for l in p.stderr.splitlines() + p.stdout.splitlines() if l.startswith("error")]
        return bool(hit), (hit[0][:160] if hit else (errs[0][:160] if errs else f"(no match, rc={p.returncode})"))
    lines = [l for l in p.stdout.splitlines() if l.strip() and not l.startswith("⚠")]
    got = lines[-1].strip() if lines else f"(no output, rc={p.returncode}) {p.stderr[-200:]}"
    return got == (d / "expect.txt").read_text().strip(), got


def main() -> int:
    own_bad = 0
    for name, what in CHECKS.items():
        ok, got = run_check(name)
        if name == "memory-cycle" and not ok:
            own_bad = 1
        print(f"{'PASS' if ok else 'FAIL'}  {name:13s} {what}\n      got: {got}")
    return own_bad


if __name__ == "__main__":
    sys.exit(main())
