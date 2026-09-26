import time
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
    reset_caches,
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

    def test_get_color_for_CSS_RGB_function_variants(self):
        """Separators other than a comma, and an alpha, still read."""
        self.assertEqual(getColor("rgb(255 0 0)"), Color(1, 0, 0, 1))
        self.assertEqual(getColor("rgba(255, 0, 0, 0.5)"), Color(1, 0, 0, 1))
        self.assertEqual(getColor("rgb(300,0,0)"), Color(1, 0, 0, 1))
        self.assertEqual(getColor("rgb(1,2)", "no"), "no")

    def test_get_color_does_not_backtrack_on_an_unclosed_rgb(self):
        """
        `rgb(` and nothing to close it used to cost 23 seconds of CPU: the
        pattern had three unanchored `.*?`, each free to divide the digits a
        different way. One `<td bgcolor>` was enough to hold a worker.
        """
        start = time.monotonic()
        getColor("rgb(" + "1" * 90, "default")
        self.assertLess(time.monotonic() - start, 1)

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


class PercentageSizeTestCase(TestCase):
    """
    A percentage is read whether or not there is a base to apply it to.

    The percentage branch used to sit inside `if relative:`, so getSize("100%")
    fell through to float("100%") and logged `getSize: Not a float '100%'`.
    The answer was 0.0 either way -- the warning read like a stylesheet error
    and was not one.
    """

    def setUp(self):
        # getSize is memoized, so a value another test already asked for would
        # answer from the cache and log nothing whatever the code does.
        super().setUp()
        reset_caches()

    def test_a_percentage_of_nothing_is_zero(self):
        self.assertEqual(0.0, getSize("100%"))

    def test_it_says_nothing_about_a_percentage(self):
        with self.assertNoLogs("xhtml2pdf.util", level="WARNING"):
            getSize("100%")

    def test_a_relative_base_is_still_applied(self):
        self.assertEqual(5.0, getSize("50%", 10))

    def test_whitespace_is_tolerated(self):
        self.assertEqual(2.5, getSize(" 25 % ", 10))

    def test_a_real_stylesheet_error_is_still_reported(self):
        with self.assertLogs("xhtml2pdf.util", level="WARNING") as logs:
            self.assertEqual(0.0, getSize("nonsense"))

        self.assertIn("Not a float", logs.output[0])


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


class _RecordingCanvas:
    """Records the drawing calls a box helper makes, in order."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record

    def named(self, name: str) -> list[tuple]:
        return [call for call in self.calls if call[0] == name]


class _BoxStyle:
    """
    A style spelt the way ParagraphStyle spells it, with nothing set.

    drawBoxBackground and drawBoxBorders read their style by attribute name
    so that any object carrying those names will do, a ParagraphStyle or not.
    """

    backColor = None
    backgroundImage = None
    textColor = Color(0, 0, 0)
    fontSize = 10

    def __init__(self, **kwargs) -> None:
        for side in ("Left", "Right", "Top", "Bottom"):
            setattr(self, f"border{side}Style", None)
            setattr(self, f"border{side}Width", 0)
            setattr(self, f"border{side}Color", None)
        for name, value in kwargs.items():
            setattr(self, name, value)


class DrawBoxBackgroundTest(TestCase):
    """The colour under the content; PmlParagraph.draw's first half."""

    def test_nothing_declared_draws_nothing(self) -> None:
        canvas = _RecordingCanvas()
        utils.drawBoxBackground(canvas, 1, 2, 3, 4, _BoxStyle())
        self.assertEqual([], canvas.calls)

    def test_a_colour_fills_the_box(self) -> None:
        canvas = _RecordingCanvas()
        red = Color(1, 0, 0)
        utils.drawBoxBackground(canvas, 10, 20, 100, 50, _BoxStyle(backColor=red))
        self.assertEqual([("setFillColor", (red,), {})], canvas.named("setFillColor"))
        self.assertEqual(
            [("rect", (10, 20, 100, 50), {"fill": 1, "stroke": 0})],
            canvas.named("rect"),
        )

    def test_a_bare_object_needs_no_attributes(self) -> None:
        # A style that does not even spell the names is "none" throughout.
        canvas = _RecordingCanvas()
        utils.drawBoxBackground(canvas, 0, 0, 1, 1, object())
        self.assertEqual([], canvas.calls)


