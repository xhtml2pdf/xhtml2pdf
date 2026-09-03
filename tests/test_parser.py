import base64
import io
import os
import re
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from xml.dom import minidom

from pypdf import PdfReader
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4, A5
from reportlab.platypus.flowables import KeepInFrame

from xhtml2pdf import pisa, properties
from xhtml2pdf.context import PageNumberText, pisaContext, pisaCSSBuilder
from xhtml2pdf.default import DEFAULT_PAGE_NAME
from xhtml2pdf.document import pisaStory
from xhtml2pdf.parser import getCSSAttrCacheKey, pisaParser
from xhtml2pdf.properties import (
    CSS_PROPERTIES,
    FRAG_BLOCK_GROUPS,
    LOOP_GROUPS,
    PROPERTY_NAMES,
    SUPPORTED_PROPERTIES,
    CSSAttrs,
)

#: The two literal blocks in the reference documentation that list properties.
_DOCS = Path(__file__).parent.parent / "docs" / "source" / "reference" / "html.rst"
_DOC_SECTIONS = (
    "xhtml2pdf supports the following standard CSS properties",
    "xhtml2pdf adds the following vendor-specific properties:",
)


def _documented_properties() -> set:
    """The property names the reference documentation lists."""
    text = _DOCS.read_text(encoding="utf-8")
    names = set()
    for heading in _DOC_SECTIONS:
        body = text.split(heading, 1)[1].split("::", 1)[1]
        # The literal block runs until the first line that is not indented.
        for line in body.splitlines()[1:]:
            if line.strip() and not line.startswith(" "):
                break
            names.update(re.findall(r"[-a-z][-a-z0-9]*", line))
    return names


_data = b"""
<!doctype html>
<html>
<title>TITLE</title>
<body>
BODY
</body>
</html>
"""


