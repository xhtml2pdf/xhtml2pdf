from unittest import TestCase

from reportlab import rl_config
from reportlab.lib.colors import Color

from xhtml2pdf import util as utils
from xhtml2pdf.files import pisaTempFile
from xhtml2pdf.tags import int_to_roman
from xhtml2pdf.util import (
    DEFAULT_FONT_SIZE,
    copy_attrs,
    getBorderStyle,
    getBox,
    getColor,
    getCoords,
    getFrameDimensions,
    getKeepInFrameMode,
    getSize,
    set_value,
    transform_attrs,
)
from xhtml2pdf.w3c.css import CSSTerminalFunction


class UtilsCoordTestCase(TestCase):
    def test_get_coordinates_simple(self):
        res = getCoords(1, 1, 10, 10, (10, 10))
        self.assertEqual(res, (1, -1, 10, 10))

        # A second time - it's memoized!
        res = getCoords(1, 1, 10, 10, (10, 10))
        self.assertEqual(res, (1, -1, 10, 10))

    def test_get_coordinates_x_lt_0(self):
        res = getCoords(-1, 1, 10, 10, (10, 10))
        self.assertEqual(res, (9, -1, 10, 10))

    def test_get_coordinates_y_lt_0(self):
        res = getCoords(1, -1, 10, 10, (10, 10))
        self.assertEqual(res, (1, -9, 10, 10))

    def test_get_coordinates_w_and_h_none(self):
        res = getCoords(1, 1, None, None, (10, 10))
        self.assertEqual(res, (1, 9))

    def test_get_coordinates_w_lt_0(self):
        res = getCoords(1, 1, -1, 10, (10, 10))
        self.assertEqual(res, (1, -1, 8, 10))

    def test_get_coordinates_h_lt_0(self):
        res = getCoords(1, 1, 10, -1, (10, 10))
        self.assertEqual(res, (1, 1, 10, 8))


