"""
CSS custom properties and var() (#743).

var() used to be parsed into a function nothing could evaluate, and the
declaration was dropped with "cannot evaluate: var()"; the custom properties
themselves were reported as properties xhtml2pdf does not implement.
"""

import logging
from pathlib import Path
from unittest import TestCase

from xhtml2pdf.document import pisaStory
from xhtml2pdf.w3c.css_variables import InvalidVarError, substituteFrom

RED, GREEN, BLUE, BLACK = (
    "Color(1,0,0,1)",
    "Color(0,1,0,1)",
    "Color(0,0,1,1)",
    "Color(0,0,0,1)",
)


def _styles(html: str) -> list:
    return [f.style for f in pisaStory(html).story if hasattr(f, "style")]


class SubstituteTest(TestCase):
    def test_a_value(self) -> None:
        self.assertEqual(
            "1px solid red", substituteFrom("1px solid var(--c)", {"--c": "red"})
        )

    def test_a_fallback_and_a_nested_one(self) -> None:
        self.assertEqual("2pt", substituteFrom("var(--a, 2pt)", {}))
        self.assertEqual(
            "3pt", substituteFrom("var(--a, var(--b, 1pt))", {"--b": "3pt"})
        )
        self.assertEqual("1pt 2pt", substituteFrom("var(--a, 1pt 2pt)", {}))

    def test_a_property_holding_var(self) -> None:
        self.assertEqual(
            "4pt", substituteFrom("var(--a)", {"--a": "var(--b)", "--b": "4pt"})
        )

    def test_undefined_and_cycles_are_invalid(self) -> None:
        for text, props in (
            ("var(--a)", {}),
            ("var(--a)", {"--a": "var(--b)", "--b": "var(--a)"}),
            ("var(color)", {}),
            ("var(--a", {"--a": "1"}),
        ):
            with self.subTest(text=text), self.assertRaises(InvalidVarError):
                substituteFrom(text, props)

    def test_a_cycle_takes_the_fallback(self) -> None:
        self.assertEqual("5pt", substituteFrom("var(--a, 5pt)", {"--a": "var(--a)"}))


class DocumentTest(TestCase):
    def setUp(self) -> None:
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)

    def test_root_properties_reach_every_element(self) -> None:
        (style,) = _styles(
            "<style>:root { --s: 20pt; --c: #ff0000 }"
            " p { font-size: var(--s); color: var(--c) }</style><p>x</p>"
        )
        self.assertEqual(20, style.fontSize)
        self.assertEqual(RED, str(style.textColor))

    def test_inherited_and_overridden(self) -> None:
        styles = _styles(
            "<style>:root { --c: #ff0000 } p { color: var(--c) }"
            " .x { --c: #00ff00 }</style>"
            "<p>a</p><div class='x'><div><p>b</p></div></div><p>c</p>"
        )
        self.assertEqual([RED, GREEN, RED], [str(s.textColor) for s in styles])

    def test_inline(self) -> None:
        (style,) = _styles('<p style="--c: #0000ff; color: var(--c)">x</p>')
        self.assertEqual(BLUE, str(style.textColor))

    def test_fallback(self) -> None:
        (style,) = _styles(
            "<style>p { color: var(--none, var(--neither, #0000ff)) }</style><p>x</p>"
        )
        self.assertEqual(BLUE, str(style.textColor))

    def test_an_invalid_one_is_dropped(self) -> None:
        # A cycle, or an undefined property without fallback: the value is
        # what the element would have had without the declaration.
        styles = _styles(
            "<style>p { color: #ff0000 } .a { color: var(--none) }"
            " .b { --x: var(--y); --y: var(--x); color: var(--x) }</style>"
            "<p class='a'>a</p><p class='b'>b</p>"
        )
        self.assertEqual([BLACK, BLACK], [str(s.textColor) for s in styles])

    def test_shorthands(self) -> None:
        (style,) = _styles(
            "<style>:root { --m: 10pt 20pt; --c: #ff0000 }"
            " p { margin: var(--m); border: 2pt solid var(--c) }</style><p>x</p>"
        )
        self.assertEqual((20, 20), (style.leftIndent, style.rightIndent))
        self.assertEqual(2, style.borderTopWidth)
        self.assertEqual(RED, str(style.borderLeftColor))

    def test_a_later_longhand_wins_over_a_pending_shorthand(self) -> None:
        (style,) = _styles(
            "<style>:root { --m: 10pt } p { margin: var(--m); margin-left: 30pt }</style>"
            "<p>x</p>"
        )
        self.assertEqual((30, 10), (style.leftIndent, style.rightIndent))

    def test_the_issue(self) -> None:
        # Salesforce's Lightning stylesheets; this used to warn and drop it.
        with self.assertNoLogs("xhtml2pdf", logging.WARNING):
            logging.disable(logging.NOTSET)
            (style,) = _styles(
                "<style>p { padding-top: var(--lwc-varSpacingXxSmall, 6pt) }</style>"
                "<p>x</p>"
            )
        self.assertEqual(6, style.paddingTop)

    def test_custom_properties_are_not_reported_as_unsupported(self) -> None:
        logging.disable(logging.NOTSET)
        with self.assertLogs("xhtml2pdf", logging.WARNING) as logs:
            logging.getLogger("xhtml2pdf").warning("start")
            _styles("<style>:root { --brand: red } p { float: left }</style><p>x</p>")
        unsupported = [line for line in logs.output if "does not implement" in line]
        self.assertEqual(1, len(unsupported))
        self.assertNotIn("--brand", unsupported[0])

    def test_at_rules_read_the_root_properties(self) -> None:
        context = pisaStory(
            "<style>:root { --m: 2cm; --size: a5 }"
            " @page { margin: var(--m); size: var(--size) landscape }</style><p>x</p>"
        )
        frame = context.templateList["body"].frames[0]
        self.assertAlmostEqual(56.69, frame._x1, places=1)
        self.assertAlmostEqual(595.28, context.pageSize[0], places=1)
        self.assertAlmostEqual(419.53, context.pageSize[1], places=1)

    def test_a_font_face_src(self) -> None:
        font = (
            Path(__file__).parent
            / "samples"
            / "font"
            / "Noto_Sans"
            / "NotoSans-Regular.ttf"
        )
        (style,) = _styles(
            f"<style>html {{ --font: url({font}) }}"
            " @font-face { font-family: N; src: var(--font) }"
            " p { font-family: N }</style><p>x</p>"
        )
        self.assertEqual("n_00", style.fontName)