class ParserTest(TestCase):
    def testParser(self) -> None:
        c = pisaContext(".")
        r = pisaParser(_data, c)
        self.assertEqual(c, r)
        self.assertEqual(r.err, 0)
        self.assertEqual(r.warn, 0)

    def test_getFile(self) -> None:
        c = pisaContext(".")
        r = pisaParser(_data, c)
        self.assertEqual(c.getFile(None), None)
        self.assertEqual(r.err, 0)
        self.assertEqual(r.warn, 0)

    def test_height_as_list(self) -> None:
        """Asserts attributes like 'height: 10px !important" are parsed"""
        c = pisaContext(".")
        data = b"<p style='height: 10px !important;width: 10px !important'>test</p>"
        r = pisaParser(data, c)
        self.assertEqual(c, r)
        self.assertEqual(r.err, 0)
        self.assertEqual(r.warn, 0)

    def test_image_os_path(self) -> None:
        c = pisaContext(".")
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        img_path = os.path.join(tests_folder, "samples", "img", "denker.png")
        data = f'<img src="{img_path}">'.encode()
        r = pisaParser(data, c)
        self.assertEqual(c, r)
        self.assertEqual(r.err, 0)
        self.assertEqual(r.warn, 0)

    def test_image_base64(self) -> None:
        c = pisaContext(".")
        data = (
            b"<img"
            b' src="data:image/gif;base64,R0lGODlhAQABAIAAAAUEBAAAACwAAAAAAQABAAACAkQBADs=">'
        )
        r = pisaParser(data, c)
        self.assertEqual(r.warn, 0)

    def test_image_base64_params(self) -> None:
        c = pisaContext(".")
        data = (
            b"<img"
            b' src="data:image/gif;foo=bar;base64,R0lGODlhAQABAIAAAAUEBAAAACwAAAAAAQABAAACAkQBADs=">'
        )
        r = pisaParser(data, c)
        self.assertEqual(r.warn, 0)

    def test_image_base64_urlencoded(self) -> None:
        c = pisaContext(".")
        data = (
            b"<img"
            b' src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAV4AAACWBAMAAABkyf1EAAAAG1BMVEXMzMyWlpacnJyqqqrFxcWxsbGjo6O3t7e%2Bvr6He3KoAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAEcElEQVR4nO2aTW%2FbRhCGh18ij1zKknMkbbf2UXITIEeyMhIfRaF1exQLA%2FJRclslRykO%2Brs7s7s0VwytNmhJtsA8gHZEcox9PTs7uysQgGEYhmEYhmEYhmEYhmEYhmEYhmEYhmEYhmEYhmEYhmGYr2OWRK%2FReIKI8Zt7Hb19wTcQ0uTkGh13bQupcw7gPOvdo12%2F5CzNtNR7xLUtNtT3CGBQ6g3InjY720pvofUec22LJPr8PhEp2OMPyI40PdwWUdronCu9yQpdPx53bQlfLKnfOVhlnDYRBXve4Ov%2BIZTeMgdedm0NR%2BxoXJeQvdJ3CvziykSukwil16W%2FOe7aGjIjqc%2F9ib4jQlJy0uArtN4A0%2BcvXFvDkmUJ47sJ1Y1ATLDNVXZkNPIepQzxy1ki9fqiwbUj%2FI%2B64zxWNzyZnPuhvohJ9K70VvXBixpcu2SAHU%2BXd9EKdEJDNpYP3AQr3bQSpPQ6Y6%2F4dl1z7ZDbArsszjA7L0g7ibB0CDcidUWVoErvIMKZh2Xs0LUzcLW6V5NfiUgNEbaYmAVL6bXl0nJRc%2B1S72ua%2FD%2FcTjGPlQj7eUqd7A096rYlRjdPYlhz7VIvxpVG3cemDKF%2BWAwLY%2F6XelOZKTXXzsC4xvDjjtSN6kHLhLke6PrwM8h1raf40qjrGO7H9aTEbduucjS04ZrYU%2F4iuS5Z2Hdt0rvCLFdmLEXcU30AGddST62o%2BsLcf5l6k7CP%2Bru4pLYqX%2FVFyxbm%2FutQbx%2Fr22ZEbTb2f5I2kns1Y1OQR8ZyofX%2BTjJxj1Rz7QQVnf1QzR26Oth0ueJVYcRP6ZUPac%2FRx%2F5M6ixO1dhSrT3Y1DpiYmx3tF4ZUdpz9LD%2FdSg9PXES0LB71BwcGjKROuV28lnvnv7HHJsezheBGH5%2BX2CfSfRbMKW%2B5aGs3JFjMrjGibJc0S7TJzqjHrh2hDybj9XRXNZa89Aro55XBdbW5wti2c%2F5WJ7jJ1RolVUn%2FHWpb0I58Tziup6Rx7Dm2hnbRP1GM9PW%2FNFmQ4PtVRVN63Wvxfmu5sowDMMwDMMwDMMwDMMwDMMwDMMwzL%2BCpT%2F%2FF%2F6beoV8zb2Jmt4Qryx6lTUCsENQ75HOkhXAO3EPVgyQtKtUy3C%2Fe%2BFJg17Zjnew1Xrdb9InbG4WqfUAftG%2BWhLwPVyfg536%2BMU7m4C1CMk4ZznpXZzDYI1PDL2nS1hpvc5cNd7E2sJg05Fe7%2F7d3Fln8Cvc3bwB616auxsKl4WPghjemHrDqyDWeu1UNW5s2btPnSQ75oOdunEwWazfwgVG0kqluYCM9OIjWOGnfA2b9G4Ha63XKpvQ8perTvTifJNhi6%2BWMWmi7smEZf6G8MmhlyGq%2BNqP8GV84TLuJr7UIQVx%2BbDEoEpRZIz42gs40OuN4Mv8hXzelV7KX1isH%2BewTWckikyVv%2BCfHuqVF7I16gN0VKypX6wPsE%2BzFPzkinolU9UH8OMGvSpnZqKsv13p%2FRsMun6X5x%2Fy2LeAr8O66lsBwzBMP%2FwJfyGq8pgBk6IAAAAASUVORK5CYII%3D">'
        )
        r = pisaParser(data, c)
        self.assertEqual(r.warn, 0)

    def test_font_base64(self) -> None:
        ttf_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "samples",
            "font",
            "Noto_Sans",
            "NotoSans-Regular.ttf",
        )
        with open(ttf_path, "rb") as f:
            b64_font = base64.b64encode(f.read()).decode("ascii")
        c = pisaContext(".")

        data = b"""
          <style>
            @font-face {
              font-family: 'FontName';
              src: url('data:font/ttf;charset=utf-8;base64,%s');
            }
          </style>
        """ % b64_font.encode(
            "utf-8"
        )

        r = pisaParser(data, c)
        self.assertEqual(r.warn, 0)