class DrawBoxBordersTest(TestCase):
    """Four independent edges; PmlParagraph.draw's second half."""

    @staticmethod
    def _lines(canvas: _RecordingCanvas) -> list[tuple]:
        return [args for _name, args, _kw in canvas.named("line")]

    def test_no_width_draws_no_line(self) -> None:
        canvas = _RecordingCanvas()
        utils.drawBoxBorders(canvas, 0, 0, 10, 10, _BoxStyle())
        self.assertEqual([], self._lines(canvas))

    def test_each_side_runs_along_its_own_edge(self) -> None:
        canvas = _RecordingCanvas()
        style = _BoxStyle()
        for side in ("Left", "Right", "Top", "Bottom"):
            setattr(style, f"border{side}Style", "solid")
            setattr(style, f"border{side}Width", 1)
            setattr(style, f"border{side}Color", Color(0, 0, 1))
        utils.drawBoxBorders(canvas, 10, 20, 100, 50, style)
        self.assertEqual(
            [
                (10, 20, 10, 70),  # left
                (110, 20, 110, 70),  # right
                (10, 70, 110, 70),  # top
                (10, 20, 110, 20),  # bottom
            ],
            self._lines(canvas),
        )

    def test_a_side_without_a_colour_takes_the_text_colour(self) -> None:
        # W3C: border-color's initial value is currentColor.
        canvas = _RecordingCanvas()
        style = _BoxStyle(
            textColor=Color(0, 1, 0),
            borderTopStyle="solid",
            borderTopWidth=2,
            borderTopColor=None,
        )
        utils.drawBoxBorders(canvas, 0, 0, 10, 10, style)
        self.assertEqual(
            [("setStrokeColor", (Color(0, 1, 0),), {})], canvas.named("setStrokeColor")
        )
        self.assertEqual(1, len(self._lines(canvas)))

    def test_a_side_with_no_style_is_not_drawn(self) -> None:
        # A width alone is not a border: getBorderWidth says the same.
        canvas = _RecordingCanvas()
        style = _BoxStyle(borderLeftWidth=3, borderLeftColor=Color(0, 0, 0))
        utils.drawBoxBorders(canvas, 0, 0, 10, 10, style)
        self.assertEqual([], self._lines(canvas))


class CSSLengthTest(TestCase):
    """A length that keeps its keyword, for the places getSize's 0.0 misleads."""

    def test_getSize_cannot_tell_auto_from_zero(self) -> None:
        # The reason CSSLength exists, as an executable note.
        self.assertEqual(getSize("auto"), getSize("0"))
        self.assertEqual(getSize("none"), getSize("0"))

    def test_a_length_resolves_to_itself(self) -> None:
        self.assertEqual(12.0, utils.getLengthOrAuto("12pt").resolve(500))
        self.assertEqual(12.0, utils.getLengthOrAuto("12pt").resolve(None))

    def test_a_percentage_resolves_against_its_basis(self) -> None:
        length = utils.getLengthOrAuto(("50", "%"))
        self.assertEqual("percent", length.kind)
        self.assertEqual(250.0, length.resolve(500))

    def test_a_percentage_of_nothing_is_indefinite(self) -> None:
        self.assertIsNone(utils.getLengthOrAuto("50%").resolve(None))

    def test_auto_and_none_are_kept_apart(self) -> None:
        self.assertIs(utils.AUTO, utils.getLengthOrAuto("auto"))
        self.assertIs(utils.NONE_LENGTH, utils.getLengthOrAuto("none"))
        self.assertIsNone(utils.AUTO.resolve(100))
        self.assertFalse(utils.AUTO.is_definite)
        self.assertTrue(utils.getLengthOrAuto("0").is_definite)

    def test_em_is_relative_to_the_font_size(self) -> None:
        self.assertEqual(24.0, utils.getLengthOrAuto("2em", 12).value)

    def test_a_bad_value_is_the_initial_value_and_says_so(self) -> None:
        utils._value_warned.discard(("length", "wide"))
        with self.assertLogs("xhtml2pdf.util", level="WARNING") as logs:
            self.assertIs(utils.AUTO, utils.getLengthOrAuto("wide"))
        self.assertIn("wide", logs.output[0])
        # Once per value, not once per element.
        with self.assertNoLogs("xhtml2pdf.util", level="WARNING"):
            utils.getLengthOrAuto("wide")


