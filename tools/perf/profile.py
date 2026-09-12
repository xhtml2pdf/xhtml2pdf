#!/usr/bin/env python3
"""
A cProfile run over one document of the corpus.

    python tools/perf/profile.py test-loremipsum
    python tools/perf/profile.py test-list --sort cumulative --lines 30

The CLI's own --profile flag (xhtml2pdf/pisa.py) profiles whatever document it
was pointed at, including the interpreter start-up and the first-render
caches. This warms up first, so what comes out is the steady-state cost.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import corpus
import runner


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="part of a fixture's file name")
    parser.add_argument("--sort", default="tottime", choices=("tottime", "cumulative"))
    parser.add_argument("--lines", type=int, default=25)
    parser.add_argument(
        "--only-ours", action="store_true", help="hide frames from outside xhtml2pdf"
    )
    args = parser.parse_args(argv)

    docs = corpus.fixtures([args.name])
    if not docs:
        print(f"no fixture matching {args.name!r}", file=sys.stderr)
        return 1
    doc = docs[0]

    runner.render(doc, runner._Sink())

    profiler = cProfile.Profile()
    profiler.enable()
    runner.render(doc, runner._Sink())
    profiler.disable()

    out = io.StringIO()
    stats = pstats.Stats(profiler, stream=out).sort_stats(args.sort)
    if args.only_ours:
        stats.print_stats("xhtml2pdf/xhtml2pdf", args.lines)
    else:
        stats.print_stats(args.lines)
    print(f"=== {doc.name}, sorted by {args.sort}\n")
    print(out.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