class CSSFunctionValueTest(TestCase):
    """
    A CSS function as the value of a property xhtml2pdf implements.

    calc(), the gradients, hsl(), min()/clamp() and var() reach the cascade as
    a CSSTerminalFunction: neither a string nor a sequence, which is what every
    consumer in CSS2Frag treats the value as. Each of these aborted the whole
    conversion -- for CSS a browser renders without complaint -- instead of
    being ignored like everything else the library does not implement.
    """

    #: property, declaration, and the name the report should give it.
    CASES = (
        ("width", "width: calc(100% - 20pt)", "width: calc()"),
        ("height", "height: calc(10pt + 2pt)", "height: calc()"),
        ("zoom", "zoom: calc(1 + 1)", "zoom: calc()"),
        ("font-size", "font-size: calc(10pt + 2pt)", "font-size: calc()"),
        ("line-height", "line-height: calc(1em + 2pt)", "line-height: calc()"),
        ("letter-spacing", "letter-spacing: calc(1pt + 1pt)", "letter-spacing: calc()"),
        ("word-spacing", "word-spacing: calc(1pt + 1pt)", "word-spacing: calc()"),
        (
            "background-image",
            "background-image: linear-gradient(to right, #000, #fff)",
            "background-image: linear-gradient()",
        ),
        (
            "list-style-image",
            "list-style-image: linear-gradient(to right, #000, #fff)",
            "list-style-image: linear-gradient()",
        ),
        ("color", "color: hsl(120, 50%, 50%)", "color: hsl()"),
        ("color", "color: var(--brand, #000)", "color: var()"),
        ("width", "width: min(100pt, 50%)", "width: min()"),
        ("margin-left", "margin-left: clamp(1pt, 2pt, 3pt)", "margin-left: clamp()"),
    )

    @staticmethod
    def _parse(declaration: str) -> pisaContext:
        html = (
            f"<html><head><style>.x{{{declaration};}}</style></head>"
            "<body><p class='x'>x</p><ul class='x'><li>a</li></ul></body></html>"
        )
        return pisaParser(html.encode(), pisaContext("."))

    def test_a_function_value_is_dropped_and_named(self) -> None:
        for prop, declaration, reported in self.CASES:
            with self.subTest(declaration=declaration):
                context = self._parse(declaration)
                self.assertEqual(context.err, 0)
                self.assertIn(reported, context.cssDroppedFunctions)
                self.assertEqual(prop, reported.split(":")[0])

    def test_an_inline_style_is_covered_too(self) -> None:
        """An inline style="" never reaches the rulesets, only the cascade."""
        html = b"<html><body><p style='width: calc(100% - 20pt)'>x</p></body></html>"
        context = pisaParser(html, pisaContext("."))
        self.assertEqual(context.err, 0)
        self.assertIn("width: calc()", context.cssDroppedFunctions)

    def test_readable_functions_are_kept(self) -> None:
        """rgb() and rgba() are read by getColor and must survive the filter."""
        for declaration in ("color: rgb(10, 200, 10)", "color: rgba(10, 200, 10, .5)"):
            with self.subTest(declaration=declaration):
                context = self._parse(declaration)
                self.assertEqual(context.cssDroppedFunctions, set())


