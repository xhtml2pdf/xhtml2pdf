#!/usr/bin/env python3
"""
Where the time goes when xhtml2pdf renders a document.

    python tools/perf/bench.py                      # the fixture corpus
    python tools/perf/bench.py --scaling            # the growth curve
    python tools/perf/bench.py --json before.json
    python tools/perf/bench.py --compare before.json

Reports the fastest of several renders, having thrown the first away. The
fastest rather than the mean or the median: every source of noise on a shared
machine -- another process taking the CPU, a garbage collection landing mid
render -- only ever makes a render slower, so the minimum is the closest thing
to the cost of the work itself. It is also what makes two runs comparable,
which is the whole point of --compare.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import corpus
import runner


def measure(doc, repeat: int) -> dict:
    runner.timed_render(doc)  # warm-up, discarded
    totals = []
    phases: dict[str, list[float]] = {}
    for _ in range(repeat):
        total, per_phase = runner.timed_render(doc)
        totals.append(total)
        for name, seconds in per_phase.items():
            phases.setdefault(name, []).append(seconds)
    fastest = totals.index(min(totals))
    return {
        "total_ms": totals[fastest] * 1000,
        # The phases of the fastest render, not the fastest of each phase:
        # those would be from different renders and need not add up to
        # anything.
        "phases_ms": {name: values[fastest] * 1000 for name, values in phases.items()},
    }


def _row(name, result, width) -> str:
    phases = result["phases_ms"]
    cells = " ".join(f"{phases.get(p, 0.0):>10.1f}" for p in runner.PHASES)
    return f"{name:<{width}} {result['total_ms']:>9.1f} {cells}"


def report(results: dict) -> None:
    width = max(len(name) for name in results) + 1
    header = " ".join(f"{p:>10}" for p in runner.PHASES)
    print(f"{'document':<{width}} {'total ms':>9} {header}")
    print("-" * (width + 10 + 11 * len(runner.PHASES)))
    for name, result in results.items():
        print(_row(name, result, width))


def report_counters(results: dict) -> None:
    width = max(len(name) for name in results) + 1
    header = " ".join(f"{c:>18}" for c in runner.COUNTERS)
    print(f"{'document':<{width}} {header}")
    print("-" * (width + 19 * len(runner.COUNTERS)))
    for name, counts in results.items():
        cells = " ".join(f"{counts.get(c, 0):>18,}" for c in runner.COUNTERS)
        print(f"{name:<{width}} {cells}")


def compare(results: dict, baseline: dict) -> None:
    width = max(len(name) for name in results) + 1
    print(f"{'document':<{width}} {'before':>10} {'after':>10} {'change':>10}")
    print("-" * (width + 33))
    for name, result in results.items():
        before = baseline.get(name)
        if before is None or "total_ms" not in before:
            print(f"{name:<{width}} {'-':>10} {result['total_ms']:>9.1f} {'new':>10}")
            continue
        after = result["total_ms"]
        change = (after - before["total_ms"]) / before["total_ms"] * 100
        print(
            f"{name:<{width}} {before['total_ms']:>9.1f} {after:>9.1f} {change:>+9.1f}%"
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "names", nargs="*", help="only fixtures whose file name contains one of these"
    )
    parser.add_argument(
        "--scaling",
        action="store_true",
        help="render the synthetic ladder instead of the fixtures",
    )
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument(
        "--counters",
        action="store_true",
        help="count units of work instead of timing them",
    )
    parser.add_argument("--json", type=Path, help="write the results here")
    parser.add_argument("--compare", type=Path, help="read a previous --json and diff")
    args = parser.parse_args(argv)

    docs = corpus.scaling() if args.scaling else corpus.fixtures(args.names)
    if not docs:
        print("nothing to render", file=sys.stderr)
        return 1

    if args.counters:
        results = {doc.name: runner.counted_render(doc) for doc in docs}
        report_counters(results)
    else:
        results = {doc.name: measure(doc, args.repeat) for doc in docs}
        report(results)

    if args.scaling and not args.counters:
        print()
        print(f"{'document':<26} {'ms/node':>9}")
        for doc, (nodes, _rules) in zip(docs, corpus.SCALING, strict=True):
            print(f"{doc.name:<26} {results[doc.name]['total_ms'] / nodes:>9.3f}")

    if args.compare:
        print()
        compare(results, json.loads(args.compare.read_text()))

    if args.json:
        args.json.write_text(json.dumps(results, indent=2, sort_keys=True))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