class UtilsColorTestCase(TestCase):
    def test_get_color_simple(self):
        res = getColor("red")
        self.assertEqual(res, Color(1, 0, 0, 1))

        # Testing it being memoized properly
        res = getColor("red")
        self.assertEqual(res, Color(1, 0, 0, 1))

    def test_get_color_from_color(self):
        # Noop if argument is already a color
        res = getColor(Color(1, 0, 0, 1))
        self.assertEqual(res, Color(1, 0, 0, 1))

    def test_get_transparent_color(self):
        res = getColor("transparent", default="TOKEN")
        self.assertEqual(res, "TOKEN")

        res = getColor("none", default="TOKEN")
        self.assertEqual(res, "TOKEN")

    def test_get_color_for_none(self):
        res = getColor(None, default="TOKEN")
        self.assertEqual(res, None)

    def test_get_color_for_RGB(self):
        res = getColor("#FF0000")
        self.assertEqual(res, Color(1, 0, 0, 1))

    def test_get_color_for_RGB_with_len_4(self):
        res = getColor("#F00")
        self.assertEqual(res, Color(1, 0, 0, 1))

    def test_get_color_for_CSS_RGB_function(self):
        # It's regexp based, let's try common cases.
        res = getColor("rgb(255,0,0)")
        self.assertEqual(res, Color(1, 0, 0, 1))

        res = getColor("<css function: rgb(255,0,0)>")
        self.assertEqual(res, Color(1, 0, 0, 1))

    def test_get_color_for_rgb_function_object(self):
        """The parser hands colours over as a function, not as a string."""
        res = getColor(CSSTerminalFunction("rgb", ["10", "200", "10"]))
        self.assertEqual(res, getColor("#0ac80a"))

    def test_get_color_for_rgba_function_object(self):
        """
        The alpha of an rgba() is not a colour channel.

        Reading the channels off the object's repr with a pattern written for
        `rgb(` matched from the "a" onwards, so rgba(10, 200, 10, 1) came out
        as #0ac801: the alpha had landed in the blue channel.
        """
        res = getColor(CSSTerminalFunction("rgba", ["10", "200", "10", "1"]))
        self.assertEqual(res, getColor("#0ac80a"))

        translucent = getColor(CSSTerminalFunction("rgba", ["10", "200", "10", "0.5"]))
        self.assertEqual(translucent.alpha, 0.5)
        self.assertEqual(
            (translucent.red, translucent.green, translucent.blue),
            (10 / 255.0, 200 / 255.0, 10 / 255.0),
        )

    def test_get_color_for_rgb_percentages(self):
        """
        A percentage argument arrives stringified, as "('50', '%')".

        CSSTerminalFunction turns every argument that is not already a str into
        one, so the number has to be found rather than parsed off a fixed
        shape. Before, these resolved to black.
        """
        res = getColor(
            CSSTerminalFunction(
                "rgb", [str(("50", "%")), str(("20", "%")), str(("10", "%"))]
            )
        )
        self.assertEqual((res.red, res.green, res.blue), (0.5, 0.2, 0.1))

    def test_get_color_clamps_out_of_range_channels(self):
        res = getColor(CSSTerminalFunction("rgb", ["300", "-5", "10"]))
        self.assertEqual((res.red, res.green), (1.0, 0.0))

    def test_get_color_for_unreadable_function(self):
        """An unreadable colour is worth a log line, not an exception."""
        for params in (["a", "b", "c"], ["10", "200"]):
            with self.subTest(params=params):
                res = getColor(CSSTerminalFunction("rgb", params), default="TOKEN")
                self.assertEqual(res, "TOKEN")

    def test_get_color_for_unreadable_string(self):
        """
        Colours reportlab cannot read raise rather than returning the default.

        `rgb(nope)` reaches toColor as a string it recognises the shape of but
        cannot read, and it answered with ValueError -- which abandoned the
        whole document over one unreadable colour.
        """
        res = getColor("rgb(nope)", default="TOKEN")
        self.assertEqual(res, "TOKEN")


class UtilsGetSizeUnreadableTestCase(TestCase):
    """getSize must answer with its default rather than with a traceback."""

    @staticmethod
    def unreadable():
        """
        What `@page { margin: calc(1cm + 1mm) }` actually hands to getSize.

        A fresh object each time: getSize is memoized, and two tests sharing
        one value would find the second call answered from the cache with no
        logging at all.
        """
        return CSSTerminalFunction("calc", ["1cm", "+", "1mm"])

    def test_unreadable_value_returns_the_default(self):
        size = getSize(self.unreadable(), relative=7.5, default="TOKEN")
        self.assertEqual(size, "TOKEN")

    def test_unreadable_value_logs_one_line(self):
        """
        A whole traceback per unreadable length buried the log.

        A stylesheet with a handful of calc() lengths produced ten lines of
        traceback for each one, at warning level, which made the warnings that
        mattered impossible to find. The traceback moved to debug.
        """
        with self.assertLogs("xhtml2pdf.util", level="WARNING") as captured:
            getSize(self.unreadable(), relative=7.5, default=0)

        self.assertEqual(len(captured.records), 1)
        record = captured.records[0]
        self.assertIsNone(record.exc_info)
        self.assertIn("cannot read", record.getMessage())

    def test_unreadable_value_keeps_the_traceback_at_debug(self):
        with self.assertLogs("xhtml2pdf.util", level="DEBUG") as captured:
            getSize(self.unreadable(), relative=7.5, default=0)

        self.assertTrue(any(r.exc_info for r in captured.records))