class FlexConvertersTest(TestCase):
    def test_flex_basis_knows_content(self) -> None:
        self.assertIs(utils.CONTENT, utils.getFlexBasis("content"))
        self.assertIs(utils.AUTO, utils.getFlexBasis("auto"))
        self.assertEqual(0.0, utils.getFlexBasis("0").value)
        self.assertEqual("length", utils.getFlexBasis("0").kind)

    def test_numbers_and_integers(self) -> None:
        self.assertEqual(1.5, utils.getNumber("1.5"))
        self.assertEqual(2.0, utils.getNumber(["2"]))
        self.assertEqual(-1, utils.getInt("-1"))
        utils._value_warned.clear()
        with self.assertLogs("xhtml2pdf.util", level="WARNING"):
            self.assertEqual(0.0, utils.getNumber("lots"))
        with self.assertLogs("xhtml2pdf.util", level="WARNING"):
            self.assertEqual(0, utils.getInt("1.5"))

    def test_keywords_and_their_aliases(self) -> None:
        self.assertEqual("row-reverse", utils.getFlexDirection("Row-Reverse"))
        self.assertEqual("wrap", utils.getFlexWrap("wrap"))
        self.assertEqual("flex-start", utils.getFlexJustify("start"))
        self.assertEqual("flex-end", utils.getFlexJustify("right"))
        self.assertEqual("space-evenly", utils.getFlexJustify("space-evenly"))
        self.assertEqual("flex-start", utils.getFlexAlign("self-start"))
        self.assertEqual("stretch", utils.getFlexAlign("normal"))
        self.assertEqual("auto", utils.getFlexAlign("auto"))

    def test_an_unknown_keyword_is_the_initial_value(self) -> None:
        utils._value_warned.clear()
        with self.assertLogs("xhtml2pdf.util", level="WARNING") as logs:
            self.assertEqual("row", utils.getFlexDirection("sideways"))
        self.assertIn("sideways", logs.output[0])

    def test_baseline_is_a_value_of_its_own(self) -> None:
        utils._value_warned.clear()
        with self.assertNoLogs("xhtml2pdf.util", level="WARNING"):
            self.assertEqual("baseline", utils.getFlexAlign("baseline"))
            self.assertEqual("baseline", utils.getFlexAlign("first baseline"))

    def test_last_baseline_is_drawn_as_flex_end_and_says_so(self) -> None:
        utils._value_warned.clear()
        with self.assertLogs("xhtml2pdf.util", level="WARNING") as logs:
            self.assertEqual("flex-end", utils.getFlexAlign("last baseline"))
        self.assertIn("last baseline", logs.output[0])
        self.assertIn("flex-end", logs.output[0])


class GetDisplayTest(TestCase):
    """
    One place that says what every display value means to this library.

    Before it the property was compared with "block" and "none" and nothing
    else, so display: table on a div did not even make it a block, and
    display: flex was text run into the parent's paragraph.
    """

    def test_the_modes_this_library_lays_out(self) -> None:
        D = utils.Display
        self.assertEqual(D.BLOCK, utils.getDisplay("block"))
        self.assertEqual(D.INLINE, utils.getDisplay("inline"))
        self.assertEqual(D.INLINE_BLOCK, utils.getDisplay("inline-block"))
        self.assertEqual(D.FLEX, utils.getDisplay("flex"))
        self.assertEqual(D.FLEX, utils.getDisplay("inline-flex"))
        self.assertEqual(D.NONE, utils.getDisplay("none"))

    def test_other_block_level_values_are_blocks(self) -> None:
        for value in ("table", "list-item", "flow-root", "grid", "table-cell"):
            with self.subTest(value=value):
                self.assertEqual(utils.Display.BLOCK, utils.getDisplay(value))

    def test_case_and_whitespace_do_not_matter(self) -> None:
        self.assertEqual(utils.Display.BLOCK, utils.getDisplay(" Block "))

    def test_an_unknown_value_is_inline_and_says_so_once(self) -> None:
        utils._value_warned.discard(("display", "ruby"))
        with self.assertLogs("xhtml2pdf.util", level="WARNING") as logs:
            self.assertEqual(utils.Display.INLINE, utils.getDisplay("ruby"))
        self.assertIn("ruby", logs.output[0])
        with self.assertNoLogs("xhtml2pdf.util", level="WARNING"):
            utils.getDisplay("ruby")


class GetBorderRadiusTest(TestCase):
    def test_one_value_serves_both_axes(self) -> None:
        radius = utils.getBorderRadius([("4", "pt")])
        self.assertEqual((4, 4), radius.resolve(100, 50))

    def test_two_values_are_horizontal_then_vertical(self) -> None:
        radius = utils.getBorderRadius([("4", "pt"), ("8", "pt")])
        self.assertEqual((4, 8), radius.resolve(100, 50))

    def test_a_percentage_waits_for_the_box(self) -> None:
        radius = utils.getBorderRadius([("50", "%")], 10)
        self.assertEqual("percent", radius.h.kind)
        self.assertEqual((50, 25), radius.resolve(100, 50))

    def test_em_is_the_font_size(self) -> None:
        radius = utils.getBorderRadius([("2", "em")], 10)
        self.assertEqual((20, 20), radius.resolve(100, 50))

    def test_a_zero_axis_makes_the_corner_square(self) -> None:
        radius = utils.getBorderRadius([("4", "pt"), "0"])
        self.assertEqual((0, 0), radius.resolve(100, 50))

    def test_an_invalid_value_is_no_radius(self) -> None:
        with self.assertLogs("xhtml2pdf.util", level="WARNING"):
            self.assertIs(utils.NO_RADIUS, utils.getBorderRadius(["auto"]))


