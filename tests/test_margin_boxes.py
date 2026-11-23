"""The page-margin boxes of CSS Paged Media: @top-center and its kin."""

from __future__ import annotations

import io
import re
import subprocess
import tempfile
from pathlib import Path
from shutil import which
from unittest import TestCase, skipUnless

from pypdf import PdfReader
from reportlab.lib.units import cm

from xhtml2pdf import pisa
from xhtml2pdf.builders.margin_boxes import margin_box_rects
from xhtml2pdf.document import pisaStory
from xhtml2pdf.w3c.cssParser import MARGIN_BOXES

A5 = (420.0, 595.0)


def render(css: str, body: str = "<p>x</p>") -> PdfReader:
    out = io.BytesIO()
    result = pisa.CreatePDF(f"<style>{css}</style>{body}", dest=out)
    assert not result.err
    return PdfReader(io.BytesIO(out.getvalue()))


def page_lines(reader: PdfReader) -> list[list[str]]:
    return [page.extract_text().splitlines() for page in reader.pages]


def words(pdf: bytes) -> dict[str, tuple[float, ...]]:
    """Word -> (x0, top, x1, bottom) on page one, from pdftotext -bbox."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.pdf"
        path.write_bytes(pdf)
        out = subprocess.run(
            ["pdftotext", "-bbox", "-f", "1", "-l", "1", str(path), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    found = {}
    for match in re.finditer(
        r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]+)<', out
    ):
        found[match.group(5)] = tuple(float(match.group(i)) for i in range(1, 5))
    return found


class ParseTest(TestCase):
    def test_every_box_is_kept_on_its_page(self) -> None:
        boxes = " ".join(f'@{name} {{ content: "{name}" }}' for name in MARGIN_BOXES)
        context = pisaStory(f"<style>@page {{ margin: 2cm; {boxes} }}</style><p>x</p>")
        (template,) = context.templateList.values()
        self.assertEqual(
            sorted(MARGIN_BOXES), sorted(box.name for box in template.pisaMarginBoxes)
        )

    def test_content_none_makes_no_box(self) -> None:
        context = pisaStory(
            "<style>@page { margin: 2cm; @top-center { content: none } }</style><p>x</p>"
        )
        (template,) = context.templateList.values()
        self.assertEqual([], template.pisaMarginBoxes)

    def test_the_page_keeps_its_other_declarations(self) -> None:
        context = pisaStory(
            '<style>@page { @top-center { content: "x" } size: a5; margin: 2cm }'
            "</style><p>x</p>"
        )
        self.assertEqual(A5, tuple(round(v) for v in context.pageSize))


class GeometryTest(TestCase):
    MARGINS = (40.0, 30.0, 20.0, 10.0)  # top, right, bottom, left

    def rects(self, *names: str) -> dict:
        return margin_box_rects((200.0, 300.0), self.MARGINS, set(names))

    def test_corners_are_the_margin_squares(self) -> None:
        rects = self.rects(
            "top-left-corner",
            "top-right-corner",
            "bottom-left-corner",
            "bottom-right-corner",
        )
        self.assertEqual((0, 260.0, 10.0, 40.0), rects["top-left-corner"])
        self.assertEqual((170.0, 260.0, 30.0, 40.0), rects["top-right-corner"])
        self.assertEqual((0, 0, 10.0, 20.0), rects["bottom-left-corner"])
        self.assertEqual((170.0, 0, 30.0, 20.0), rects["bottom-right-corner"])

    def test_three_boxes_share_the_top_in_thirds(self) -> None:
        rects = self.rects("top-left", "top-center", "top-right")
        for got, expected in zip(
            rects["top-left"], (10.0, 260.0, 160 / 3, 40.0), strict=True
        ):
            self.assertAlmostEqual(expected, got)
        self.assertAlmostEqual(10.0 + 160 / 3, rects["top-center"][0])
        self.assertAlmostEqual(170.0, rects["top-right"][0] + rects["top-right"][2])

    def test_a_lone_box_has_its_whole_side(self) -> None:
        self.assertEqual(
            (10.0, 0, 160.0, 20.0), self.rects("bottom-center")["bottom-center"]
        )
        self.assertEqual(
            (10.0, 260.0, 160.0, 40.0), self.rects("top-right")["top-right"]
        )

    def test_side_boxes_run_down_the_margin(self) -> None:
        rects = self.rects("left-top", "left-bottom")
        self.assertEqual((0, 140.0, 10.0, 120.0), rects["left-top"])
        self.assertEqual((0, 20.0, 10.0, 120.0), rects["left-bottom"])


class DrawTest(TestCase):
    def test_page_numbers_and_the_total(self) -> None:
        reader = render(
            "@page { margin: 2cm; @bottom-center { content: 'Page ' counter(page)"
            " ' of ' counter(pages) } }",
            "<p>one</p><pdf:nextpage/><p>two</p><pdf:nextpage/><p>three</p>",
        )
        for number, lines in enumerate(page_lines(reader), start=1):
            self.assertIn(f"Page {number} of 3", lines)

    def test_a_counter_style_and_a_reset(self) -> None:
        reader = render(
            "@page { margin: 2cm; @bottom-right { content: counter(page, upper-roman) } }",
            "<p>one</p><pdf:nextpage/><pdf:resetpagenumber value='10'/><p>two</p>",
        )
        self.assertEqual(["I", "X"], [lines[-1] for lines in page_lines(reader)])

    def test_the_box_has_its_own_style(self) -> None:
        reader = render(
            "@page { margin: 2cm; @top-left { content: 'Head'; color: #ff0000;"
            " font-size: 20pt; background-color: #00ff00 } }"
        )
        stream = reader.pages[0].get_contents().get_data().decode("latin-1")
        self.assertRegex(stream, r"\b1 0 0 rg\b")
        self.assertRegex(stream, r"\b0 1 0 rg\b")
        self.assertRegex(stream, r"/F\d+ 20 Tf")

    def test_a_translucent_box_is_a_group(self) -> None:
        reader = render(
            "@page { margin: 2cm; @top-left { content: 'x'; opacity: .5 } }"
        )
        xobjects = reader.pages[0]["/Resources"]["/XObject"]
        self.assertEqual(1, len(xobjects))

    @skipUnless(which("pdftotext"), "needs pdftotext")
    def test_each_box_sits_at_its_end_of_the_side(self) -> None:
        out = io.BytesIO()
        pisa.CreatePDF(
            "<style>@page { size: a5; margin: 2cm 1.5cm;"
            " @top-left { content: 'Left' } @top-center { content: 'Middle' }"
            " @top-right { content: 'Right' } @left-middle { content: 'Side' } }"
            "</style><p>x</p>",
            dest=out,
        )
        found = words(out.getvalue())
        width = A5[0]
        self.assertAlmostEqual(1.5 * cm, found["Left"][0], delta=1)
        self.assertAlmostEqual(width - 1.5 * cm, found["Right"][2], delta=1)
        middle = (found["Middle"][0] + found["Middle"][2]) / 2
        self.assertAlmostEqual(width / 2, middle, delta=1)
        # Down the left margin, centred across it by default.
        self.assertAlmostEqual(
            1.5 * cm / 2, (found["Side"][0] + found["Side"][2]) / 2, delta=1
        )
        # In the top margin, centred in it.
        top, bottom = found["Middle"][1], found["Middle"][3]
        self.assertAlmostEqual(cm, (top + bottom) / 2, delta=2)


class FirstPageTest(TestCase):
    BASE = (
        "@page { size: a5; margin: 2cm; @top-center { content: 'Header' }"
        " @bottom-center { content: counter(page) } }"
    )
    BODY = "<p>one</p><pdf:nextpage/><p>two</p><pdf:nextpage/><p>three</p>"

    def heads(self, css: str) -> list[list[str]]:
        return [
            [line for line in lines if line not in {"one", "two", "three"}]
            for lines in page_lines(render(css, self.BODY))
        ]

    def test_first_blanks_a_box_on_page_one_only(self) -> None:
        first = "@page :first { @top-center { content: none } }"
        expected = [["1"], ["Header", "2"], ["Header", "3"]]
        self.assertEqual(expected, self.heads(self.BASE + first))
        # Written before the @page it belongs to, it waits for it.
        self.assertEqual(expected, self.heads(first + self.BASE))

    def test_first_keeps_the_pages_other_declarations(self) -> None:
        reader = render(
            self.BASE + "@page :first { @top-center { content: 'Cover' } }", self.BODY
        )
        self.assertEqual(3, len(reader.pages))
        self.assertEqual(
            {(420, 595)},
            {
                (round(float(p.mediabox.width)), round(float(p.mediabox.height)))
                for p in reader.pages
            },
        )
        self.assertIn("Cover", page_lines(reader)[0])

    @skipUnless(which("pdftotext"), "needs pdftotext")
    def test_first_may_have_margins_of_its_own(self) -> None:
        out = io.BytesIO()
        pisa.CreatePDF(
            f"<style>{self.BASE} @page :first {{ margin-top: 6cm }}</style>"
            + self.BODY,
            dest=out,
        )
        found = words(out.getvalue())
        self.assertGreater(found["one"][1], 6 * cm - 1)


class StringSetTest(TestCase):
    CSS = (
        "@page { size: a6; margin: 1.5cm 1cm;"
        " @top-left { content: string(chapter) }"
        " @top-right { content: 'last:' string(chapter, last) }"
        " @bottom-left { content: 'start:' string(chapter, start) }"
        " @bottom-right { content: 'except:' string(chapter, first-except) } }"
        " h1 { string-set: chapter 'Ch. ' counter(c) ' ' content();"
        " counter-increment: c }"
    )

    def margins(self, body: str) -> list[list[str]]:
        return [
            [line for line in lines if ":" in line or line.startswith("Ch.")]
            for lines in page_lines(render(self.CSS, body))
        ]

    def test_a_running_header_follows_the_headings(self) -> None:
        body = (
            "<h1>One</h1><p>a</p><pdf:nextpage/><p>still one</p><pdf:nextpage/>"
            "<h1>Two</h1><p>b</p><h1>Three</h1><p>c</p>"
        )
        self.assertEqual(
            [
                ["Ch. 1 One", "last:Ch. 1 One", "start:Ch. 1 One", "except:"],
                ["Ch. 1 One", "last:Ch. 1 One", "start:Ch. 1 One", "except:Ch. 1 One"],
                ["Ch. 2 Two", "last:Ch. 3 Three", "start:Ch. 1 One", "except:"],
            ],
            self.margins(body),
        )

    def test_attr_and_a_part_of_the_content(self) -> None:
        reader = render(
            "@page { margin: 2cm; @top-center { content: string(t) '|' string(f) } }"
            " h1 { string-set: t attr(title), f content(first-letter) }",
            '<h1 title="Tooltip">Heading</h1>',
        )
        self.assertIn("Tooltip|H", page_lines(reader)[0])

    def test_before_any_assignment_the_string_is_empty(self) -> None:
        reader = render(
            "@page { margin: 2cm; @top-center { content: '[' string(x) ']' } }",
            "<p>no headings</p>",
        )
        self.assertIn("[]", page_lines(reader)[0])
