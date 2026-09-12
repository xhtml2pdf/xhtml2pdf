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


class RulesetIndexTest(TestCase):
    """
    CSSRuleset files its rules under a condition the element must meet, so a
    lookup evaluates a handful of selectors instead of the whole stylesheet.
    The index is allowed to narrow the field; it is not allowed to decide.
    """

    MEDIUM_SET: ClassVar[list[str]] = ["all", "print", "pdf"]

    def _ruleset(self, css: str):
        return CSSParser(CSSBuilder(mediumSet=self.MEDIUM_SET)).parse(css)[0]

    @staticmethod
    def _element(html: str, tag: str | None = None):
        document = minidom.parseString(html)
        node = (
            document.getElementsByTagName(tag)[0] if tag else document.documentElement
        )
        return CSSDOMElementInterface(node)

    @staticmethod
    def _scan(ruleset, element, attrName):
        """Every rule, scanned and matched directly: the oracle for the index."""
        results = [
            rule
            for rule in ruleset.items()
            if attrName in rule[1] and rule[0].matches(element)
        ]
        results.sort(key=lambda rule: rule[0].sortKey())
        return results

    def _assertSameAsScan(self, css: str, html: str, tag: str | None = None) -> None:
        ruleset = self._ruleset(css)
        element = self._element(html, tag)
        for attrName in ("color", "margin-left", "orphans"):
            self.assertEqual(
                self._scan(ruleset, element, attrName),
                ruleset.findCSSRulesFor(element, attrName),
                f"{attrName} in {css!r} against {html!r}",
            )

    def test_a_second_class_is_still_required(self) -> None:
        # ".a.b" can only be filed under one of its classes; the other is left
        # for matches() to insist on.
        self._assertSameAsScan(".a.b { color: red }", "<p class='a'>x</p>")
        self._assertSameAsScan(".a.b { color: red }", "<p class='a b'>x</p>")

    def test_a_hash_on_an_ancestor_is_not_a_hash_on_the_element(self) -> None:
        # "#main .x p" constrains an ancestor. Filing it under id "main" would
        # look for a <p id="main">, and the rule would never be found.
        self._assertSameAsScan(
            "#main .x p { color: red }",
            "<div id='main'><div class='x'><p>hit</p></div></div>",
            tag="p",
        )

    def test_a_descendant_of_something_else_still_misses(self) -> None:
        self._assertSameAsScan(
            "#main .x p { color: red }",
            "<div id='other'><div class='x'><p>miss</p></div></div>",
            tag="p",
        )

    def test_the_universal_selector_reaches_everything(self) -> None:
        self._assertSameAsScan("* { color: red }", "<p class='a' id='b'>x</p>")

    def test_a_tag_is_matched_as_written(self) -> None:
        # Neither the parser nor matches() lowercases a tag name, so "DIV"
        # does not match <div> -- and the index must not quietly make it, or
        # stop it, matching. Recorded as it is rather than as it should be:
        # changing it is a matcher decision, not an indexing one.
        ruleset = self._ruleset("DIV { color: red }")
        element = self._element("<div>x</div>")
        self.assertEqual([], ruleset.findCSSRulesFor(element, "color"))
        self.assertEqual(
            self._scan(ruleset, element, "color"),
            ruleset.findCSSRulesFor(element, "color"),
        )

    def test_an_id_selector_finds_its_element(self) -> None:
        self._assertSameAsScan("#here { color: red }", "<p id='here'>x</p>")
        self._assertSameAsScan("#here { color: red }", "<p id='elsewhere'>x</p>")

    def test_an_unmentioned_property_is_answered_without_matching(self) -> None:
        ruleset = self._ruleset("p { color: red }")
        element = self._element("<p>x</p>")
        self.assertEqual([], ruleset.findCSSRulesFor(element, "orphans"))

    def test_merging_styles_invalidates_the_index(self) -> None:
        # mergeStyles reaches into a declarations dict the ruleset already
        # held, which does not go through __setitem__.
        ruleset = self._ruleset("p { color: red }")
        element = self._element("<p>x</p>")
        self.assertEqual([], ruleset.findCSSRulesFor(element, "margin-left"))

        ruleset.mergeStyles(self._ruleset("p { margin-left: 5px }"))
        self.assertEqual(
            self._scan(ruleset, element, "margin-left"),
            ruleset.findCSSRulesFor(element, "margin-left"),
        )

    def test_adding_a_rule_invalidates_the_index(self) -> None:
        ruleset = self._ruleset("p { color: red }")
        element = self._element("<p class='late'>x</p>")
        ruleset.findCSSRulesFor(element, "color")

        ruleset.update(self._ruleset(".late { color: blue }"))
        self.assertEqual(
            self._scan(ruleset, element, "color"),
            ruleset.findCSSRulesFor(element, "color"),
        )

    def test_findMatchingRules_agrees_with_the_selectors(self) -> None:
        css = "p { color: red } .a { color: blue } #z { color: green } div { x: y }"
        ruleset = self._ruleset(css)
        element = self._element("<p class='a' id='z'>x</p>")
        self.assertEqual(
            sorted((s for s in ruleset if s.matches(element)), key=lambda s: s.order),
            sorted(
                (s for s, _ in ruleset.findMatchingRules(element)),
                key=lambda s: s.order,
            ),
        )

    def test_a_rule_appears_once_even_with_two_matching_classes(self) -> None:
        ruleset = self._ruleset(".a.b { color: red }")
        element = self._element("<p class='a b'>x</p>")
        self.assertEqual(1, len(ruleset.findMatchingRules(element)))


