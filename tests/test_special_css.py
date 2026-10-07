import io
import re
import time
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa
from xhtml2pdf.util import apply_text_transform
from xhtml2pdf.w3c.css import CSSBuilder
from xhtml2pdf.w3c.cssParser import CSSParser
from xhtml2pdf.w3c.cssSpecial import parseSpecialRules, splitBorder


class FontTest(TestCase):
    """
    Tests if the CSS font property gets split up properly
    into font-size, font-weight, etc.
    """

    def test_font_size_family(self) -> None:
        func_in = [("font", [("15", "px"), "Comic Sans"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("font-size", ("15", "px"), None),
            ("font-family", ["Comic Sans"], None),
        ]
        self.assertEqual(func_out, expected)

    def test_font_style_size_family(self) -> None:
        func_in = [("font", ["italic", ("15", "px"), "Comic Sans"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("font-style", "italic", None),
            ("font-size", ("15", "px"), None),
            ("font-family", ["Comic Sans"], None),
        ]
        self.assertEqual(func_out, expected)

    def test_font_variant_size_family(self) -> None:
        func_in = [("font", ["small-caps", ("15", "px"), "Comic Sans"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("font-variant", "small-caps", None),
            ("font-size", ("15", "px"), None),
            ("font-family", ["Comic Sans"], None),
        ]
        self.assertEqual(func_out, expected)

    def test_font_weight_size_family(self) -> None:
        func_in = [("font", ["bold", ("15", "px"), "Comic Sans"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("font-weight", "bold", None),
            ("font-size", ("15", "px"), None),
            ("font-family", ["Comic Sans"], None),
        ]
        self.assertEqual(func_out, expected)

    def test_font_style_variant_weight_size_height_family(self) -> None:
        func_in = [
            (
                "font",
                [
                    "italic",
                    "small-caps",
                    "bold",
                    (("15", "px"), "/", ("30", "px")),
                    "Comic Sans",
                ],
                None,
            )
        ]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("font-style", "italic", None),
            ("font-variant", "small-caps", None),
            ("font-weight", "bold", None),
            ("font-size", ("15", "px"), None),
            ("line-height", ("30", "px"), None),
            ("font-family", ["Comic Sans"], None),
        ]
        self.assertEqual(func_out, expected)


class BackgroundTest(TestCase):
    """
    Tests if the CSS background property gets split up
    properly into background-image and background-color
    """

    def test_background_image(self) -> None:
        func_in = [("background", "image.jpg", None)]
        func_out = parseSpecialRules(func_in)
        expected = [("background-image", "image.jpg", None)]
        self.assertEqual(func_out, expected)

    def test_background_color(self) -> None:
        func_in = [("background", "lightblue", None)]
        func_out = parseSpecialRules(func_in)
        expected = [("background-color", "lightblue", None)]
        self.assertEqual(func_out, expected)


class TranslucentBackgroundTest(TestCase):
    """
    A background with an alpha is painted once, and leaves the text opaque.

    The words inside a block inherited its background and painted it again
    behind every line, and that second fill left its opacity on for the text:
    black text on #0b5e9b33 came out at 20 %.
    """

    BLUE = ".043137 .368627 .607843 rg"

    @staticmethod
    def _stream(html: str) -> str:
        dest = io.BytesIO()
        pisa.CreatePDF(html, dest=dest)
        page = PdfReader(io.BytesIO(dest.getvalue())).pages[0]
        return page.get_contents().get_data().decode("latin-1")

    def _fills(self, html: str) -> int:
        return self._stream(html).count(self.BLUE)

    @staticmethod
    def _opacity_at_text(html: str) -> list:
        """The fill-opacity state in force at every BT, tracking q/Q."""
        dest = io.BytesIO()
        pisa.CreatePDF(html, dest=dest)
        page = PdfReader(io.BytesIO(dest.getvalue())).pages[0]
        states = page["/Resources"].get("/ExtGState", {})
        stream = page.get_contents().get_data().decode("latin-1")
        stack, found = [1.0], []
        for token in re.finditer(r"\bq\b|\bQ\b|/(\S+) gs|\bBT\b", stream):
            text = token.group(0)
            if text == "q":
                stack.append(stack[-1])
            elif text == "Q":
                stack.pop()
            elif text == "BT":
                found.append(stack[-1])
            else:
                stack[-1] = float(states[f"/{token.group(1)}"].get("/ca", stack[-1]))
        return found

    def test_a_paragraph_paints_it_once(self) -> None:
        html = '<p style="background-color:#0b5e9b33">Hola</p>'
        self.assertEqual(1, self._fills(html))
        self.assertEqual({1.0}, set(self._opacity_at_text(html)))

    def test_a_block_of_text_paints_it_once(self) -> None:
        self.assertEqual(
            1, self._fills('<div style="background-color:#0b5e9b33">Hola</div>')
        )

    def test_a_cell_paints_it_once(self) -> None:
        html = (
            '<table><tr><td style="background-color:#0b5e9b33">Hola</td></tr></table>'
        )
        self.assertEqual(1, self._fills(html))
        self.assertEqual({1.0}, set(self._opacity_at_text(html)))

    def test_a_row_and_a_table_paint_it_once(self) -> None:
        for attr in ("tr", "table"):
            html = (
                f'<table{" style=background-color:#0b5e9b33" if attr == "table" else ""}>'
                f'<tr{" style=background-color:#0b5e9b33" if attr == "tr" else ""}>'
                "<td>a</td><td>b</td></tr></table>"
            )
            with self.subTest(attr):
                self.assertEqual(1, self._fills(html))

    def test_a_highlighted_word_keeps_its_background(self) -> None:
        html = '<p>a <span style="background-color:#0b5e9b33">Hola</span> b</p>'
        self.assertEqual(1, self._fills(html))
        self.assertEqual({1.0}, set(self._opacity_at_text(html)))


class MarginTest(TestCase):
    """
    Tests if the CSS margin property gets split up properly into
    left, right, top, bottom - depending on the amount of given values (1 to 4)
    """

    def test_one_margin_value(self) -> None:
        func_in = [("margin", ("11", "px"), None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("margin-left", ("11", "px"), None),
            ("margin-right", ("11", "px"), None),
            ("margin-top", ("11", "px"), None),
            ("margin-bottom", ("11", "px"), None),
        ]
        self.assertEqual(func_out, expected)

    def test_two_margin_values(self) -> None:
        func_in = [("margin", [("11", "px"), ("22", "px")], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("margin-left", ("22", "px"), None),
            ("margin-right", ("22", "px"), None),
            ("margin-top", ("11", "px"), None),
            ("margin-bottom", ("11", "px"), None),
        ]
        self.assertEqual(func_out, expected)

    def test_three_margin_values(self) -> None:
        func_in = [("margin", [("11", "px"), ("22", "px"), ("33", "px")], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("margin-left", ("22", "px"), None),
            ("margin-right", ("22", "px"), None),
            ("margin-top", ("11", "px"), None),
            ("margin-bottom", ("33", "px"), None),
        ]
        self.assertEqual(func_out, expected)

    def test_four_margin_values(self) -> None:
        func_in = [
            ("margin", [("11", "px"), ("22", "px"), ("33", "px"), ("44", "px")], None)
        ]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("margin-left", ("44", "px"), None),
            ("margin-right", ("22", "px"), None),
            ("margin-top", ("11", "px"), None),
            ("margin-bottom", ("33", "px"), None),
        ]
        self.assertEqual(func_out, expected)


class PaddingTest(TestCase):
    """
    Tests if the CSS padding property gets split up properly into
    left, right, top, bottom - depending on the amount of given values (1 to 4)
    """

    def test_one_padding_value(self) -> None:
        func_in = [("padding", ("11", "px"), None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("padding-left", ("11", "px"), None),
            ("padding-right", ("11", "px"), None),
            ("padding-top", ("11", "px"), None),
            ("padding-bottom", ("11", "px"), None),
        ]
        self.assertEqual(func_out, expected)

    def test_two_padding_values(self) -> None:
        func_in = [("padding", [("11", "px"), ("22", "px")], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("padding-left", ("22", "px"), None),
            ("padding-right", ("22", "px"), None),
            ("padding-top", ("11", "px"), None),
            ("padding-bottom", ("11", "px"), None),
        ]
        self.assertEqual(func_out, expected)

    def test_three_padding_values(self) -> None:
        func_in = [("padding", [("11", "px"), ("22", "px"), ("33", "px")], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("padding-left", ("22", "px"), None),
            ("padding-right", ("22", "px"), None),
            ("padding-top", ("11", "px"), None),
            ("padding-bottom", ("33", "px"), None),
        ]
        self.assertEqual(func_out, expected)

    def test_four_padding_values(self) -> None:
        func_in = [
            ("padding", [("11", "px"), ("22", "px"), ("33", "px"), ("44", "px")], None)
        ]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("padding-left", ("44", "px"), None),
            ("padding-right", ("22", "px"), None),
            ("padding-top", ("11", "px"), None),
            ("padding-bottom", ("33", "px"), None),
        ]
        self.assertEqual(func_out, expected)


class BorderWidthTest(TestCase):
    """
    Tests if the CSS border-width property gets split up properly into
    left, right, top, bottom -  depending on the amount of given values (1 to 4)
    """

    def test_one_border_width_value(self) -> None:
        func_in = [("border-width", ("11", "px"), None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-width", ("11", "px"), None),
            ("border-right-width", ("11", "px"), None),
            ("border-top-width", ("11", "px"), None),
            ("border-bottom-width", ("11", "px"), None),
        ]
        self.assertEqual(func_out, expected)

    def test_two_border_width_values(self) -> None:
        func_in = [("border-width", [("11", "px"), ("22", "px")], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-width", ("22", "px"), None),
            ("border-right-width", ("22", "px"), None),
            ("border-top-width", ("11", "px"), None),
            ("border-bottom-width", ("11", "px"), None),
        ]
        self.assertEqual(func_out, expected)

    def test_three_border_width_values(self) -> None:
        func_in = [("border-width", [("11", "px"), ("22", "px"), ("33", "px")], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-width", ("22", "px"), None),
            ("border-right-width", ("22", "px"), None),
            ("border-top-width", ("11", "px"), None),
            ("border-bottom-width", ("33", "px"), None),
        ]
        self.assertEqual(func_out, expected)

    def test_four_border_width_values(self) -> None:
        func_in = [
            (
                "border-width",
                [("11", "px"), ("22", "px"), ("33", "px"), ("44", "px")],
                None,
            )
        ]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-width", ("44", "px"), None),
            ("border-right-width", ("22", "px"), None),
            ("border-top-width", ("11", "px"), None),
            ("border-bottom-width", ("33", "px"), None),
        ]
        self.assertEqual(func_out, expected)


class BorderColorTest(TestCase):
    def test_one_border_color_value(self) -> None:
        func_in = [("border-color", ["red"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-color", "red", None),
            ("border-right-color", "red", None),
            ("border-top-color", "red", None),
            ("border-bottom-color", "red", None),
        ]
        self.assertEqual(func_out, expected)

    def test_two_border_color_values(self) -> None:
        func_in = [("border-color", ["red", "green"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-color", "green", None),
            ("border-right-color", "green", None),
            ("border-top-color", "red", None),
            ("border-bottom-color", "red", None),
        ]
        self.assertEqual(func_out, expected)

    def test_three_border_color_values(self) -> None:
        func_in = [("border-color", ["red", "green", "blue"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-color", "green", None),
            ("border-right-color", "green", None),
            ("border-top-color", "red", None),
            ("border-bottom-color", "blue", None),
        ]
        self.assertEqual(func_out, expected)

    def test_four_border_color_values(self) -> None:
        func_in = [("border-color", ["red", "green", "blue", "pink"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-color", "pink", None),
            ("border-right-color", "green", None),
            ("border-top-color", "red", None),
            ("border-bottom-color", "blue", None),
        ]
        self.assertEqual(func_out, expected)


class BorderStyleTest(TestCase):
    """
    Tests if the CSS border-style property gets split up properly into
    left, right, top, bottom - depending on the amount of given values (1 to 4)
    """

    def test_one_border_style_value(self) -> None:
        func_in = [("border-style", ["dotted"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-style", "dotted", None),
            ("border-right-style", "dotted", None),
            ("border-top-style", "dotted", None),
            ("border-bottom-style", "dotted", None),
        ]
        self.assertEqual(func_out, expected)

    def test_two_border_style_values(self) -> None:
        func_in = [("border-style", ["dotted", "solid"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-style", "solid", None),
            ("border-right-style", "solid", None),
            ("border-top-style", "dotted", None),
            ("border-bottom-style", "dotted", None),
        ]
        self.assertEqual(func_out, expected)

    def test_three_border_style_values(self) -> None:
        func_in = [("border-style", ["dotted", "solid", "double"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-style", "solid", None),
            ("border-right-style", "solid", None),
            ("border-top-style", "dotted", None),
            ("border-bottom-style", "double", None),
        ]
        self.assertEqual(func_out, expected)

    def test_four_border_style_values(self) -> None:
        func_in = [("border-style", ["dotted", "solid", "double", "dashed"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-style", "dashed", None),
            ("border-right-style", "solid", None),
            ("border-top-style", "dotted", None),
            ("border-bottom-style", "double", None),
        ]
        self.assertEqual(func_out, expected)


class BorderSplitTest(TestCase):
    """Tests the functionality of splitBorder(), that should output (width, style color)"""

    def test_split_border_empty(self) -> None:
        func_in: list = []
        func_out = splitBorder(func_in)
        expected = (None, None, None)
        self.assertEqual(func_out, expected)

    def test_split_border_style(self) -> None:
        func_in = ["dotted"]
        func_out = splitBorder(func_in)
        expected = (None, "dotted", None)
        self.assertEqual(func_out, expected)

    def test_split_border_style_width(self) -> None:
        func_in = ["dotted", ("99", "px")]
        func_out = splitBorder(func_in)
        expected = (("99", "px"), "dotted", None)
        self.assertEqual(func_out, expected)

    def test_split_border_style_color(self) -> None:
        func_in = ["red", "dotted"]
        func_out = splitBorder(func_in)
        expected = (None, "dotted", "red")
        self.assertEqual(func_out, expected)

    def test_split_border_style_width_color(self) -> None:
        func_in = ["red", "dotted", ("99", "px")]
        func_out = splitBorder(func_in)
        expected = (("99", "px"), "dotted", "red")
        self.assertEqual(func_out, expected)


class BorderTest(TestCase):
    """
    Tests if the CSS border property gets split up properly into
    width, style and color - depending on the amount of given values (1 to 3)
    """

    def test_border_style(self) -> None:
        func_in = [("border", "dotted", None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-style", "dotted", None),
            ("border-right-style", "dotted", None),
            ("border-top-style", "dotted", None),
            ("border-bottom-style", "dotted", None),
        ]
        self.assertEqual(func_out, expected)

    def test_border_width_style(self) -> None:
        func_in = [("border", [("99", "px"), "dotted"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-width", ("99", "px"), None),
            ("border-right-width", ("99", "px"), None),
            ("border-top-width", ("99", "px"), None),
            ("border-bottom-width", ("99", "px"), None),
            ("border-left-style", "dotted", None),
            ("border-right-style", "dotted", None),
            ("border-top-style", "dotted", None),
            ("border-bottom-style", "dotted", None),
        ]
        self.assertEqual(func_out, expected)

    def test_border_style_color(self) -> None:
        func_in = [("border", ["dotted", "red"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-style", "dotted", None),
            ("border-right-style", "dotted", None),
            ("border-top-style", "dotted", None),
            ("border-bottom-style", "dotted", None),
            ("border-left-color", "red", None),
            ("border-right-color", "red", None),
            ("border-top-color", "red", None),
            ("border-bottom-color", "red", None),
        ]
        self.assertEqual(func_out, expected)

    def test_border_width_style_color(self) -> None:
        func_in = [("border", [("99", "px"), "dotted", "red"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-width", ("99", "px"), None),
            ("border-right-width", ("99", "px"), None),
            ("border-top-width", ("99", "px"), None),
            ("border-bottom-width", ("99", "px"), None),
            ("border-left-style", "dotted", None),
            ("border-right-style", "dotted", None),
            ("border-top-style", "dotted", None),
            ("border-bottom-style", "dotted", None),
            ("border-left-color", "red", None),
            ("border-right-color", "red", None),
            ("border-top-color", "red", None),
            ("border-bottom-color", "red", None),
        ]
        self.assertEqual(func_out, expected)


class BorderTop(TestCase):
    """
    Tests if the CSS border-top property gets split up properly into
    width, style, color - depending on the amount of given values (1 to 3)
    """

    def test_border_top_style(self) -> None:
        func_in = [("border-top", "dotted", None)]
        func_out = parseSpecialRules(func_in)
        expected = [("border-top-style", "dotted", None)]
        self.assertEqual(func_out, expected)

    def test_border_top_widt_style(self) -> None:
        func_in = [("border-top", [("99", "px"), "dotted"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-top-width", ("99", "px"), None),
            ("border-top-style", "dotted", None),
        ]
        self.assertEqual(func_out, expected)

    def test_border_top_style_color(self) -> None:
        func_in = [("border-top", ["dotted", "red"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-top-style", "dotted", None),
            ("border-top-color", "red", None),
        ]
        self.assertEqual(func_out, expected)

    def test_border_top_width_style_color(self) -> None:
        func_in = [("border-top", [("99", "px"), "dotted", "red"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-top-width", ("99", "px"), None),
            ("border-top-style", "dotted", None),
            ("border-top-color", "red", None),
        ]
        self.assertEqual(func_out, expected)


class BorderBottom(TestCase):
    """
    Tests if the CSS border-bottom property gets split up properly into
    width, style, color - No need to test for different combinations,
    as it's the same as in BorderTop()
    """

    def test_border_top_width_style_color(self) -> None:
        func_in = [("border-bottom", [("99", "px"), "dotted", "red"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-bottom-width", ("99", "px"), None),
            ("border-bottom-style", "dotted", None),
            ("border-bottom-color", "red", None),
        ]
        self.assertEqual(func_out, expected)


class BorderLeft(TestCase):
    """
    Tests if the CSS border-left property gets split up properly into
    width, style, color - No need to test for different combinations,
    as it's the same as in BorderTop()
    """

    def test_border_top_width_style_color(self) -> None:
        func_in = [("border-left", [("99", "px"), "dotted", "red"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-left-width", ("99", "px"), None),
            ("border-left-style", "dotted", None),
            ("border-left-color", "red", None),
        ]
        self.assertEqual(func_out, expected)


class BorderRight(TestCase):
    """
    Tests if the CSS border-right property gets split up properly into
    width, style, color - No need to test for different combinations,
    as it's the same as in BorderTop()
    """

    def test_border_top_width_style_color(self) -> None:
        func_in = [("border-right", [("99", "px"), "dotted", "red"], None)]
        func_out = parseSpecialRules(func_in)
        expected = [
            ("border-right-width", ("99", "px"), None),
            ("border-right-style", "dotted", None),
            ("border-right-color", "red", None),
        ]
        self.assertEqual(func_out, expected)


class ListStyleShorthandTest(TestCase):
    """
    The list-style shorthand was not expanded at all, so the whole declaration
    was dropped and `list-style: none` did nothing.
    """

    def test_none_sets_both_type_and_image(self) -> None:
        # CSS 2.1 12.6.2: a bare `none` is ambiguous and sets both.
        self.assertEqual(
            [("list-style-type", "none", None), ("list-style-image", "none", None)],
            parseSpecialRules([("list-style", ["none"], None)]),
        )

    def test_type_and_position(self) -> None:
        self.assertEqual(
            [
                ("list-style-type", "square", None),
                ("list-style-position", "inside", None),
            ],
            parseSpecialRules([("list-style", ["square", "inside"], None)]),
        )

    def test_anything_else_is_the_image(self) -> None:
        self.assertEqual(
            [("list-style-image", "bullet.png", None)],
            parseSpecialRules([("list-style", ["bullet.png"], None)]),
        )


class TextTransformTest(TestCase):
    def test_transforms(self) -> None:
        self.assertEqual("ABC DEF", apply_text_transform("abc def", "uppercase"))
        self.assertEqual("abc def", apply_text_transform("ABC DEF", "lowercase"))
        self.assertEqual("Abc Def", apply_text_transform("abc def", "capitalize"))
        self.assertEqual("abc def", apply_text_transform("abc def", "none"))
        self.assertEqual("abc def", apply_text_transform("abc def", "nonsense"))


class WhiteSpaceTest(TestCase):
    """
    CSS 2.1 16.6. Only `pre` used to have any effect; nowrap, pre-wrap and
    pre-line all behaved as `normal`.
    """

    @staticmethod
    def _text(value: str) -> str:
        html = (
            "<html><body>"
            f'<p style="white-space: {value}">two   spaces\nand a newline</p>'
            "</body></html>"
        )
        out = io.BytesIO()
        pisa.pisaDocument(io.StringIO(html), out)
        return PdfReader(out).pages[0].extract_text()

    def test_normal_collapses_everything(self) -> None:
        self.assertEqual("two spaces and a newline", self._text("normal").strip())

    def test_pre_line_keeps_the_newline_and_collapses_spaces(self) -> None:
        self.assertEqual(
            ["two spaces", "and a newline"], self._text("pre-line").strip().split("\n")
        )

    def test_pre_wrap_keeps_both(self) -> None:
        lines = self._text("pre-wrap").strip().split("\n")
        self.assertEqual(2, len(lines))
        self.assertIn("two   spaces", lines[0])

    def test_nowrap_keeps_one_line(self) -> None:
        self.assertEqual("two spaces and a newline", self._text("nowrap").strip())


class BackgroundShorthandTest(TestCase):
    """
    Every part of the shorthand but one used to be thrown away: the first was
    read as an image if it contained a dot and as a colour otherwise.
    """

    def test_colour_image_and_repeat(self) -> None:
        self.assertEqual(
            [
                ("background-color", "#fcaf3e", None),
                ("background-image", "img/a.png", None),
                ("background-repeat", "no-repeat", None),
            ],
            parseSpecialRules(
                [("background", ["#fcaf3e", "img/a.png", "no-repeat"], None)]
            ),
        )

    def test_position_is_collected(self) -> None:
        self.assertEqual(
            [
                ("background-image", "a.png", None),
                ("background-repeat", "repeat-x", None),
                ("background-position", "right top", None),
            ],
            parseSpecialRules(
                [("background", ["a.png", "repeat-x", "right", "top"], None)]
            ),
        )

    def test_colour_alone(self) -> None:
        self.assertEqual(
            [("background-color", "red", None)],
            parseSpecialRules([("background", "red", None)]),
        )

    def test_attachment_is_recognised_and_dropped(self) -> None:
        # Nothing consumes background-attachment; a PDF page does not scroll.
        # What matters is that "fixed" is not mistaken for a colour.
        self.assertEqual(
            [("background-color", "red", None)],
            parseSpecialRules([("background", ["red", "fixed"], None)]),
        )


class StringPatternBacktrackingTest(TestCase):
    """
    The string and escape patterns used to give the engine two ways to match
    the same character, and inside a `*` that costs exponential time on a
    string nobody closed: 40 backslashes in a <style> held a worker for three
    minutes, and each further four multiplied it by eight. The three shapes
    below are the ones that overlapped -- a bare backslash, a run of hex
    digits after one, and the space an escape may swallow.
    """

    #: Well under what any of these costs once it backtracks, and far above
    #: the cost of matching them once each way round.
    BUDGET_SECONDS = 5

    def assertMatchesQuickly(self, text: str) -> None:
        start = time.monotonic()
        CSSParser.re_string.match(text)
        self.assertLess(time.monotonic() - start, self.BUDGET_SECONDS)

    def test_an_unclosed_string_of_backslashes(self) -> None:
        self.assertMatchesQuickly('"' + "\\" * 64)

    def test_an_unclosed_string_of_hex_escapes(self) -> None:
        self.assertMatchesQuickly('"' + "\\aaaaaaa" * 64)

    def test_an_unclosed_string_of_spaced_escapes(self) -> None:
        self.assertMatchesQuickly('"' + "\\1 " * 64)

    def test_what_the_pattern_still_reads(self) -> None:
        """The escapes above are not rejected, only matched the one way."""
        for text, content in (
            ('"plain"', "plain"),
            (r'"a\41 b"', r"a\41 b"),
            (r'"a\000041b"', r"a\000041b"),
            (r'"back\\slash"', r"back\\slash"),
            ("'single'", "single"),
        ):
            with self.subTest(text=text):
                match = CSSParser.re_string.match(text)
                if match is None:
                    self.fail(f"{text} no longer reads as a string")
                self.assertEqual(content, next(g for g in match.groups() if g))


class FlexShorthandTest(TestCase):
    """
    flex expands into flex-grow, flex-shrink and flex-basis.

    The omitted parts are not the longhands' initial values: css-flexbox-1
    7.1.1 says a bare number means basis 0, and a bare basis means grow 1.
    """

    @staticmethod
    def _expand(value):
        return parseSpecialRules([("flex", value, None)])

    def test_one_number_means_grow_one_shrink_one_basis_zero(self) -> None:
        self.assertEqual(
            [
                ("flex-grow", "1", None),
                ("flex-shrink", "1", None),
                ("flex-basis", "0", None),
            ],
            self._expand("1"),
        )

    def test_none_auto_and_initial(self) -> None:
        self.assertEqual(
            [
                ("flex-grow", "0", None),
                ("flex-shrink", "0", None),
                ("flex-basis", "auto", None),
            ],
            self._expand("none"),
        )
        self.assertEqual(
            [
                ("flex-grow", "1", None),
                ("flex-shrink", "1", None),
                ("flex-basis", "auto", None),
            ],
            self._expand("auto"),
        )
        self.assertEqual(
            [
                ("flex-grow", "0", None),
                ("flex-shrink", "1", None),
                ("flex-basis", "auto", None),
            ],
            self._expand("initial"),
        )

    def test_a_bare_basis_means_grow_one(self) -> None:
        self.assertEqual(
            [
                ("flex-grow", "1", None),
                ("flex-shrink", "1", None),
                ("flex-basis", ("120", "px"), None),
            ],
            self._expand(("120", "px")),
        )

    def test_two_and_three_value_forms(self) -> None:
        self.assertEqual(
            [
                ("flex-grow", "2", None),
                ("flex-shrink", "0", None),
                ("flex-basis", "0", None),
            ],
            self._expand(["2", "0"]),
        )
        self.assertEqual(
            [
                ("flex-grow", "1", None),
                ("flex-shrink", "1", None),
                ("flex-basis", "auto", None),
            ],
            self._expand(["1", "auto"]),
        )
        self.assertEqual(
            [
                ("flex-grow", "0", None),
                ("flex-shrink", "0", None),
                ("flex-basis", ("120", "px"), None),
            ],
            self._expand(["0", "0", ("120", "px")]),
        )
        # The basis may come first.
        self.assertEqual(
            [
                ("flex-grow", "2", None),
                ("flex-shrink", "1", None),
                ("flex-basis", ("30", "%"), None),
            ],
            self._expand([("30", "%"), "2"]),
        )

    def test_a_form_it_does_not_understand_is_kept_as_written(self) -> None:
        with self.assertLogs("xhtml2pdf.w3c.cssSpecial", level="WARNING"):
            self.assertEqual(
                [("flex", ["1", "2", "3"], None)], self._expand(["1", "2", "3"])
            )


class FlexFlowTest(TestCase):
    def test_either_order(self) -> None:
        self.assertEqual(
            [("flex-direction", "row", None), ("flex-wrap", "wrap", None)],
            parseSpecialRules([("flex-flow", ["row", "wrap"], None)]),
        )
        self.assertEqual(
            [("flex-wrap", "wrap-reverse", None), ("flex-direction", "column", None)],
            parseSpecialRules([("flex-flow", ["wrap-reverse", "column"], None)]),
        )

    def test_one_value(self) -> None:
        self.assertEqual(
            [("flex-wrap", "wrap", None)],
            parseSpecialRules([("flex-flow", "wrap", None)]),
        )

    def test_a_stray_word_keeps_the_declaration_as_written(self) -> None:
        with self.assertLogs("xhtml2pdf.w3c.cssSpecial", level="WARNING"):
            self.assertEqual(
                [("flex-flow", ["row", "tight"], None)],
                parseSpecialRules([("flex-flow", ["row", "tight"], None)]),
            )


class GapTest(TestCase):
    def test_one_value_sets_both_axes(self) -> None:
        self.assertEqual(
            [("row-gap", ("1", "em"), None), ("column-gap", ("1", "em"), None)],
            parseSpecialRules([("gap", ("1", "em"), None)]),
        )

    def test_two_values_are_row_then_column(self) -> None:
        self.assertEqual(
            [("row-gap", ("10", "px"), None), ("column-gap", ("5", "px"), None)],
            parseSpecialRules([("gap", [("10", "px"), ("5", "px")], None)]),
        )

    def test_three_values_keep_the_declaration_as_written(self) -> None:
        parts = [("1", "px"), ("2", "px"), ("3", "px")]
        with self.assertLogs("xhtml2pdf.w3c.cssSpecial", level="WARNING"):
            self.assertEqual(
                [("gap", parts, None)], parseSpecialRules([("gap", parts, None)])
            )


def _radii(value: str) -> dict:
    """What `border-radius: <value>` expands to, through the real parser."""
    builder = CSSBuilder(mediumSet=["all"])
    declarations, _ = CSSParser(builder).parseInline(f"border-radius: {value}")
    return declarations


class BorderRadiusShorthandTest(TestCase):
    """
    border-radius lists the corners top-left, top-right, bottom-right,
    bottom-left, with the same 1-to-4 pattern as margin; `/` separates the
    horizontal radii from the vertical ones.
    """

    @staticmethod
    def corners(value: str) -> list:
        radii = _radii(value)
        return [
            radii[f"border-{corner}-radius"]
            for corner in ("top-left", "top-right", "bottom-right", "bottom-left")
        ]

    def test_one_value_rounds_every_corner_alike(self) -> None:
        px = ("10", "px")
        self.assertEqual([[px, px]] * 4, self.corners("10px"))

    def test_two_values_pair_opposite_corners(self) -> None:
        a, b = ("1", "px"), ("2", "px")
        self.assertEqual([[a, a], [b, b], [a, a], [b, b]], self.corners("1px 2px"))

    def test_three_values_share_the_second_between_top_right_and_bottom_left(
        self,
    ) -> None:
        a, b, c = ("1", "px"), ("2", "px"), ("3", "px")
        self.assertEqual([[a, a], [b, b], [c, c], [b, b]], self.corners("1px 2px 3px"))

    def test_four_values_go_clockwise_from_top_left(self) -> None:
        values = [(str(n), "px") for n in (1, 2, 3, 4)]
        self.assertEqual([[v, v] for v in values], self.corners("1px 2px 3px 4px"))

    def test_slash_gives_the_vertical_radii(self) -> None:
        h, v = ("10", "px"), ("20", "px")
        self.assertEqual([[h, v]] * 4, self.corners("10px / 20px"))
        self.assertEqual([[h, v]] * 4, self.corners("10px/20px"))

    def test_each_side_of_the_slash_expands_on_its_own(self) -> None:
        px = lambda n: (str(n), "px")  # noqa: E731
        self.assertEqual(
            [[px(10), px(20)], [px(5), px(4)], [px(3), px(20)], [px(1), px(4)]],
            self.corners("10px 5px 3px 1px / 20px 4px"),
        )

    def test_percentages_and_ems_are_kept_as_written(self) -> None:
        self.assertEqual([[("50", "%")] * 2] * 4, self.corners("50%"))
        self.assertEqual([[("1", "em"), ("2", "em")]] * 4, self.corners("1em/2em"))

    def test_zero(self) -> None:
        self.assertEqual([["0", "0"]] * 4, self.corners("0"))

    def test_an_invalid_value_drops_the_declaration(self) -> None:
        for value in ("-3px", "1px/2px/3px", "calc(1px)", "1px 2px 3px 4px 5px", "10"):
            with (
                self.subTest(value),
                self.assertLogs("xhtml2pdf.w3c.cssSpecial", level="WARNING"),
            ):
                self.assertEqual({}, dict(_radii(value)))

    def test_an_invalid_longhand_is_dropped(self) -> None:
        with self.assertLogs("xhtml2pdf.w3c.cssSpecial", level="WARNING"):
            self.assertEqual(
                [],
                parseSpecialRules([("border-top-left-radius", [("-1", "px")], None)]),
            )

    def test_a_valid_longhand_is_kept(self) -> None:
        declaration = ("border-top-left-radius", [("1", "px"), ("2", "px")], None)
        self.assertEqual([declaration], parseSpecialRules([declaration]))


class TransparentColorTest(TestCase):
    """`color: transparent` and the hex forms with alpha (#811)."""

    @staticmethod
    def render(html: str) -> str:
        out = io.BytesIO()
        result = pisa.CreatePDF(html, dest=out)
        assert not result.err
        page = PdfReader(io.BytesIO(out.getvalue())).pages[0]
        return page.get_contents().get_data().decode("latin-1")

    def text_operators(self, html: str, word: str) -> str:
        return next(
            line for line in self.render(html).splitlines() if f"({word})" in line
        )

    def test_transparent_text_is_drawn_with_no_ink(self) -> None:
        line = self.text_operators('<p style="color: transparent">HIDDEN</p>', "HIDDEN")
        # An ExtGState with a zero fill alpha is set before the text.
        self.assertIn(" gs ", line)

    def test_opaque_text_sets_no_alpha(self) -> None:
        line = self.text_operators("<p>SHOWN</p>", "SHOWN")
        self.assertNotIn(" gs ", line)

    def test_four_digit_hex_does_not_abort(self) -> None:
        line = self.text_operators('<p style="color: #0000">HIDDEN</p>', "HIDDEN")
        self.assertIn(" gs ", line)

    def test_eight_digit_hex_is_read_as_rgba(self) -> None:
        line = self.text_operators('<p style="color: #ff000080">RED</p>', "RED")
        self.assertIn("1 0 0 rg", line)


class RootEmTest(TestCase):
    """rem is relative to the font size of <html> (#726)."""

    @staticmethod
    def font_sizes(html: str) -> list[str]:
        out = io.BytesIO()
        pisa.CreatePDF(html, dest=out)
        page = PdfReader(io.BytesIO(out.getvalue())).pages[0]
        data = page.get_contents().get_data().decode("latin-1")
        return [
            line.split(" Tf")[0].split()[-1]
            for line in data.splitlines()
            if "Tj" in line
        ]

    def test_rem_ignores_the_parent_font_size(self) -> None:
        sizes = self.font_sizes(
            '<html style="font-size: 20px"><body><div style="font-size: 10px">'
            '<p style="font-size: 2rem">x</p></div></body></html>'
        )
        self.assertEqual(["30"], sizes)

    def test_rem_uses_the_default_root_size(self) -> None:
        # DEFAULT_CSS sets html to 10px, 7.5pt.
        sizes = self.font_sizes(
            '<div style="font-size: 30pt"><p style="font-size: 2rem">x</p></div>'
        )
        self.assertEqual(["15"], sizes)

    def test_rem_on_html_itself_is_the_initial_size(self) -> None:
        sizes = self.font_sizes(
            '<html style="font-size: 1rem"><body><p>x</p></body></html>'
        )
        self.assertEqual(["12"], sizes)