class UtilsGetSizeTestCase(TestCase):
    def test_get_size_simple(self):
        res = getSize("12pt")
        self.assertEqual(res, 12.00)

        # Memoized...
        res = getSize("12pt")
        self.assertEqual(res, 12.00)

    def test_get_size_for_none(self):
        res = getSize(None, relative="TOKEN")
        self.assertEqual(res, "TOKEN")

    def test_get_size_for_float(self):
        res = getSize(12.00)
        self.assertEqual(res, 12.00)

    def test_get_size_for_tuple(self):
        # TODO: This is a really strange case. Probably should not work this
        # way.
        res = getSize(("12", ".12"))
        self.assertEqual(res, 12.12)

    def test_get_size_for_cm(self):
        res = getSize("1cm")
        self.assertEqual(res, 28.346456692913385)

    def test_get_size_for_mm(self):
        res = getSize("1mm")
        self.assertEqual(res, 2.8346456692913385)

    def test_get_size_for_in(self):
        res = getSize("1in")
        self.assertEqual(res, 72.00)

    def test_get_size_for_inch(self):
        res = getSize("1in")
        self.assertEqual(res, 72.00)

    def test_get_size_for_pc(self):
        res = getSize("1pc")
        self.assertEqual(res, 12.00)

    def test_get_size_for_none_str(self):
        res = getSize("none")
        self.assertEqual(res, 0.0)
        res = getSize("0")
        self.assertEqual(res, 0.0)
        res = getSize("auto")  # Really?
        self.assertEqual(res, 0.0)


