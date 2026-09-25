"""
The CSS parser on its own: the at-rules, selectors and declarations that no
document in the rest of the suite happens to contain, and the errors it
reports. Several of these used to raise something other than a CSSParseError
-- an IndexError, a TypeError, an AttributeError -- which nothing catches, so
one line of a stylesheet cost the whole document.
"""

import logging
import tempfile
from pathlib import Path
from typing import ClassVar
from unittest import TestCase
from xml.dom import minidom

from xhtml2pdf.context import pisaContext
from xhtml2pdf.w3c.css import CSSBuilder, CSSParser
from xhtml2pdf.w3c.cssDOMElementInterface import CSSDOMElementInterface
from xhtml2pdf.w3c.cssParser import CSSParseError


class ParserTestCase(TestCase):
    MEDIUM_SET: ClassVar[list[str]] = ["all", "print", "pdf"]

    def setUp(self) -> None:
        # The parser warns about every rule it drops, which is what most of
        # these tests do on purpose.
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)

    def _parser(self) -> CSSParser:
        return CSSParser(CSSBuilder(mediumSet=self.MEDIUM_SET))

    def _parse(self, css: str) -> dict:
        ruleset = self._parser().parse(css)[0]
        return {str(selector): dict(decls) for selector, decls in ruleset.items()}


class ParseErrorTest(ParserTestCase):
    def test_message_points_at_the_error_in_its_context(self) -> None:
        error = CSSParseError("Bad thing", "bc", "abc")
        self.assertEqual("Bad thing:: ('a', 'bc')", str(error))

    def test_message_without_a_position_quotes_the_source(self) -> None:
        # At the very start of its context, or not found in it at all.
        self.assertEqual("Bad:: 'abc'", str(CSSParseError("Bad", "abc")))
        self.assertEqual("Bad:: 'zzz'", str(CSSParseError("Bad", "zzz", "abc")))
        self.assertEqual("Bad:: ''", str(CSSParseError("Bad", "")))

    def test_full_source_is_located_and_decoded(self) -> None:
        error = CSSParseError("Bad", "b", "abc")
        error.setFullCSSSource(b"xxabc", inline=True)

        self.assertEqual("xxabc", error.fullsrc)
        self.assertTrue(error.inline)
        self.assertEqual(3, error.srcFullIdx)
        self.assertEqual(2, error.ctxsrcFullIdx)

    def test_full_source_that_does_not_contain_the_error(self) -> None:
        error = CSSParseError("Bad", "q", "abc")
        error.setFullCSSSource("xyz")

        self.assertIsNone(error.srcFullIdx)
        self.assertIsNone(error.ctxsrcFullIdx)

    def test_parse_attaches_the_stylesheet(self) -> None:
        with self.assertRaises(CSSParseError) as caught:
            self._parser().parse("@import foo;")
        self.assertEqual("@import foo;", caught.exception.fullsrc)
        self.assertIn("Import expecting string or url", str(caught.exception))


class PublicApiTest(ParserTestCase):
    def test_parse_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "style.css")
            path.write_text("p { color: red; }", encoding="utf-8")
            ruleset = self._parser().parseFile(str(path))[0]

        self.assertEqual(
            {"p": {"color": "red"}},
            {str(selector): dict(decls) for selector, decls in ruleset.items()},
        )

    def test_parse_inline_error_carries_the_attribute(self) -> None:
        with self.assertRaises(CSSParseError) as caught:
            self._parser().parseInline("width: calc(1px ; color: red")
        self.assertIn("expected closing ')'", str(caught.exception))
        self.assertEqual("width: calc(1px ; color: red", caught.exception.fullsrc)
        self.assertTrue(caught.exception.inline)

    def test_parse_attributes(self) -> None:
        normal, important = self._parser().parseAttributes(
            {"color": "red"}, font="10px Arial"
        )
        self.assertEqual({}, dict(important))
        self.assertEqual("red", normal["color"])
        self.assertEqual(("10", "px"), normal["font-size"])
        self.assertEqual(["Arial"], normal["font-family"])

    def test_parse_attributes_error(self) -> None:
        with self.assertRaises(CSSParseError) as caught:
            self._parser().parseAttributes(width="calc(1px ;")
        self.assertTrue(caught.exception.inline)

    def test_parse_single_attribute(self) -> None:
        parser = self._parser()
        self.assertEqual(
            [("110", "%"), "Times New Roman", "Arial"],
            parser.parseSingleAttr('110%, "Times New Roman", Arial'),
        )
        # An !important value comes back from the other half of the result.
        self.assertEqual("red", parser.parseSingleAttr("red !important"))