class BatchAgreesWithPerPropertyTest(TestCase):
    """
    findStylesForElement resolves a whole element in one walk of the cascade
    and has to agree with findStyleFor, which walks it once per property --
    including where the winner is decided by the cascade level rather than by
    specificity or source order.
    """

    MEDIUM_SET: ClassVar[list[str]] = ["all", "print", "pdf"]

    NAMES: ClassVar[tuple[str, ...]] = (
        "color",
        "background-color",
        "margin-left",
        "font-size",
        "orphans",
    )

    def _cascade(self, *, author=None, user=None, userAgent=None):
        parser = CSSParser(CSSBuilder(mediumSet=self.MEDIUM_SET))
        return CSSCascadeStrategy(
            author=parser.parse(author) if author else None,
            user=parser.parse(user) if user else None,
            userAgent=parser.parse(userAgent) if userAgent else None,
        )

    def _assertAgrees(self, cascade, html: str) -> None:
        node = minidom.parseString(html).documentElement
        element = CSSDOMElementInterface(node)
        batch = cascade.findStylesForElement(element, self.NAMES)
        for name in self.NAMES:
            one = cascade.findStyleFor(element, name, None)
            self.assertEqual(one, batch.get(name), f"{name} in {html!r}")

    def test_specificity_and_source_order(self) -> None:
        self._assertAgrees(
            self._cascade(
                author=".zebra { color: orange } .alpha { color: blue }"
                " p.alpha { margin-left: 5px } .zebra { margin-left: 9px }"
            ),
            "<p class='zebra alpha'>x</p>",
        )

    def test_important_from_the_user_level(self) -> None:
        # The case the level in the sort key exists for: a user !important
        # declaration is applied last although its selector was written first.
        self._assertAgrees(
            self._cascade(
                user=".zebra { color: orange !important }",
                author=".alpha { color: blue }",
            ),
            "<p class='zebra alpha'>x</p>",
        )

    def test_across_every_level(self) -> None:
        self._assertAgrees(
            self._cascade(
                userAgent="p { color: black; margin-left: 1px }",
                user="p { color: grey !important; font-size: 9px }",
                author="p { color: red; margin-left: 2px }",
            ),
            "<p class='a' id='b'>x</p>",
        )

    def test_an_inline_style(self) -> None:
        self._assertAgrees(
            self._cascade(author="p { color: red }"),
            "<p style='color: green; margin-left: 3px'>x</p>",
        )

    def test_a_property_nobody_declares_is_absent(self) -> None:
        cascade = self._cascade(author="p { color: red }")
        node = minidom.parseString("<p>x</p>").documentElement
        batch = cascade.findStylesForElement(CSSDOMElementInterface(node), self.NAMES)
        self.assertNotIn("orphans", batch)
        self.assertEqual({"color"}, set(batch))

    def test_findStylesForEach_agrees_too(self) -> None:
        cascade = self._cascade(
            user=".zebra { color: orange !important }", author=".alpha { color: blue }"
        )
        node = minidom.parseString("<p class='zebra alpha'>x</p>").documentElement
        element = CSSDOMElementInterface(node)
        self.assertEqual(
            [(name, cascade.findStyleFor(element, name, None)) for name in self.NAMES],
            cascade.findStylesForEach(element, self.NAMES, None),
        )