class FrameBorderDataTest(TestCase):
    """
    _getFromData is asked for a border by its four side names at once.

    The `return` used to sit inside the loop unconditionally, so only the first
    name was ever consulted: a @frame that declared border-left-width and
    nothing else got the default and drew no border at all.
    """

    SIDES = (
        "border-top-width",
        "border-bottom-width",
        "border-left-width",
        "border-right-width",
    )

    def test_any_declared_side_is_found(self) -> None:
        for side in self.SIDES:
            with self.subTest(side=side):
                found = pisaCSSBuilder._getFromData(
                    {side: "3pt"}, self.SIDES, "DEFAULT"
                )
                self.assertEqual(found, "3pt")

    def test_the_first_declared_side_wins(self) -> None:
        data = {"border-bottom-width": "2pt", "border-left-width": "3pt"}
        found = pisaCSSBuilder._getFromData(data, self.SIDES, "DEFAULT")
        self.assertEqual(found, "2pt")

    def test_no_declared_side_gives_the_default(self) -> None:
        found = pisaCSSBuilder._getFromData({}, self.SIDES, "DEFAULT")
        self.assertEqual(found, "DEFAULT")

    def test_an_empty_name_list_gives_the_default(self) -> None:
        self.assertEqual(pisaCSSBuilder._getFromData({}, (), "DEFAULT"), "DEFAULT")


class FrameBoundaryTest(TestCase):
    """
    -pdf-frame-border switches a frame's boundary on; the border-* rules say
    what it looks like.

    The two used to be exclusive: with the switch on, the declared colour and
    width were dropped for reportlab's black hairline. And the switch was read
    with int(), so a non-integer value, or a switch set on the @page rather
    than on the frame, aborted the conversion.
    """

    @staticmethod
    def boundary(border=None, page_border=None, color=None, width=0):
        return pisaCSSBuilder._frame_boundary(border, page_border, color, width)

    def test_nothing_declared_draws_nothing(self) -> None:
        """Falsy, and reportlab skips the boundary entirely."""
        self.assertFalse(self.boundary())

    def test_a_declared_border_draws_without_the_switch(self) -> None:
        boundary = self.boundary(color=Color(0, 0, 1), width=2)
        self.assertTrue(boundary)
        self.assertEqual(Color(0, 0, 1), boundary.color)
        self.assertEqual(2, boundary.width)

    def test_the_switch_alone_draws_a_black_line(self) -> None:
        boundary = self.boundary(border="1")
        self.assertEqual((0, 0, 0), boundary.color)
        self.assertEqual(1, boundary.width)

    def test_the_switch_keeps_a_declared_colour_and_width(self) -> None:
        boundary = self.boundary(border="1", color=Color(0.8, 0, 0), width=3)
        self.assertEqual(Color(0.8, 0, 0), boundary.color)
        self.assertEqual(3, boundary.width)

    def test_the_switch_may_be_set_on_the_page(self) -> None:
        """int(None) raised TypeError for a frame that did not set it."""
        boundary = self.boundary(border=None, page_border="1")
        self.assertTrue(boundary)
        self.assertEqual(1, boundary.width)

    def test_the_switch_need_not_be_an_integer(self) -> None:
        """int("1.5") raised ValueError."""
        self.assertEqual(1.5, self.boundary(border="1.5").width)

    def test_a_page_wide_switch_converts(self) -> None:
        """End-to-end: this is the form the documentation describes."""
        html = (
            "<html><head><style>"
            "@page { size: a5 portrait; -pdf-frame-border: 1;"
            "  @frame f { left: 10mm; right: 10mm; top: 10mm; bottom: 10mm; } }"
            "</style></head><body><p>x</p></body></html>"
        )
        self.assertEqual(0, pisaStory(html).err)


