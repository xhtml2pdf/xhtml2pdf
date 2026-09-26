"""
The CSS parser on its own: the at-rules, selectors and declarations that no
document in the rest of the suite happens to contain.

What is invalid is dropped and the rest applies, as CSS Syntax 3 says: an
at-rule to its ";" or through its block, a declaration to its ";". Each of
these used to raise instead -- a CSSParseError, an IndexError, a TypeError --
and nothing catches it, so one line of a stylesheet cost the whole document.
"""

import logging
import tempfile
from pathlib import Path
from typing import ClassVar
from unittest import TestCase
from xml.dom import minidom

from xhtml2pdf.context import pisaContext
from xhtml2pdf.document import pisaStory
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

    def test_error_at_the_start_is_located(self) -> None:
        # Position 0 used to count as no position at all.
        self.assertEqual("Bad:: ('', 'abc')", str(CSSParseError("Bad", "abc")))

    def test_message_without_a_position_quotes_the_source(self) -> None:
        self.assertEqual("Bad:: 'zzz'", str(CSSParseError("Bad", "zzz", "abc")))

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

    def test_parse_inline_drops_only_the_broken_declaration(self) -> None:
        normal, _ = self._parser().parseInline("color: red; width: calc(1px")
        self.assertEqual({"color": "red"}, dict(normal))
        # An open "(" runs to the end of the source, taking the ";" with it
        # (CSS Syntax 3, "consume a function"), as it does in a browser.
        normal, _ = self._parser().parseInline("width: calc(1px ; color: red")
        self.assertEqual({}, dict(normal))

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
        # The at-rule runs on to the block of the next rule, and both go.
        self.assertEqual({"div"}, set(self._parse('@charset "utf-8" p{c:d} div{c:d}')))

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

    def test_malformed_import_is_dropped(self) -> None:
        self.assertEqual(([], {"p"}), self._imports("@import foo; p{c:d}"))
        # Without its ";" it takes the next rule's block as its own.
        self.assertEqual(
            ([], {"div"}), self._imports("@import 'x.css' print p{c:d} div{c:d}")
        )

    def test_import_after_a_rule_is_ignored(self) -> None:
        # CSS 2.1 6.3: @import must come before every other rule.
        self.assertEqual(
            ([], {"p", "div"}), self._imports("p{c:d} @import url(x.css); div{c:d}")
        )

    def test_namespace(self) -> None:
        rules = self._parse(
            "@namespace svg url(http://www.w3.org/2000/svg);"
            "@namespace url(http://www.w3.org/1999/xhtml);"
            "svg|circle{color:red} p{color:blue}"
        )
        self.assertEqual({"svg|circle", "p"}, set(rules))

    def test_malformed_namespace_is_dropped(self) -> None:
        cases = {
            "@namespace ; p{c:d}": {"p"},
            "@namespace svg; p{c:d}": {"p"},
            # Without its ";" it takes the next rule's block as its own.
            "@namespace url(x) p{c:d} div{c:d}": {"div"},
        }
        for css, kept in cases.items():
            with self.subTest(css=css):
                self.assertEqual(kept, set(self._parse(css)))

    def test_at_rule_without_a_name_is_dropped(self) -> None:
        self.assertEqual({"p"}, set(self._parse("@123 {} p{c:d}")))

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

    def test_media_without_a_block_is_dropped(self) -> None:
        # These used to raise IndexError and AttributeError.
        for css in ("p{c:d} @media print", "p{c:d} @media (max-width: 1px) p"):
            with self.subTest(css=css):
                self.assertEqual({"p"}, set(self._parse(css)))


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

    def test_page_without_a_block_is_dropped(self) -> None:
        context = self._context("@page x y; @page { size: a5 }")
        self.assertEqual((420, 595), tuple(round(side) for side in context.pageSize))


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
        self.assertEqual(set(), self._matched("[title~=re] {c:d}"))
        self.assertEqual({"text"}, self._matched("[lang|=en] {c:d}"))
        self.assertEqual({"box"}, self._matched("[lang|=fr] {c:d}"))
        # A prefix up to a "-", not any "-" separated part: this used to match.
        self.assertEqual(set(), self._matched("[lang|=GB] {c:d}"))

    def test_prefix_suffix_and_substring(self) -> None:
        # Selectors 3. "^=" used to raise RuntimeError, out of the document.
        self.assertEqual(
            {"text", "box"}, self._matched("[type^=te], [type^=check] {c:d}")
        )
        self.assertEqual({"box"}, self._matched("[type$=box] {c:d}"))
        self.assertEqual({"text", "link"}, self._matched("[title*=' '] {c:d}"))
        self.assertEqual(set(), self._matched("[type^=ext] {c:d}"))

    def test_empty_value_matches_nothing(self) -> None:
        for op in ("^=", "$=", "*="):
            with self.subTest(op=op):
                self.assertEqual(set(), self._matched(f"[type{op}''] {{c:d}}"))

    def test_undeclared_namespace_prefix_drops_the_rule(self) -> None:
        self.assertEqual({"p"}, set(self._parse("[ns|attr] {c:d} p{c:d}")))

    def test_malformed_attribute_drops_only_its_rule(self) -> None:
        # "!=" is no CSS operator; it used to parse, then raise when matched.
        for css in ("a[=x]", "a[x=]", "a[x=y", "a[x!=y]"):
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

    def test_invalid_declaration_drops_only_itself(self) -> None:
        # It used to take the whole rule with it.
        self.assertEqual(
            {"p": {"color": "red"}, "div": {"c": "d"}},
            self._parse("p{color:red; !ie} div{c:d}"),
        )
        self.assertEqual(
            {"p": {"color": "red"}}, self._parse("p{color: red blue !x; color: red}")
        )

    def test_star_hack_is_dropped(self) -> None:
        # "*font" is an old IE hack, invalid CSS that a browser ignores.
        self.assertEqual(
            {"color": "red"}, self._parse("p{*font: smaller; color:red}")["p"]
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
        self.assertEqual(
            {"p": {"color": "blue"}}, self._parse("p{color: blue; width: calc(1px")
        )

    def test_non_ascii_strings_and_names(self) -> None:
        # Only Latin-1 counted as a string character: "宋体" gave NotImplemented,
        # '宋体' kept its quotes, and "a宋" lost the whole rule.
        self.assertEqual(
            {
                "p": {"font-family": ["宋体", "serif"]},
                "q": {"font-family": "宋体"},
                "b": {"font-family": "宋体"},
                "i": {"content": "a宋"},
            },
            self._parse(
                "p{font-family: \"宋体\", serif} q{font-family: '宋体'}"
                ' b{font-family: 宋体} i{content: "a宋"}'
            ),
        )

    def test_empty_string(self) -> None:
        self.assertEqual({"content": ""}, self._parse("p{content: ''}")["p"])


class DocumentTest(ParserTestCase):
    """What the fixes above are for: the document renders, with the rest of the CSS."""

    @staticmethod
    def _colors(html: bytes) -> list[str]:
        return [
            str(flowable.style.textColor)
            for flowable in pisaStory(html).story
            if hasattr(flowable, "style")
        ]

    def test_malformed_at_rules_do_not_stop_the_document(self) -> None:
        html = (
            b"<style>@import foo; @namespace svg; @charset 'x'"
            b" p { color: #ff0000 } @media print</style><p>x</p>"
        )
        # "@charset 'x' p {...}" is one invalid at-rule; the rule after it is not.
        self.assertEqual(["Color(0,0,0,1)"], self._colors(html))
        html = (
            b"<style>@namespace svg; p { color: #ff0000 } @media print</style><p>x</p>"
        )
        self.assertEqual(["Color(1,0,0,1)"], self._colors(html))

    def test_broken_inline_style_keeps_the_rest(self) -> None:
        html = b'<p style="color: #ff0000; width: calc(1px">x</p>'
        self.assertEqual(["Color(1,0,0,1)"], self._colors(html))

    def test_attribute_selectors_tell_siblings_apart(self) -> None:
        # The style cache keyed siblings by tag, class, id and style only, so
        # the second paragraph was handed the first one's colour.
        html = (
            b"<style>p[title^=big] { color: #ff0000 }</style>"
            b"<p title='big one'>x</p><p title='small'>y</p>"
        )
        self.assertEqual(["Color(1,0,0,1)", "Color(0,0,0,1)"], self._colors(html))
