"""
Tests for xhtml2pdf.bidi, the Unicode Bidirectional Algorithm.

The full Unicode conformance suites run with tools/bidi/conformance.py; the
cases here are a sample of both, kept so that a regression shows up in the
ordinary test run, plus what get_display adds on top of the algorithm:
mirroring and dropping the control characters.
"""

from __future__ import annotations

from unittest import TestCase

from xhtml2pdf.bidi import (
    CONTROL_CHARS,
    _paragraph_level,
    bidi_class,
    display_order,
    get_display,
    mirrored,
    needs_bidi,
    reorder,
    resolve_levels,
)

#: From BidiCharacterTest.txt, Unicode 15.1: code points; direction (0 LTR,
#: 1 RTL, 2 auto); paragraph level; levels; visual order.
CHARACTER_CASES = """
0061 0062 0063 0020 0028 0064 0065 0066 0020 0627 0628 062C 0029 0020 05D0 05D1 05D2;0;0;0 0 0 0 0 0 0 0 0 1 1 1 0 0 1 1 1;0 1 2 3 4 5 6 7 8 11 10 9 12 13 16 15 14
05D0 05D1 05D2 0020 0028 0064 0065 0066 0020 0627 0628 062C 0029 0020 0061 0062 0063;1;1;1 1 1 1 1 2 2 2 1 1 1 1 1 1 2 2 2;14 15 16 13 12 11 10 9 8 5 6 7 4 3 2 1 0
05D0 05D1 05D2 0020 0028 0627 0628 062C 0020 0064 0065 0066 0029 0020 0061 0062 0063;0;0;1 1 1 0 0 1 1 1 0 0 0 0 0 0 0 0 0;2 1 0 3 4 7 6 5 8 9 10 11 12 13 14 15 16
0627 0628 062C 0020 0062 006F 006F 006B 0028 0073 0029;1;1;1 1 1 1 2 2 2 2 2 2 2;4 5 6 7 8 9 10 3 2 1 0
202E 0061 202A 0062 202C 2066 0063 2069 202A 0064 202C 0065 202C;2;0;x 1 x 2 x 1 2 1 x 2 x 1 x;11 9 7 6 5 3 1
202D 0661 202B 0662 202C 2068 0663 2069 202B 0664 202C 0665 202C;0;0;x 2 x 4 x 2 6 2 x 4 x 2 x;1 3 5 6 7 9 11
202B 202D 05D0 202C 0028 005B 0061 202C 202E 005D 0029 202C;2;1;x x 4 x 4 4 4 x x 3 3 x;10 9 2 4 5 6
05D0 0028 05D1 0029 0331;0;0;1 1 1 1 1;4 3 2 1 0
0661 0028 0332 0662 0029 0333;0;0;2 1 1 2 1 1;5 4 3 2 1 0
0041 200F 005B 200D 200B 20D6 05D0 005D 200B 200D 20D6;1;1;2 1 1 x x 1 1 1 x x 1;10 7 6 5 2 1 0
05D0 2067 202A 0041;1;1;1 1 x 4;3 1 0
062A 0031 002F 0032;2;1;1 2 2 2;1 2 3 0
0061 2067 202A 2069 0062;1;1;2 2 x 2 2;0 1 3 4
"""

#: From BidiTest.txt, Unicode 15.1: levels | visual order | classes;
#: paragraph levels to try (1 auto, 2 LTR, 4 RTL, as a bitset).
CLASS_CASES = """
0 | 0 | CS; 3
0 0 x x | 0 1 | WS NSM LRE RLO; 3
1 x x 1 | 3 0 | RLI PDF BN B; 4
x 3 x 4 | 3 1 | RLO ES LRE ET; 4
0 0 x 2 | 0 1 3 | ON CS LRO ES; 3
1 1 1 x | 2 1 0 | CS FSI PDI RLE; 4
1 x 1 1 | 3 2 0 | FSI BN LRI LRI; 4
x 1 0 0 | 1 2 3 | RLO ET LRI WS; 3
0 0 0 0 | 0 1 2 3 | CS EN NSM S; 3
0 2 2 2 | 0 1 2 3 | LRI WS EN ON; 3
1 1 3 1 | 3 2 1 0 | AL FSI AL S; 5
"""


def _visual_order(levels: list[int | None]) -> list[int]:
    kept = [i for i, level in enumerate(levels) if level is not None]
    return [kept[i] for i in reorder([levels[i] for i in kept])]  # type: ignore[misc]


def _parse_levels(field: str) -> list[int | None]:
    return [None if value == "x" else int(value) for value in field.split()]