class PropertyRegistryTest(TestCase):
    """
    The registry is the single source of truth for which CSS properties this
    library reads. It replaced a whitespace-separated string that nothing
    checked, which is how -pdf-keep-in-frame-max-width came to be read in
    pisaLoop while never being collected, and how the reference documentation
    came to list "colordisplay" -- two property names run together.
    """

    def test_no_duplicate_names(self) -> None:
        names = list(PROPERTY_NAMES)
        self.assertEqual(sorted(names), sorted(set(names)))

    def test_registry_drives_collection(self) -> None:
        self.assertEqual(set(PROPERTY_NAMES), set(SUPPORTED_PROPERTIES))
        self.assertEqual(len(PROPERTY_NAMES), len(CSS_PROPERTIES))

    def test_a_registry_driven_mapping_is_complete(self) -> None:
        # frag says "the registry applies this one"; without a converter
        # transform_attrs would be handed None and fail at render time.
        for prop in CSS_PROPERTIES:
            if prop.frag is not None:
                self.assertIsNotNone(prop.convert, prop.name)

    def test_uniform_groups_cover_every_driven_property(self) -> None:
        driven = {p.name for p in CSS_PROPERTIES if p.frag is not None}
        grouped = {
            name
            for groups in (FRAG_BLOCK_GROUPS, LOOP_GROUPS)
            for group in groups
            for _frag, name in group.pairs
        }
        self.assertEqual(driven, grouped)

    def test_documentation_lists_exactly_the_registry(self) -> None:
        """
        docs/source/reference/html.rst and the registry must agree.

        The list in the documentation was hand-maintained and had drifted in
        both directions for years; this is what stops it drifting again.
        """
        documented = _documented_properties()
        registered = set(PROPERTY_NAMES)

        self.assertEqual(
            registered - documented, set(), "registered but not documented"
        )
        self.assertEqual(
            documented - registered, set(), "documented but not registered"
        )


class CSSAttrsTest(TestCase):
    def test_reading_a_registered_property_is_quiet(self) -> None:
        attrs = CSSAttrs({"color": "red"})
        with self.assertNoLogs("xhtml2pdf.properties", level="WARNING"):
            self.assertIn("color", attrs)
            self.assertEqual("red", attrs["color"])
            self.assertEqual("red", attrs.get("color"))

    def test_reading_an_unregistered_property_says_so(self) -> None:
        # The failure this makes loud: a branch reads a property nobody
        # collects, the membership test answers False, and the feature
        # silently does nothing.
        properties._unregistered_seen.discard("float")
        attrs = CSSAttrs()
        with self.assertLogs("xhtml2pdf.properties", level="WARNING") as logs:
            self.assertNotIn("float", attrs)
        self.assertIn("float", logs.output[0])


class CSSAttrCacheKeyTest(TestCase):
    """
    The key used to be "#".join(parent, tag, class, id, style), which is
    ambiguous: the separator can appear inside a value.
    """

    @staticmethod
    def _element(html: str):
        return minidom.parseString(html).getElementsByTagName("p")[0]

    def test_the_separator_case_no_longer_collides(self) -> None:
        # As strings these two built the identical key "…#p##x#color:#fff".
        a = self._element('<div><p id="x" style="color:#fff">t</p></div>')
        b = self._element('<div><p id="x#color:" style="fff">t</p></div>')

        self.assertNotEqual(getCSSAttrCacheKey(a), getCSSAttrCacheKey(b))

    def test_same_shape_shares_a_key(self) -> None:
        document = minidom.parseString(
            '<div><p class="a">one</p><p class="a">two</p></div>'
        )
        first, second = document.getElementsByTagName("p")

        self.assertEqual(getCSSAttrCacheKey(first), getCSSAttrCacheKey(second))

    def test_position_separates_siblings_when_a_rule_asks(self) -> None:
        document = minidom.parseString(
            '<div><p class="a">one</p><p class="a">two</p></div>'
        )
        first, second = document.getElementsByTagName("p")

        self.assertNotEqual(
            getCSSAttrCacheKey(first, {"p"}), getCSSAttrCacheKey(second, {"p"})
        )


