"""CSS counters and ::before / ::after content (#112)."""

from __future__ import annotations

import io
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa
from xhtml2pdf.w3c.css import CSSString, CSSTerminalFunction
from xhtml2pdf.w3c.generated_content import (
    AttrItem,
    CounterItem,
    Counters,
    format_counter,
    parse_content,
    parse_counter_list,
)

HEADINGS = """
body { counter-reset: h2 }
h2 { counter-increment: h2; counter-reset: h3 }
h3 { counter-increment: h3 }
h2::before { content: counter(h2) ". " }
h3::before { content: counter(h2) "." counter(h3) " " }
"""


def render(body: str, css: str = HEADINGS) -> PdfReader:
    html = f"<html><head><style>{css}</style></head><body>{body}</body></html>"
    output = io.BytesIO()
    pisa.CreatePDF(html, dest=output, raise_exception=True)
    return PdfReader(output)


def lines(body: str, css: str = HEADINGS) -> list[str]:
    text = "".join(page.extract_text() for page in render(body, css).pages)
    return [line.strip() for line in text.split("\n") if line.strip()]


def outline_titles(items) -> list[str]:
    titles: list[str] = []
    for item in items:
        if isinstance(item, list):
            titles += outline_titles(item)
        else:
            titles.append(item["/Title"])
    return titles


class NumberedHeadingsTest(TestCase):
    BODY = "<h2>Intro</h2><h3>Scope</h3><h3>Terms</h3><h2>Design</h2><h3>Parts</h3>"

    def test_the_headings_are_numbered(self) -> None:
        self.assertEqual(
            ["1. Intro", "1.1 Scope", "1.2 Terms", "2. Design", "2.1 Parts"],
            lines(self.BODY),
        )

    def test_the_table_of_contents_shows_the_numbers(self) -> None:
        text = lines("<pdf:toc/>" + self.BODY)

        # Once in the table of contents and once as the heading itself.
        for heading in ("1. Intro", "1.1 Scope", "2.1 Parts"):
            self.assertEqual(2, text.count(heading), (heading, text))

    def test_the_outline_shows_the_numbers(self) -> None:
        titles = outline_titles(render(self.BODY).outline)

        self.assertIn("1.2 Terms", titles)
        self.assertIn("2. Design", titles)

    def test_a_hidden_heading_is_not_counted(self) -> None:
        body = '<h2>A</h2><h2 style="display: none">Hidden</h2><h2>B</h2>'

        self.assertEqual(["1. A", "2. B"], lines(body))

    def test_without_a_before_rule_nothing_changes(self) -> None:
        self.assertEqual(["Intro"], lines("<h2>Intro</h2>", css="h2 { color: red }"))


class ContentTest(TestCase):
    def test_after_and_attr(self) -> None:
        css = 'p::after { content: " [" attr(data-ref) "]" }'

        self.assertEqual(["Text [r1]"], lines('<p data-ref="r1">Text</p>', css))

    def test_a_counter_style(self) -> None:
        css = (
            "ol { counter-reset: item; list-style: none }"
            " li { counter-increment: item }"
            ' li::before { content: counter(item, upper-roman) ") " }'
        )

        self.assertEqual(
            ["I) a", "II) b", "III) c"],
            lines("<ol><li>a</li><li>b</li><li>c</li></ol>", css),
        )

    def test_counters_joins_the_nested_instances(self) -> None:
        css = (
            "ol { counter-reset: item; list-style: none } li { counter-increment: item }"
            ' li::before { content: counters(item, ".") " " }'
        )
        body = "<ol><li>a<ol><li>b</li><li>c</li></ol></li><li>d</li></ol>"

        self.assertEqual(["1 a", "1.1 b", "1.2 c", "2 d"], lines(body, css))

    def test_the_css2_single_colon_form(self) -> None:
        css = 'h2:before { content: "> " }'

        self.assertEqual(["> Intro"], lines("<h2>Intro</h2>", css))

    def test_a_before_rule_does_not_style_the_element_itself(self) -> None:
        css = 'h2::before { content: "x "; color: red }'
        reader = render("<h2>Intro</h2>", css)
        content = reader.pages[0].get_contents().get_data().decode("latin-1")

        # The number is red, the heading after it is not.
        self.assertIn("1 0 0 rg", content)
        self.assertIn("0 0 0 rg", content)

    def test_the_more_specific_rule_wins(self) -> None:
        css = 'h2::before { content: "a " } h2.x::before { content: "b " }'

        self.assertEqual(["b Intro"], lines('<h2 class="x">Intro</h2>', css))

    def test_none_and_an_empty_string_generate_nothing(self) -> None:
        for content in ("none", '""'):
            with self.subTest(content=content):
                css = f"h2::before {{ content: {content} }}"
                self.assertEqual(["Intro"], lines("<h2>Intro</h2>", css))


class FormatCounterTest(TestCase):
    def test_styles(self) -> None:
        cases = {
            "decimal": "4",
            "decimal-leading-zero": "04",
            "lower-roman": "iv",
            "upper-roman": "IV",
            "lower-alpha": "d",
            "upper-latin": "D",
            "lower-greek": "δ",
            "none": "",
            "unknown": "4",
        }
        for style, expected in cases.items():
            with self.subTest(style=style):
                self.assertEqual(expected, format_counter(4, style))

    def test_letters_go_on_past_z(self) -> None:
        self.assertEqual(
            ["z", "aa", "ab"], [format_counter(n, "lower-alpha") for n in (26, 27, 28)]
        )

    def test_out_of_range_falls_back_to_decimal(self) -> None:
        self.assertEqual("0", format_counter(0, "upper-roman"))
        self.assertEqual("-1", format_counter(-1, "lower-alpha"))


class ParseTest(TestCase):
    def test_content_items(self) -> None:
        value = [
            CSSTerminalFunction("counter", ["h2", "upper-roman"]),
            CSSString(". "),
            CSSTerminalFunction("counters", ["item", CSSString(".")]),
            CSSTerminalFunction("attr", ["title"]),
        ]

        self.assertEqual(
            [
                CounterItem("h2", "upper-roman"),
                ". ",
                CounterItem("item", "decimal", "."),
                AttrItem("title"),
            ],
            parse_content(value),
        )

    def test_a_css_escape_in_a_string(self) -> None:
        self.assertEqual(["—"], parse_content(CSSString("\\2014")))

    def test_none_is_nothing_and_the_string_none_is_text(self) -> None:
        self.assertIsNone(parse_content("none"))
        self.assertEqual(["none"], parse_content(CSSString("none")))

    def test_counter_lists(self) -> None:
        self.assertEqual(
            [("h2", 0), ("h3", 5)], parse_counter_list(["h2", "h3", "5"], 0)
        )
        self.assertEqual([], parse_counter_list("none", 1))


class CountersTest(TestCase):
    def test_a_sibling_reset_takes_over_and_leaving_the_parent_ends_it(self) -> None:
        from xml.dom.minidom import parseString

        root = parseString("<r><a/><b/></r>").documentElement
        assert root is not None
        a, b = root.childNodes
        assert a.parentNode is not None and b.parentNode is not None
        counters = Counters()
        counters.reset(root, "n", 1)
        counters.reset(a.parentNode, "n", 5)
        counters.increment(b.parentNode, "n", 1)

        self.assertEqual([6], counters.values("n"))
        counters.leave(root)
        self.assertEqual([], counters.values("n"))