class ConformanceSampleTests(TestCase):
    def test_character_cases(self) -> None:
        for line in CHARACTER_CASES.strip().splitlines():
            codes, direction, para_level, levels, order = line.split(";")
            with self.subTest(codes=codes, direction=direction):
                text = "".join(chr(int(code, 16)) for code in codes.split())
                types = [bidi_class(char) for char in text]
                base_dir = {"0": "L", "1": "R", "2": None}[direction]
                level = _paragraph_level(types, base_dir)
                self.assertEqual(level, int(para_level))
                resolved = resolve_levels(types, level, text)
                self.assertEqual(resolved, _parse_levels(levels))
                self.assertEqual(
                    _visual_order(resolved), [int(i) for i in order.split()]
                )

    def test_class_cases(self) -> None:
        for line in CLASS_CASES.strip().splitlines():
            levels, order, case = (part.strip() for part in line.split("|"))
            classes, bitset = case.split(";")
            types = classes.split()
            # Bit 1 is the automatic direction, which each case here resolves
            # to LTR or RTL along with one of the forced ones.
            for bit, para_level in ((2, 0), (4, 1)):
                if not int(bitset) & bit:
                    continue
                with self.subTest(classes=classes, para_level=para_level):
                    # The paragraph separator closes the paragraph and
                    # belongs to it, which resolve_levels handles as the
                    # last character.
                    resolved = resolve_levels(types, para_level)
                    self.assertEqual(resolved, _parse_levels(levels))
                    self.assertEqual(
                        _visual_order(resolved), [int(i) for i in order.split()]
                    )


class GetDisplayTests(TestCase):
    def test_left_to_right_text_is_returned_unchanged(self) -> None:
        text = "Plain text, 12.5% (and brackets)."
        self.assertIs(get_display(text, base_dir="L"), text)

    def test_empty_text(self) -> None:
        self.assertEqual(get_display("", base_dir="R"), "")

    def test_brackets_are_mirrored_in_right_to_left_text(self) -> None:
        # Rule L4: at an odd level a bracket is drawn as its mirror image.
        self.assertEqual(get_display("(א)", base_dir="R"), "(א)")
        self.assertEqual(get_display("«שלום»", base_dir="R"), "«םולש»")

    def test_latin_inside_right_to_left_keeps_its_brackets(self) -> None:
        self.assertEqual(
            get_display("שלום (world) 123", base_dir="R"), "123 (world) םולש"
        )

    def test_bracket_pairs_are_resolved_together(self) -> None:
        # Rule N0: each pair takes the direction of what it encloses.
        self.assertEqual(get_display("[אב] (גד)", base_dir="R"), "(דג) [בא]")
        self.assertEqual(get_display("[אב] (גד)", base_dir="L"), "[בא] (דג)")

    def test_hebrew_word_inside_left_to_right_text(self) -> None:
        self.assertEqual(get_display("abc אבג def", base_dir="L"), "abc גבא def")

    def test_list_marker_in_right_to_left(self) -> None:
        self.assertEqual(get_display("1.", base_dir="R"), ".1")

    def test_arabic_letters_turn_european_digits_arabic(self) -> None:
        self.assertEqual(get_display("رقم 123", base_dir="R"), "123 مقر")

    def test_control_characters_are_not_drawn(self) -> None:
        self.assertEqual(get_display("א\u2067b\u2069", base_dir="R"), "bא")
        self.assertEqual(get_display("a\u200fb\u202bc\u202c", base_dir="L"), "abc")

    def test_other_format_characters_stay(self) -> None:
        # A soft hyphen is BN, removed from the algorithm but not the text.
        self.assertEqual(get_display("אב\u00adגד", base_dir="R"), "דג\u00adבא")

    def test_paragraph_separators_start_a_new_paragraph(self) -> None:
        self.assertEqual(get_display("אב\nגד", base_dir="L"), "בא\nדג")

    def test_automatic_direction(self) -> None:
        self.assertEqual(get_display("אב c", base_dir=None), "c בא")
        self.assertEqual(get_display("c אב", base_dir=None), "c בא")


class LineApiTests(TestCase):
    """What Paragraph.displayLines builds a line's order from."""

    def test_needs_bidi_finds_every_character_that_reorders(self) -> None:
        import sys

        reordering = {"R", "AL", "AN", "RLE", "RLO", "RLI", "FSI", "LRE", "LRO"}
        reordering |= {"LRI", "PDF", "PDI"}
        missed = [
            hex(code)
            for code in range(sys.maxunicode + 1)
            if not 0xD800 <= code <= 0xDFFF
            and bidi_class(chr(code)) in reordering
            and not needs_bidi(chr(code))
        ]
        self.assertEqual([], missed)

    def test_needs_bidi_leaves_latin_alone(self) -> None:
        self.assertFalse(needs_bidi("Plain text, 123 (and brackets)."))
        self.assertTrue(needs_bidi("Plain text", base_dir="R"))

    def test_display_order_is_what_get_display_draws(self) -> None:
        text = "אב (cd) 12 \u2067גד\u2069"
        order, levels = display_order(text, "R")
        drawn = "".join(
            mirrored(text[i], levels[i]) for i in order if text[i] not in CONTROL_CHARS
        )
        self.assertEqual(get_display(text, "R"), drawn)

    def test_mirrored_only_at_an_odd_level(self) -> None:
        self.assertEqual(")", mirrored("(", 1))
        self.assertEqual("(", mirrored("(", 2))
        self.assertEqual("a", mirrored("a", 1))
