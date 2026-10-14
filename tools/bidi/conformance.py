"""
Run the Unicode bidi conformance suites against xhtml2pdf.bidi.

    python tools/bidi/conformance.py [UCD_DIR]

BidiTest.txt gives sequences of bidi classes; BidiCharacterTest.txt gives
real text, which is what exercises bracket pairing (rule N0). Both list the
expected levels and visual order of every case. UCD_DIR holds the two
files; without it they are downloaded, about 15 MB, for the Unicode
version of this interpreter's unicodedata -- the classes and the expected
answers have to come from the same version.

Not part of the test suite because of that size; tests/test_bidi.py keeps a
handful of cases from both.
"""

from __future__ import annotations

import sys
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from xhtml2pdf.bidi import (
    _paragraph_level,
    _paragraphs,
    bidi_class,
    reorder,
    resolve_levels,
)


def read(name: str, ucd_dir: Path | None) -> list[str]:
    if ucd_dir is not None:
        return (ucd_dir / name).read_text(encoding="utf-8").splitlines()
    url = f"https://www.unicode.org/Public/{unicodedata.unidata_version}/ucd/{name}"
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8").splitlines()


def run(types: list[str], base_dir: str | None, text: str | None):
    """Levels (None where X9 removes) and visual order, as the suites list them."""
    levels: list[int | None] = []
    para_levels = []
    for start, end in _paragraphs(types):
        para_level = _paragraph_level(types[start:end], base_dir)
        para_levels.append(para_level)
        levels.extend(
            resolve_levels(
                types[start:end], para_level, text[start:end] if text else None
            )
        )
    kept = [i for i, level in enumerate(levels) if level is not None]
    order = [kept[i] for i in reorder([levels[i] for i in kept])]  # type: ignore[misc]
    return levels, order, para_levels


def check_bidi_test(lines: list[str]) -> tuple[int, int, list[str]]:
    passed = failed = 0
    failures: list[str] = []
    expected_levels: list[int | None] = []
    expected_order: list[int] = []
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("@Levels:"):
            expected_levels = [None if v == "x" else int(v) for v in line[8:].split()]
            continue
        if line.startswith("@Reorder:"):
            expected_order = [int(v) for v in line[9:].split()]
            continue
        if line.startswith("@"):
            continue
        classes, bitset = line.split(";")
        types = classes.split()
        for bit, base_dir in ((1, None), (2, "L"), (4, "R")):
            if not int(bitset) & bit:
                continue
            levels, order, _ = run(types, base_dir, None)
            if levels == expected_levels and order == expected_order:
                passed += 1
            else:
                failed += 1
                if len(failures) < 20:
                    failures.append(
                        f"{classes} base={base_dir}: levels {levels} order {order}, "
                        f"expected {expected_levels} {expected_order}"
                    )
    return passed, failed, failures


def check_character_test(lines: list[str]) -> tuple[int, int, list[str]]:
    passed = failed = 0
    failures: list[str] = []
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        codes, direction, para_level, level_field, order_field = line.split(";")
        text = "".join(chr(int(c, 16)) for c in codes.split())
        base_dir = {"0": "L", "1": "R", "2": None}[direction]
        expected_levels = [None if v == "x" else int(v) for v in level_field.split()]
        expected_order = [int(v) for v in order_field.split()]
        levels, order, para_levels = run([bidi_class(c) for c in text], base_dir, text)
        if (
            levels == expected_levels
            and order == expected_order
            and para_levels[0] == int(para_level)
        ):
            passed += 1
        else:
            failed += 1
            if len(failures) < 20:
                failures.append(
                    f"{codes} dir={direction}: levels {levels} order {order}, "
                    f"expected {expected_levels} {expected_order}"
                )
    return passed, failed, failures


def main() -> int:
    ucd_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print(f"Unicode {unicodedata.unidata_version}")
    status = 0
    for name, check in (
        ("BidiTest.txt", check_bidi_test),
        ("BidiCharacterTest.txt", check_character_test),
    ):
        passed, failed, failures = check(read(name, ucd_dir))
        print(f"{name}: {passed} passed, {failed} failed")
        for failure in failures:
            print("   ", failure)
        status = status or int(failed > 0)
    return status


if __name__ == "__main__":
    sys.exit(main())
