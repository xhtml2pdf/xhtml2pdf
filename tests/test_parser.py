import base64
import os
import re
from pathlib import Path
from unittest import TestCase
from xml.dom import minidom

from xhtml2pdf import properties
from xhtml2pdf.context import pisaContext
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
