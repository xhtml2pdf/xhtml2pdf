import io
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa
from xhtml2pdf.util import apply_text_transform
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
