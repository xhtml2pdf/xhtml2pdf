from typing import ClassVar
from unittest import TestCase
from xml.dom import minidom

from xhtml2pdf.w3c.css import CSSBuilder, CSSCascadeStrategy, CSSParser
from xhtml2pdf.w3c.cssDOMElementInterface import CSSDOMElementInterface


class SelectorsTest(TestCase):
    def test_selector_lt(self) -> None:
        # test html:
        # <html>
        #   <head>
        #     <style>
        #         p { color: yellow;}
        #         .red { color: red;}
        #     </style>
        #   </head>
        #   <body>
        #       <p>I want to be yellow</p>
        #       <p class="red">I want to be red</p>
        #   </body>
        # </html>

        general_css = "p { color: yellow;}"
        specific_css = ".red { color: red;}"

        parser = CSSParser(CSSBuilder(mediumSet=["pdf"]))

        general_selector = next(iter(parser.parse(general_css)[0].keys()))
        specific_selector = next(iter(parser.parse(specific_css)[0].keys()))

        self.assertGreater(specific_selector, general_selector)


class MalformedSelectorTest(TestCase):
    """
    CSS 2.1 4.2: a malformed selector invalidates its own ruleset and nothing
    else. Before this was handled, the CSSParseError escaped all the way out
    of pisaParser and the whole document failed to render.
    """

    # The medium set pisaContext.parseCSS builds, so that @media print rules
    # are kept here exactly as they are in a real render.
    MEDIUM_SET: ClassVar[list[str]] = ["all", "print", "pdf"]

    @classmethod
    def _parse(cls, css: str) -> dict:
        parser = CSSParser(CSSBuilder(mediumSet=cls.MEDIUM_SET))
        ruleset = parser.parse(css)[0]
        return {str(selector): dict(decls) for selector, decls in ruleset.items()}

    def test_malformed_selector_drops_only_its_own_rule(self) -> None:
        # ">>" is not a combinator, so the middle rule cannot be parsed. The
        # rules on either side of it must survive.
        rules = self._parse(
            "p { color: green; }"
            "h2 >> p.sib { border-left: 4px solid red; }"
            "p.after { font-weight: bold; }"
        )

        self.assertEqual({"p", "p.after"}, set(rules))
        self.assertEqual({"color": "green"}, rules["p"])
        self.assertEqual({"font-weight": "bold"}, rules["p.after"])

    def test_malformed_selector_inside_at_media(self) -> None:
        rules = self._parse(
            "@media print {"
            "  p { color: green; }"
            "  h2 >> p.sib { color: red; }"
            "  div { color: blue; }"
            "}"
            "span { color: teal; }"
        )

        self.assertEqual({"p", "div", "span"}, set(rules))
        self.assertEqual({"color": "teal"}, rules["span"])

    def test_malformed_selector_as_last_rule_in_at_media(self) -> None:
        # The skip must not eat the brace that closes the @media block, or
        # every rule after it is swallowed too.
        rules = self._parse(
            "@media print {"
            "  p { color: green; }"
            "  h2 >> p.sib { color: red; }"
            "}"
            "div { color: blue; }"
        )

        self.assertEqual({"p", "div"}, set(rules))

    def test_malformed_selector_with_no_declaration_block(self) -> None:
        rules = self._parse("p { color: green; } h2 >> ")

        self.assertEqual({"p"}, set(rules))