class PisaDimensionTestCase(TestCase):
    def test_frame_dimensions_left_top_width_height(self):
        dims = {"left": "10pt", "top": "20pt", "width": "30pt", "height": "40pt"}
        expected = (10.0, 20.0, 30.0, 40.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_left_top_width_height_percent(self):
        dims = {"left": "10%", "top": "10%", "width": "30%", "height": "20%"}
        expected = (10.0, 20.0, 30.0, 40.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_left_top_bottom_right(self):
        dims = {"left": "10pt", "top": "20pt", "bottom": "30pt", "right": "40pt"}
        expected = (10.0, 20.0, 50.0, 150.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_bottom_right_width_height(self):
        dims = {"bottom": "10pt", "right": "20pt", "width": "70pt", "height": "80pt"}
        expected = (10.0, 110.0, 70.0, 80.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_left_top_width_height_with_margin(self):
        dims = {
            "left": "10pt",
            "top": "20pt",
            "width": "70pt",
            "height": "80pt",
            "margin-top": "10pt",
            "margin-left": "15pt",
            "margin-bottom": "20pt",
            "margin-right": "25pt",
        }
        # The margin offsets the frame, it does not eat into the declared size:
        # left 10 + margin-left 15 puts the left edge at 25, and the frame is
        # the 70x80 that was asked for. A margin outside the box is what the
        # CSS box model means by margin; the frame used to come back 30x50,
        # the declared size with the margins subtracted from it.
        expected = (25.0, 30.0, 70.0, 80.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_bottom_right_width_height_with_margin(self):
        dims = {
            "bottom": "10pt",
            "right": "20pt",
            "width": "70pt",
            "height": "80pt",
            "margin-top": "10pt",
            "margin-left": "15pt",
            "margin-bottom": "20pt",
            "margin-right": "25pt",
        }
        # As above, anchored to the opposite corner. left comes out negative
        # because a 70pt-wide frame whose right edge sits 45pt from the right
        # of a 100pt page does not fit; that is the declaration's own doing,
        # and _pisaAddFrame warns about the resulting geometry.
        expected = (-15.0, 90.0, 70.0, 80.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_page_margin_and_height(self):
        # @page { margin: 10pt; height: 40pt } asks for a content area 40pt
        # tall, inset 10pt from every page edge -- the geometry the browser
        # comparison's css-page-box fixture reproduces.
        dims = {
            "margin-top": "10pt",
            "margin-left": "10pt",
            "margin-bottom": "10pt",
            "margin-right": "10pt",
            "height": "40pt",
        }
        expected = (10.0, 10.0, 80.0, 40.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_relative_margin(self):
        # A relative length used to resolve to nothing: getSize returns its
        # default when it is handed a relative unit and no base, so the margin
        # silently became 0 and the frame filled the page.
        dims = {
            "margin-top": "2em",
            "margin-left": "2em",
            "margin-bottom": "2em",
            "margin-right": "2em",
        }
        margin = 2 * DEFAULT_FONT_SIZE
        expected = (margin, margin, 100 - 2 * margin, 200 - 2 * margin)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_relative_margin_with_font_size(self):
        dims = {"margin-top": "2em", "margin-left": "2em"}
        result = getFrameDimensions(dims, 100, 200, font_size=20.0)
        self.assertEqual((40.0, 40.0, 60.0, 160.0), result)

    def test_frame_dimensions_percentage_is_of_the_page(self):
        # CSS 2.1 10.2/10.5: the page box is the containing block, so a
        # percentage is a fraction of the page and differs per axis. getSize
        # would read it against the font size.
        dims = {
            "margin-top": "10%",
            "margin-left": "10%",
            "margin-bottom": "10%",
            "margin-right": "10%",
        }
        expected = (10.0, 20.0, 80.0, 160.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_for_box_len_eq_4(self):
        dims = {"-pdf-frame-box": ["12pt", "12,pt", "12pt", "12pt"]}
        expected = (12.0, 12.0, 12.0, 12.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(result, expected)

    def test_frame_dimensions_for_height_without_top_or_bottom(self):
        dims = {
            "left": "10pt",
            # 'top': '20pt',
            "width": "30pt",
            "height": "40pt",
        }
        # top defaults to 0, so the frame is the declared 40pt tall at the top
        # of the page. It used to come back full-page: the height was computed
        # and then thrown away, because nothing moved the bottom edge.
        expected = (10.0, 0.0, 30.0, 40.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)

    def test_frame_dimensions_for_width_without_left_or_right(self):
        dims = {
            # 'left': '10pt',
            "top": "20pt",
            "width": "30pt",
            "height": "40pt",
        }
        # Likewise for width with neither left nor right: left defaults to 0
        # and the frame is the declared 30pt wide, not the full 100pt page.
        expected = (0.0, 20.0, 30.0, 40.0)
        result = getFrameDimensions(dims, 100, 200)
        self.assertEqual(expected, result)


class GetPosTestCase(TestCase):
    def test_get_pos_simple(self):
        res = getBox("1pt 1pt 10pt 10pt", (10, 10))
        self.assertEqual(res, (1.0, -1.0, 10, 10))

    def test_get_pos_raising(self):
        raised = False
        try:
            getBox("1pt 1pt 10pt", (10, 10))
        except Exception:
            raised = True
        self.assertTrue(raised)


class GetKeepInFrameModeTestCase(TestCase):
    def test_the_four_modes_are_read_as_written(self):
        for mode in ("shrink", "error", "overflow", "truncate"):
            self.assertEqual(mode, getKeepInFrameMode(f"  {mode.upper()} "))

    def test_anything_else_falls_back(self):
        """KeepInFrame raises on a mode it does not know, so nothing else may reach it."""
        self.assertEqual("shrink", getKeepInFrameMode("clip"))
        self.assertEqual("shrink", getKeepInFrameMode(None))
        self.assertEqual("truncate", getKeepInFrameMode("", default="truncate"))


class TestTagUtils(TestCase):
    def test_roman_numeral_conversion(self):
        self.assertEqual("I", int_to_roman(1))
        self.assertEqual("L", int_to_roman(50))
        self.assertEqual("XLII", int_to_roman(42))
        self.assertEqual("XXVI", int_to_roman(26))


class TempFileTestCase(TestCase):
    def test_unicode(self):
        """Asserts bytes generated by reportlab are returned"""
        src = pisaTempFile()
        value = (
            b"%PDF-1.4\r\n%\x93\x8c\x8b\x9e ReportLab Generated PDF document"
            b" http://www.reportlab.com"
        )
        try:
            src.write(value)
        except UnicodeDecodeError as error:
            self.fail(error)


class GetBorderStyleTestCase(TestCase):
    def test_will_return_value_if_passed_value_is_not_none_or_hidden(self):
        style = getBorderStyle("foo", default="blah")
        self.assertEqual(style, "foo")

    def test_will_return_default_if_passed_value_is_non_case_sensitive_none(self):
        style = getBorderStyle("None", default="blah")
        self.assertEqual(style, "blah")

    def test_will_return_default_if_passed_value_is_non_case_sensitive_hidden(self):
        style = getBorderStyle("hidDen", default="defaultPassedArg")
        self.assertEqual(style, "defaultPassedArg")


class CopyUtils(TestCase):
    class A:
        attr = 2
        attr1 = 10

    class B:
        def __init__(self, a, b):
            self.attr = a
            self.attr1 = b

    class C:
        pass

    class D:
        param1 = 28
        param2 = 1

    def test_set_value(self):
        a = self.A()
        b = self.B(20, 30)
        c = self.C()
        set_value(a, ["attr", "attr1"], 8)
        set_value(b, ["attr", "attr1"], 8)
        set_value(c, ["attr", "attr1"], 8)

        self.assertEqual(a.attr, 8)
        self.assertEqual(a.attr1, 8)
        self.assertEqual(b.attr, 8)
        self.assertEqual(b.attr1, 8)
        self.assertEqual(c.attr, 8)
        self.assertEqual(c.attr1, 8)

    def test_copy_attrs(self):
        a = self.A()
        b = self.B(19, 22)
        copy_attrs(a, b, ["attr", "attr1"])
        self.assertEqual(a.attr, 19)
        self.assertEqual(a.attr1, 22)

    def test_transform_attrs(self):
        obj = self.D()
        container = {"attr": 19, "attr1": 22}

        transform_attrs(obj, (("param1", "attr"), ("param2", "attr1")), container, str)

        self.assertEqual(obj.param1, str(19))
        self.assertEqual(obj.param2, str(22))


class MemoizedTest(TestCase):
    def test_cache_is_bounded(self) -> None:
        """
        Keys come from CSS in the rendered document, so an unbounded cache
        grows without limit in a long-running server process.
        """
        calls: list[int] = []

        def double(value: int) -> int:
            calls.append(value)
            return value * 2

        memoized = utils.Memoized(double, maxsize=2)
        for value in (1, 2, 3):
            memoized(value)

        self.assertEqual(2, len(memoized.cache))
        self.assertEqual([1, 2, 3], calls)

        # 1 was evicted first (FIFO), so it has to be recomputed
        memoized(1)
        self.assertEqual([1, 2, 3, 1], calls)

    def test_hit_does_not_recompute(self) -> None:
        calls: list[int] = []
        memoized = utils.Memoized(calls.append)
        memoized(1)
        memoized(1)
        self.assertEqual([1], calls)

    def test_unhashable_arguments_bypass_the_cache(self) -> None:
        """The TypeError fallback is why this cannot become functools.lru_cache."""
        memoized = utils.Memoized(sum)
        self.assertEqual(6, memoized([1, 2, 3]))
        self.assertEqual({}, memoized.cache)

    def test_reset_caches_clears_every_instance(self) -> None:
        utils.getSize("1cm")
        self.assertTrue(utils.getSize.cache)
        utils.reset_caches()
        self.assertEqual({}, utils.getSize.cache)

    def test_registered_with_reportlab_reset(self) -> None:
        """
        Reportlab wraps reset callbacks in a WeakMethod, which rejects builtins
        such as ``dict.clear``.
        """
        utils.getSize("2cm")
        self.assertTrue(utils.getSize.cache)
        rl_config._reset()
        self.assertEqual({}, utils.getSize.cache)