class CSSAttrCacheTest(TestCase):
    def test_the_cache_belongs_to_the_render(self) -> None:
        """
        It used to be a module global reset with `global` at the top of every
        parse, so concurrent renders shared it and entries outlived the
        document that filled them.
        """
        first, second = pisaContext("."), pisaContext(".")
        pisaParser(b"<p>one</p>", first)
        pisaParser(b"<p>two</p>", second)

        self.assertTrue(first.cssAttrCache)
        self.assertTrue(second.cssAttrCache)
        self.assertFalse(set(first.cssAttrCache) & set(second.cssAttrCache))


class InlineOnlyPropertyTest(TestCase):
    def test_a_property_only_ever_declared_inline_still_applies(self) -> None:
        """
        CSSCascadeStrategy skips the ruleset search for a property no rule
        mentions. An inline style is consulted after that search, so it must
        survive the shortcut.
        """
        context = pisaContext(".")
        # letter-spacing appears in no stylesheet, only in the style attribute.
        pisaParser(b'<p style="letter-spacing: 3px">spaced</p>', context)

        self.assertNotIn("letter-spacing", context.cssCascade.propertyNames)
        self.assertEqual("3px", "".join(context.fragList[0].letterSpacing))


class PseudoPageTest(TestCase):
    """
    A pseudo page written without a name -- "@page :left", which is how CSS
    paged media spells it -- belongs to the page a plain @page defines.

    The parser used to build the template name with `page + "_" + pseudopage`,
    and `page` is None in that form, so every one of :left, :right, :first and
    :blank aborted the conversion with a TypeError before anything was drawn.
    """

    @staticmethod
    def story(css: str):
        return pisaStory(
            f"<html><head><style>{css}</style></head><body><p>x</p></body></html>"
        )

    def test_an_unnamed_pair_converts(self) -> None:
        context = self.story("@page :left { size: a5; } @page :right { size: a5; }")

        self.assertEqual(0, context.err)

    def test_an_unnamed_pair_belongs_to_the_default_page(self) -> None:
        context = self.story("@page :left { size: a5; } @page :right { size: a5; }")

        self.assertIn(f"{DEFAULT_PAGE_NAME}_left", context.templateList)
        self.assertIn(f"{DEFAULT_PAGE_NAME}_right", context.templateList)

    def test_a_named_pair_is_unaffected(self) -> None:
        context = self.story("@page b:left { size: a5; } @page b:right { size: a5; }")

        self.assertIn("b_left", context.templateList)
        self.assertIn("b_right", context.templateList)

    def test_an_unsupported_pseudo_says_so(self) -> None:
        """:first has no equivalent here, and used to crash rather than say it."""
        with self.assertLogs("xhtml2pdf", level="WARNING") as logged:
            context = self.story("@page :first { size: a5; }")

        self.assertEqual(0, context.err)
        self.assertTrue(
            any("Unsupported pseudo page :first" in line for line in logged.output),
            logged.output,
        )


class PageSizeTest(TestCase):
    """
    An unreadable `size` used to raise RuntimeError, which is the only value in
    a stylesheet that threw the document away instead of being dropped.
    """

    @staticmethod
    def size(css: str):
        html = f"<html><head><style>{css}</style></head><body><p>x</p></body></html>"
        return pisaStory(html).pageSize

    def test_an_unknown_size_keeps_the_current_one(self) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING") as logged:
            size = self.size("@page { size: banana; }")

        self.assertEqual(A4, size)
        self.assertTrue(
            any("Unknown size value" in line for line in logged.output), logged.output
        )

    def test_a_known_size_still_wins_over_a_bad_one(self) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING"):
            self.assertEqual(A5, self.size("@page { size: a5 banana; }"))

    def test_a_known_size_warns_about_nothing(self) -> None:
        with self.assertNoLogs("xhtml2pdf", level="WARNING"):
            self.assertEqual(A5, self.size("@page { size: a5; }"))