class AtRuleTest(ParserTestCase):
    def test_html_comment_markers_are_ignored(self) -> None:
        self.assertEqual({"p": {"color": "red"}}, self._parse("<!-- p{color:red} -->"))

    def test_charset(self) -> None:
        self.assertEqual(
            {"p": {"color": "red"}}, self._parse('@charset "utf-8"; p{color:red}')
        )

    def test_charset_without_semicolon(self) -> None:
        # Used to raise AttributeError: the parser has no ctxsrc of its own.
        with self.assertRaisesRegex(CSSParseError, "@charset expected a terminating"):
            self._parse('@charset "utf-8" p{color:red}')

    def test_import_errors(self) -> None:
        with self.assertRaisesRegex(CSSParseError, "Import expecting string or url"):
            self._parse("@import foo; p{color:red}")
        with self.assertRaisesRegex(CSSParseError, "@import expected a terminating"):
            self._parse("@import 'x.css' print p{color:red}")

    def _imports(self, css: str) -> tuple[list, set]:
        """The stylesheets css imports, and the rules it keeps."""
        imported = []

        class Parser(CSSParser):
            @staticmethod
            def parseExternal(cssResourceName):
                imported.append(cssResourceName)

        parser = Parser(CSSBuilder(mediumSet=self.MEDIUM_SET))
        ruleset = parser.parse(css)[0]
        return imported, {str(selector) for selector in ruleset}

    def test_import_media_list(self) -> None:
        self.assertEqual(
            (["x.css"], {"p"}), self._imports("@import 'x.css' print, screen; p{c:d}")
        )
        # None of the media apply, so the file is not even fetched.
        self.assertEqual(
            ([], {"p"}), self._imports("@import 'x.css' tv, aural; p{c:d}")
        )

    def test_import_after_a_rule(self) -> None:
        # Invalid in CSS, which puts @import first, but honoured all the same.
        self.assertEqual(
            (["x.css"], {"p", "div"}),
            self._imports("p{c:d} @import url(x.css); div{c:d}"),
        )

    def test_namespace(self) -> None:
        rules = self._parse(
            "@namespace svg url(http://www.w3.org/2000/svg);"
            "@namespace url(http://www.w3.org/1999/xhtml);"
            "svg|circle{color:red} p{color:blue}"
        )
        self.assertEqual({"svg|circle", "p"}, set(rules))

    def test_namespace_errors(self) -> None:
        cases = {
            "@namespace ; p{c:d}": "@namespace expected an identifier or a URI",
            "@namespace svg; p{c:d}": "@namespace expected a URI",
            "@namespace url(x) p{c:d}": "@namespace expected a terminating",
        }
        for css, message in cases.items():
            with self.subTest(css=css), self.assertRaisesRegex(CSSParseError, message):
                self._parse(css)

    def test_at_rule_without_a_name(self) -> None:
        with self.assertRaisesRegex(CSSParseError, "At-rule expected an identifier"):
            self._parse("@123 {} p{c:d}")

    def test_unknown_state(self) -> None:
        with self.assertRaisesRegex(CSSParseError, "Unknown state in atKeyword"):
            self._parser()._parseAtKeyword("p{c:d}")


class MediaTest(ParserTestCase):
    def test_unsupported_at_rule_inside_media(self) -> None:
        # Used to raise TypeError: the skipped rule's NotImplemented was
        # iterated as if it were a list of rules.
        rules = self._parse(
            "@media print {"
            "  @keyframes fade { from { opacity: 0; } }"
            "  @layer base;"
            "  p { color: red; }"
            "}"
        )
        self.assertEqual({"p": {"color": "red"}}, rules)

    def test_at_rule_inside_media(self) -> None:
        rules = self._parse(
            "@media print { @font-face { font-family: x; src: url(a.ttf) }"
            " p { color: red; } }"
        )
        self.assertEqual({"*", "p"}, set(rules))

    def test_end_of_stylesheet_closes_the_block(self) -> None:
        self.assertEqual(
            {"p": {"color": "red"}}, self._parse("@media print { p{color:red}")
        )

    def test_media_without_a_block(self) -> None:
        # Both used to fail on something other than a parse error: an
        # IndexError, and an AttributeError on a failed regex match.
        for css in ("@media print", "@media (max-width: 1px) p"):
            with (
                self.subTest(css=css),
                self.assertRaisesRegex(CSSParseError, "opening '{' not found"),
            ):
                self._parse(css)


class PageTest(ParserTestCase):
    @staticmethod
    def _context(css: str) -> pisaContext:
        context = pisaContext(".")
        context.addCSS(css)
        context.parseCSS()
        return context

    def test_size_as_two_lengths(self) -> None:
        context = self._context("@page { size: 10cm 20cm }")
        self.assertEqual(
            (10, 20), tuple(round(side / 28.3464567) for side in context.pageSize)
        )

    def test_pdf_page_size(self) -> None:
        context = self._context("@page { -pdf-page-size: a5 }")
        self.assertEqual((420, 595), tuple(round(side) for side in context.pageSize))

    def test_unsupported_at_rule_inside_page(self) -> None:
        context = self._context("@page { @supports (x) { p { c: d } } size: a5 }")
        self.assertEqual((420, 595), tuple(round(side) for side in context.pageSize))

    def test_page_without_a_block(self) -> None:
        with self.assertRaisesRegex(CSSParseError, "opening '{' not found"):
            self._context("@page x y")


