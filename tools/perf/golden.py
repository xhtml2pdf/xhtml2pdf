#!/usr/bin/env python3
"""
Proof that a change to the pipeline did not change what comes out of it.

    python tools/perf/golden.py --update     # before touching anything
    python tools/perf/golden.py              # after each step

reportlab renders repeatably once rl_config.invariant is set (runner.py sets
it), so two renders of the same document from the same code are identical
byte for byte. That makes a hash a complete test: it catches a cascade that
resolved one property differently on one element of one fixture, which a
rasterised comparison would round away.

A hash that changes is not automatically a bug -- some changes are meant to
change the output -- but it does mean nobody gets to assume otherwise.

Repeatable only within one hash seed: a rendered PDF still carries a name
derived from a memory address (see the note in README.md), so two processes
with different PYTHONHASHSEED lay objects out differently and produce
different bytes. This re-executes itself with the seed pinned rather than
quietly comparing hashes that were never going to match.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

if os.environ.get("PYTHONHASHSEED") != "0":
    os.execve(
        sys.executable,
        [sys.executable, *sys.argv],
        {**os.environ, "PYTHONHASHSEED": "0"},
    )

sys.path.insert(0, str(Path(__file__).resolve().parent))

import corpus
import runner

HASHES = Path(__file__).resolve().parent / "golden.json"


def digests() -> dict[str, str]:
    return {
        doc.name: hashlib.sha256(runner.render_bytes(doc)).hexdigest()
        for doc in corpus.fixtures()
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="record the current output as the reference",
    )
    args = parser.parse_args(argv)

    current = digests()

    if args.update:
        HASHES.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"recorded {len(current)} hashes in {HASHES}")
        return 0

    if not HASHES.exists():
        print("no reference yet -- run with --update first", file=sys.stderr)
        return 1

    reference = json.loads(HASHES.read_text())
    changed = [
        name
        for name, digest in current.items()
        if reference.get(name) not in {None, digest}
    ]
    missing = sorted(set(reference) - set(current))
    added = sorted(set(current) - set(reference))

    for name in changed:
        print(f"CHANGED  {name}")
    for name in missing:
        print(f"MISSING  {name}")
    for name in added:
        print(f"NEW      {name}")

    if changed or missing:
        print(f"\n{len(changed)} of {len(current)} documents render differently")
        return 1
    print(f"{len(current)} documents render byte for byte as before")
    return 0


if __name__ == "__main__":
    sys.exit(main())