class DefaultFrameTest(TestCase):
    """
    A @page with no @frame at all gets a default content frame, which is the
    normal way to write a document. It used to warn about it every time, and
    the message -- "missing explicit frame definition for content or just
    static frames" -- describes a different situation: static frames declared
    with nowhere for the story to go.
    """

    @staticmethod
    def story(css: str):
        return pisaStory(
            f"<html><head><style>{css}</style></head>"
            "<body><div id='hd'>h</div><p>x</p></body></html>"
        )

    def test_no_frames_at_all_is_not_worth_a_warning(self) -> None:
        with self.assertNoLogs("xhtml2pdf", level="WARNING"):
            self.story("@page { size: a5; }")

    def test_static_frames_without_a_content_frame_still_warn(self) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING") as logged:
            self.story(
                "@page { size: a5; @frame h { -pdf-frame-content: hd;"
                " left: 5mm; right: 5mm; top: 5mm; height: 10mm; } }"
            )

        self.assertTrue(
            any("missing explicit frame" in line for line in logged.output),
            logged.output,
        )


class StaticFrameKeepInFrameTest(TestCase):
    """
    -pdf-keep-in-frame-mode on the element a static frame draws wraps that
    element's whole content.

    The story index the wrapper is built from used to be taken before the
    static block swapped the story, so it pointed into the story the block
    interrupted. With anything ahead of the static div in the body, the first
    flowables of the header escaped the KeepInFrame.
    """

    CSS = (
        "@page { size: a5;"
        " @frame h { -pdf-frame-content: hd; left: 5mm; right: 5mm;"
        " top: 5mm; height: 10mm; }"
        " @frame b { left: 5mm; right: 5mm; top: 20mm; bottom: 5mm; } }"
    )

    def static_story(self, before: str) -> list:
        context = pisaStory(
            f"<html><head><style>{self.CSS}</style></head><body>{before}"
            "<div id='hd' style='-pdf-keep-in-frame-mode: shrink'>"
            "<p>one</p><p>two</p><p>three</p></div>"
            "<p>body</p></body></html>"
        )
        [frame] = context.frameStatic["hd"]
        return frame.pisaStaticStory

    def test_the_whole_static_block_is_wrapped(self) -> None:
        self.assertEqual(1, len(self.static_story("")))

    def test_content_ahead_of_the_block_does_not_shift_the_wrapper(self) -> None:
        story = self.static_story("<p>a</p><p>b</p><p>c</p>")

        self.assertEqual(1, len(story))
        self.assertIsInstance(story[0], KeepInFrame)


class ImportedStylesheetTest(TestCase):
    """
    A url() inside a stylesheet is relative to that stylesheet.

    The root path an imported sheet resolves against used to be derived from
    the uri as written -- "fonts.css" -- and Path("fonts.css").parent.resolve()
    is the process working directory, so a @font-face inside an imported sheet
    never found its file. A sheet reached through <link> has the same problem
    one level up, because pisaPreLoop turns it into an @import: it only worked
    when the process happened to run from the directory of the HTML.

    An import that cannot be read used to reach the parser as None and leave a
    ten-line traceback in the log rather than one readable line.
    """

    FONT = (
        Path(__file__).parent
        / "samples"
        / "font"
        / "Noto_Sans"
        / "NotoSans-Regular.ttf"
    )

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "css").mkdir()
        shutil.copy(self.FONT, self.root / "css" / "font.ttf")
        (self.root / "css" / "fonts.css").write_text(
            '@font-face { font-family: "Probe"; src: url("font.ttf"); }'
        )
        (self.root / "css" / "main.css").write_text(
            '@import url("fonts.css");\nbody { font-family: "Probe"; }'
        )
        (self.root / "css" / "direct.css").write_text(
            '@font-face { font-family: "Direct"; src: url("font.ttf"); }\n'
            'body { font-family: "Direct"; }'
        )
        # Somewhere that is not the directory holding the document, which is
        # the whole point: running from there used to hide half of this.
        self.cwd = os.getcwd()
        os.chdir(tempfile.gettempdir())

    def tearDown(self) -> None:
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def convert(self, sheet: str):
        page = self.root / "page.html"
        page.write_text(
            f'<html><head><link rel="stylesheet" href="css/{sheet}"></head>'
            "<body><p>x</p></body></html>"
        )
        return pisaStory(page.read_text(), path=str(page))

    def test_a_font_face_in_a_linked_sheet_is_found(self) -> None:
        self.assertIn("direct", self.convert("direct.css").fontList)

    def test_a_font_face_in_an_imported_sheet_is_found(self) -> None:
        self.assertIn("probe", self.convert("main.css").fontList)

    def test_an_unreadable_import_says_so_once(self) -> None:
        (self.root / "css" / "broken.css").write_text('@import url("nope.css");')

        with self.assertLogs("xhtml2pdf", level="WARNING") as logged:
            context = self.convert("broken.css")

        self.assertEqual(0, context.err)
        self.assertTrue(
            any(
                "Could not read the imported stylesheet" in line
                for line in logged.output
            ),
            logged.output,
        )
        self.assertFalse(
            any("Traceback" in line for line in logged.output), logged.output
        )