class StandardSelectorTest(TestCase):
    """
    Selectors the parser has always accepted and the matcher used to drop on
    the floor: inPseudoState answered False for every name it did not know,
    and "~" was not a combinator at all.
    """

    MEDIUM_SET: ClassVar[list[str]] = ["all", "print", "pdf"]

    def _matched(self, html: str, css: str) -> set:
        """Ids of the elements a one-rule stylesheet colours."""
        parser = CSSParser(CSSBuilder(mediumSet=self.MEDIUM_SET))
        ruleset = parser.parse(css)[0]
        document = minidom.parseString(html)

        matched = set()
        for node in document.getElementsByTagName("*"):
            element = CSSDOMElementInterface(node)
            for selector in ruleset:
                if selector.matches(element):
                    matched.add(element.getIdAttr())
        return matched

    LIST = (
        "<ul>"
        "<li id='one'>a</li><li id='two'>b</li>"
        "<li id='three'>c</li><li id='four'>d</li>"
        "</ul>"
    )

    def test_nth_child_keyword(self) -> None:
        self.assertEqual(
            {"one", "three"}, self._matched(self.LIST, "li:nth-child(odd) {color: red}")
        )
        self.assertEqual(
            {"two", "four"}, self._matched(self.LIST, "li:nth-child(even) {color: red}")
        )

    def test_nth_child_expression(self) -> None:
        self.assertEqual(
            {"one", "three"},
            self._matched(self.LIST, "li:nth-child(2n+1) {color: red}"),
        )
        self.assertEqual(
            {"one", "two", "three"},
            self._matched(self.LIST, "li:nth-child(-n+3) {color: red}"),
        )

    def test_nth_child_index(self) -> None:
        self.assertEqual(
            {"three"}, self._matched(self.LIST, "li:nth-child(3) {color: red}")
        )

    def test_nth_last_child(self) -> None:
        self.assertEqual(
            {"four"}, self._matched(self.LIST, "li:nth-last-child(1) {color: red}")
        )

    def test_only_child(self) -> None:
        html = "<div><p id='alone'>x</p></div>"
        self.assertEqual({"alone"}, self._matched(html, "p:only-child {color: red}"))
        self.assertEqual(set(), self._matched(self.LIST, "li:only-child {color: red}"))

    def test_first_and_last_of_type(self) -> None:
        html = (
            "<div><span id='s1'>x</span><p id='p1'>x</p>"
            "<span id='s2'>x</span><p id='p2'>x</p></div>"
        )
        self.assertEqual({"s1"}, self._matched(html, "span:first-of-type {color: red}"))
        self.assertEqual({"p2"}, self._matched(html, "p:last-of-type {color: red}"))

    def test_empty(self) -> None:
        html = "<div><p id='full'>x</p><p id='blank'></p><p id='spaces'>  </p></div>"
        self.assertEqual(
            {"blank", "spaces"}, self._matched(html, "p:empty {color: red}")
        )

    def test_adjacent_sibling_combinator(self) -> None:
        # Used to raise AttributeError inside matches(), swallowed by the
        # blanket handler in parser.py, so the rule silently never applied.
        html = "<div><h2 id='h'>t</h2><p id='next'>x</p><p id='later'>y</p></div>"
        self.assertEqual({"next"}, self._matched(html, "h2 + p {color: red}"))

    def test_general_sibling_combinator(self) -> None:
        html = "<div><h2 id='h'>t</h2><p id='next'>x</p><p id='later'>y</p></div>"
        self.assertEqual({"next", "later"}, self._matched(html, "h2 ~ p {color: red}"))

    def test_unknown_pseudo_class_still_matches_nothing(self) -> None:
        self.assertEqual(set(), self._matched(self.LIST, "li:hover {color: red}"))


class CascadeOrderTest(TestCase):
    """
    CSS 2.1 6.4.1: where specificity ties, the rule written later wins. Rules
    were sorted by (specificity, fullName, qualifiers) instead, so the tie was
    broken alphabetically by tag name and qualifier -- ".alpha" beat ".zebra"
    whichever of the two was written last.
    """

    MEDIUM_SET: ClassVar[list[str]] = ["all", "print", "pdf"]

    def _color(self, css: str, html: str = "<p class='zebra alpha'>x</p>") -> str:
        parser = CSSParser(CSSBuilder(mediumSet=self.MEDIUM_SET))
        cascade = CSSCascadeStrategy(user=parser.parse(css))
        node = minidom.parseString(html).documentElement
        return cascade.findStyleFor(CSSDOMElementInterface(node), "color")

    def test_later_rule_wins(self) -> None:
        self.assertEqual(
            "blue", self._color(".zebra { color: orange } .alpha { color: blue }")
        )

    def test_later_rule_wins_whichever_way_round(self) -> None:
        self.assertEqual(
            "orange", self._color(".alpha { color: blue } .zebra { color: orange }")
        )

    def test_specificity_still_outranks_source_order(self) -> None:
        self.assertEqual(
            "blue", self._color("p.alpha { color: blue } .zebra { color: orange }")
        )

    def test_important_still_wins_over_a_later_rule(self) -> None:
        # The !important declarations are a separate cascade level applied last,
        # and their selectors are written early. Sorting by source order alone
        # would hand the win to the later normal rule.
        self.assertEqual(
            "orange",
            self._color(".zebra { color: orange !important } .alpha { color: blue }"),
        )