def _radius(*values: float) -> utils.CornerRadius:
    """A corner radius in points: one value for both axes, or two."""
    h, v = (values[0], values[-1])
    return utils.CornerRadius(
        utils.CSSLength("length", h), utils.CSSLength("length", v)
    )


def _rounded(radius, **kwargs) -> _BoxStyle:
    """A style whose four corners have the same radius."""
    corners = {f"border{corner}Radius": radius for corner in utils.RADIUS_CORNERS}
    return _BoxStyle(**corners, **kwargs)


def _solid(width: float, color=None, **kwargs) -> dict:
    color = color or Color(0, 0, 1)
    return {
        f"border{side}{part}": value
        for side in ("Left", "Right", "Top", "Bottom")
        for part, value in (("Style", "solid"), ("Width", width), ("Color", color))
    } | kwargs


def _box(style, *geometry, **kwargs) -> utils.RoundedBox:
    box = utils.roundedBox(style, *geometry, **kwargs)
    assert box is not None
    return box


class RoundedBoxTest(TestCase):
    """The geometry every rounded painter shares."""

    def test_no_radius_is_no_rounded_box(self) -> None:
        self.assertIsNone(utils.roundedBox(_BoxStyle(), 0, 0, 100, 50))
        self.assertIsNone(utils.roundedBox(_rounded(utils.NO_RADIUS), 0, 0, 100, 50))
        self.assertIsNone(utils.roundedBox(_rounded(_radius(0)), 0, 0, 100, 50))

    def test_without_borders_the_box_is_the_outer_edge(self) -> None:
        box = _box(_rounded(_radius(8, 4)), 10, 20, 100, 50)
        self.assertEqual((10, 20, 100, 50), box[:4])
        self.assertEqual(((8, 4),) * 4, box.radii)

    def test_a_border_moves_the_outer_edge_out_by_half_its_width(self) -> None:
        box = _box(_rounded(_radius(8), **_solid(4)), 10, 20, 100, 50)
        self.assertEqual((8, 18, 104, 54), box[:4])

    def test_percentages_resolve_against_the_outer_edge(self) -> None:
        # With a 4pt border the outer edge is 104 x 44; the inner one would
        # give 50 x 20.
        percent = utils.CSSLength("percent", 50)
        style = _rounded(utils.CornerRadius(percent, percent), **_solid(4))
        box = _box(style, 0, 0, 100, 40)
        self.assertEqual(((52, 22),) * 4, box.radii)

    def test_radii_too_large_for_a_side_shrink_together(self) -> None:
        # css-backgrounds-3 5.5: 999 on a 40pt tall box is scaled to 20.
        box = _box(_rounded(_radius(999)), 0, 0, 100, 40)
        for rx, ry in box.radii:
            self.assertAlmostEqual(20, rx)
            self.assertAlmostEqual(20, ry)

    def test_the_corners_at_a_cut_are_square(self) -> None:
        box = _box(_rounded(_radius(8)), 0, 0, 100, 50, sides=("Left", "Right", "Top"))
        self.assertEqual(((8, 8), (8, 8), (0, 0), (0, 0)), box.radii)

    def test_a_square_corner_at_a_cut_does_not_shrink_the_others(self) -> None:
        # Four radii of 30 on a 50 tall box scale to 25; with the bottom cut
        # the top ones fit as they are.
        box = _box(_rounded(_radius(30)), 0, 0, 100, 50, sides=("Left", "Right", "Top"))
        self.assertEqual((30, 30), box.radii[0])

    def test_the_inner_edge_takes_the_border_widths_off_the_radii(self) -> None:
        style = _rounded(_radius(10), **_solid(4, borderLeftWidth=12, borderTopWidth=2))
        box = _box(style, 0, 0, 100, 50)
        x, y, w, h, radii = box.inset(1.0)
        # Top-left loses the left width across and the top width down;
        # 10 - 12 is below zero, so the corner is square.
        self.assertEqual((0, 0), radii[0])
        self.assertEqual((6, 8), radii[1])
        self.assertEqual((6, 6), radii[2])

    def test_the_middle_of_the_border_is_the_box_passed_in(self) -> None:
        box = _box(_rounded(_radius(10), **_solid(4)), 10, 20, 100, 50)
        x, y, w, h, radii = box.inset(0.5)
        self.assertEqual((10, 20, 100, 50), (x, y, w, h))
        self.assertEqual(((8, 8),) * 4, radii)