class AttributeSelectorTest(ParserTestCase):
    HTML = (
        "<form>"
        "<input id='text' type='text' lang='en-GB' title='big red'/>"
        "<input id='box' type='checkbox' lang='fr'/>"
        "<a id='link' href='x' title='a b'/>"
        "</form>"
    )

    def _matched(self, css: str) -> set:
        ruleset = self._parser().parse(css)[0]
        document = minidom.parseString(self.HTML)
        matched = set()
        for node in document.getElementsByTagName("*"):
            element = CSSDOMElementInterface(node)
            if any(selector.matches(element) for selector in ruleset):
                matched.add(element.getIdAttr())
        return matched

    def test_presence(self) -> None:
        self.assertEqual({"link"}, self._matched("[href] {c:d}"))

    def test_equals(self) -> None:
        self.assertEqual({"text"}, self._matched("input[type=text] {c:d}"))
        self.assertEqual({"link"}, self._matched('a[title="a b"] {c:d}'))

    def test_word_and_language(self) -> None:
        self.assertEqual({"text"}, self._matched("[title~=red] {c:d}"))
        self.assertEqual({"text"}, self._matched("[lang|=en] {c:d}"))

    def test_namespaced_attribute(self) -> None:
        self.assertEqual(
            {"[('ns', None, 'attr')]"},
            {str(selector).lstrip("*") for selector in self._parse("[ns|attr] {c:d}")},
        )

    def test_malformed_attribute_drops_only_its_rule(self) -> None:
        for css in ("a[=x]", "a[x=]", "a[x=y"):
            with self.subTest(css=css):
                self.assertEqual({"p"}, set(self._parse(css + " {c:d} p{c:d}")))


class SelectorTest(ParserTestCase):
    def test_malformed_pseudo_drops_only_its_rule(self) -> None:
        for css in ("a:", "li:nth-child(2"):
            with self.subTest(css=css):
                self.assertEqual({"p"}, set(self._parse(css + " {c:d} p{c:d}")))

    def test_selector_starting_with_a_digit(self) -> None:
        for css in (".1", "p .1"):
            with self.subTest(css=css):
                self.assertEqual({"p"}, set(self._parse(css + " {c:d} p{c:d}")))

    def test_namespace_wildcards(self) -> None:
        self.assertEqual({"*|p", "|p"}, set(self._parse("*|p{c:d} |p{c:d}")))


class DeclarationTest(ParserTestCase):
    def test_group_without_an_opening_brace(self) -> None:
        with self.assertRaisesRegex(CSSParseError, "opening '{' not found"):
            self._parser()._parseDeclarationGroup("color: red }")

    def test_empty_declarations_are_skipped(self) -> None:
        # Both used to throw the whole rule away.
        self.assertEqual(
            {"p": {"color": "red", "font-size": ("2", "px")}},
            self._parse("p{color:red;;font-size:2px}"),
        )
        self.assertEqual({"p": {"color": "red"}}, self._parse("p{;color:red}"))

    def test_end_of_stylesheet_closes_the_block(self) -> None:
        self.assertEqual({"p": {"color": "red"}}, self._parse("p{color:red"))

    def test_declaration_that_is_not_one_drops_its_rule(self) -> None:
        self.assertEqual({"div"}, set(self._parse("p{color:red; !ie} div{c:d}")))

    def test_star_hack_is_neutralised(self) -> None:
        # "*font" is an old IE hack; the property it becomes means nothing.
        self.assertEqual(
            {"-nothing-font": "smaller", "color": "red"},
            self._parse("p{*font: smaller; color:red}")["p"],
        )

    def test_equals_as_separator(self) -> None:
        self.assertEqual({"p": {"color": "red"}}, self._parse("p{color=red}"))

    def test_unicode_range(self) -> None:
        # Used to raise IndexError, from every @font-face Google Fonts serves.
        self.assertEqual(
            {"unicode-range": "U+0025-00FF"},
            self._parse("p{unicode-range: U+0025-00FF}")["p"],
        )

    def test_unclosed_function(self) -> None:
        # At the end of the stylesheet this used to raise IndexError.
        self.assertEqual({}, self._parse("p{width: calc(1px"))
        self.assertEqual({"div"}, set(self._parse("p{width: calc(1px} div{c:d}")))

    def test_terms(self) -> None:
        declarations = self._parse("p{a: foo|bar; b: 宋体; c: '宋体'; d: ''}")["p"]
        self.assertEqual(
            {"a": ("foo", None, "bar"), "b": "宋体", "c": "'宋体'", "d": ""},
            declarations,
        )