class ListTypeAttributeTest(TestCase):
    """
    <ol type="a"> and <ul type="square"> choose the counter.

    Both attributes were declared in TAGS and parsed, and then nothing read
    them: only list-style-type in a stylesheet had any effect.
    """

    @staticmethod
    def markers(html: str) -> str:
        dest = io.BytesIO()
        result = pisa.pisaDocument(
            io.StringIO(f"<html><body>{html}</body></html>"), dest
        )
        assert result.err == 0
        dest.seek(0)
        return (PdfReader(dest).pages[0].extract_text() or "").replace("\n", " ")

    ITEMS = "<li>one</li><li>two</li>"

    def test_lower_alpha(self) -> None:
        self.assertIn("a.", self.markers(f'<ol type="a">{self.ITEMS}</ol>'))

    def test_upper_alpha(self) -> None:
        """The parsed attribute is lowercased, so the case comes from the DOM."""
        self.assertIn("A.", self.markers(f'<ol type="A">{self.ITEMS}</ol>'))

    def test_upper_roman(self) -> None:
        self.assertIn("II.", self.markers(f'<ol type="I">{self.ITEMS}</ol>'))

    def test_a_list_without_the_attribute_is_unchanged(self) -> None:
        self.assertIn("1.", self.markers(f"<ol>{self.ITEMS}</ol>"))

    def test_a_stylesheet_still_decides_when_nothing_is_declared(self) -> None:
        self.assertIn(
            "ii.",
            self.markers(f'<ol style="list-style-type: lower-roman">{self.ITEMS}</ol>'),
        )

    def test_a_square_bullet(self) -> None:
        self.assertIn("■", self.markers(f'<ul type="square">{self.ITEMS}</ul>'))


class PageNumberExampleTest(TestCase):
    """
    <pdf:pagenumber example=""> is what the line is measured with until the
    page number is known. The attribute was declared and never read, so the
    line was laid out as if the number were not there.
    """

    def test_the_example_is_what_it_starts_with(self) -> None:
        self.assertEqual("88", PageNumberText("88").data)

    def test_without_one_it_starts_empty(self) -> None:
        self.assertEqual("", PageNumberText().data)

    def test_the_example_does_not_reach_the_page(self) -> None:
        html = (
            "<html><head><style>@page { size: a5;"
            " @frame f { -pdf-frame-content: foot; left: 10mm; right: 10mm;"
            " bottom: 10mm; height: 10mm; }"
            " @frame b { left: 10mm; right: 10mm; top: 10mm; bottom: 25mm; } }"
            "</style></head><body>"
            '<div id="foot"><p>page <pdf:pagenumber example="88"></p></div>'
            "<p>x</p></body></html>"
        )
        dest = io.BytesIO()
        pisa.pisaDocument(io.StringIO(html), dest)
        dest.seek(0)

        text = PdfReader(dest).pages[0].extract_text() or ""
        self.assertIn("page 1", text)
        self.assertNotIn("88", text)