class _PathCanvas:
    """
    A real canvas whose paths are recorded, operator by operator.

    Rounded boxes build paths with beginPath, which the plain recorder cannot
    answer; this keeps ReportLab's own path objects and records what is done
    with them.
    """

    def __init__(self) -> None:
        from io import BytesIO

        from reportlab.pdfgen.canvas import Canvas

        self._canvas = Canvas(BytesIO())
        self.calls: list[tuple] = []

    def beginPath(self):
        return self._canvas.beginPath()

    def __getattr__(self, name):
        def record(*args, **kwargs):
            args = tuple(
                arg.getCode() if hasattr(arg, "getCode") else arg for arg in args
            )
            self.calls.append((name, args, kwargs))

        return record

    def named(self, name: str) -> list[tuple]:
        return [call for call in self.calls if call[0] == name]


class RoundedPaintingTest(TestCase):
    def test_a_rounded_background_fills_a_curved_path(self) -> None:
        canvas = _PathCanvas()
        style = _rounded(_radius(8), backColor=Color(1, 0, 0))
        utils.drawBoxBackground(canvas, 0, 0, 100, 50, style)
        self.assertEqual([], canvas.named("rect"))
        ((_, (code,), kwargs),) = canvas.named("drawPath")
        self.assertEqual(4, code.count(" c"))
        self.assertEqual({"fill": 1, "stroke": 0}, kwargs)

    def test_a_uniform_solid_border_is_one_ring(self) -> None:
        canvas = _PathCanvas()
        utils.drawBoxBorders(canvas, 0, 0, 100, 50, _rounded(_radius(8), **_solid(2)))
        self.assertEqual([], canvas.named("clipPath"))
        ((_, (code,), kwargs),) = canvas.named("drawPath")
        # The outer edge and the inner one, filled even-odd.
        self.assertEqual(2, code.count(" m"))
        self.assertEqual(utils.FILL_EVEN_ODD, kwargs["fillMode"])

    def test_a_double_border_is_two_rings(self) -> None:
        canvas = _PathCanvas()
        style = _rounded(
            _radius(8),
            **_solid(
                6,
                **{
                    f"border{s}Style": "double"
                    for s in ["Top", "Left", "Right", "Bottom"]
                },
            ),
        )
        utils.drawBoxBorders(canvas, 0, 0, 100, 50, style)
        self.assertEqual(2, len(canvas.named("drawPath")))

    def test_a_dashed_border_is_stroked(self) -> None:
        canvas = _PathCanvas()
        style = _rounded(
            _radius(8),
            **_solid(
                3,
                **{
                    f"border{s}Style": "dashed"
                    for s in ["Top", "Left", "Right", "Bottom"]
                },
            ),
        )
        utils.drawBoxBorders(canvas, 0, 0, 100, 50, style)
        self.assertEqual(1, len(canvas.named("setDash")))
        ((_, _, kwargs),) = canvas.named("drawPath")
        self.assertEqual({"fill": 0, "stroke": 1}, kwargs)

    def test_sides_that_differ_are_each_clipped_to_their_wedge(self) -> None:
        canvas = _PathCanvas()
        style = _rounded(_radius(8), **_solid(2, borderTopColor=Color(1, 0, 0)))
        utils.drawBoxBorders(canvas, 0, 0, 100, 50, style)
        self.assertEqual(4, len(canvas.named("clipPath")))
        self.assertEqual(4, len(canvas.named("drawPath")))

    def test_a_side_with_no_border_is_not_painted(self) -> None:
        canvas = _PathCanvas()
        style = _rounded(_radius(8), **_solid(2, borderLeftStyle="none"))
        utils.drawBoxBorders(canvas, 0, 0, 100, 50, style)
        self.assertEqual(3, len(canvas.named("drawPath")))

    def test_the_sides_at_a_cut_are_not_painted(self) -> None:
        canvas = _PathCanvas()
        utils.drawBoxBorders(
            canvas,
            0,
            0,
            100,
            50,
            _rounded(_radius(8), **_solid(2)),
            sides=("Left", "Right", "Top"),
        )
        self.assertEqual(3, len(canvas.named("drawPath")))
