"""
CSS-2.1 parser.

Copyright (C) 2002-2004 TechGame Networks, LLC.

This library is free software; you can redistribute it and/or
modify it under the terms of the BSD style License as found in the
LICENSE file included with this distribution.

Modified by Dirk Holtwick <holtwick@web.de>, 2007-2008

The CSS 2.1 Specification this parser was derived from can be found at http://www.w3.org/TR/CSS21/

Primary Classes:
    * CSSParser
        Parses CSS source forms into results using a Builder Pattern.  Must
        provide concrete implementation of CSSBuilderAbstract.

    * CSSBuilderAbstract
        Outlines the interface between CSSParser and it's rule-builder.
        Compose CSSParser with a concrete implementation of the builder to get
        usable results from the CSS parser.

Dependencies:
    re
"""

# ruff: file-ignore[invalid-module-name]
from __future__ import annotations

import logging
import re
from abc import abstractmethod
from typing import ClassVar

from reportlab.lib.pagesizes import landscape

import xhtml2pdf.default
from xhtml2pdf.util import getSize
from xhtml2pdf.w3c import cssSpecial

log = logging.getLogger("xhtml2pdf")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ Definitions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def isAtRuleIdent(src, ident):
    return re.match(r"^@" + ident + r"\s*", src)


def stripAtRuleIdent(src):
    return re.sub(r"^@[a-z\-]+\s*", "", src)


class CSSSelectorAbstract:
    """
    Outlines the interface between CSSParser and it's rule-builder for selectors.

    CSSBuilderAbstract.selector and CSSBuilderAbstract.combineSelectors must
    return concrete implementations of this abstract.

    See css.CSSMutableSelector for an example implementation.
    """

    @abstractmethod
    def addHashId(self, hashId):
        raise NotImplementedError

    @abstractmethod
    def addClass(self, class_):
        raise NotImplementedError

    @abstractmethod
    def addAttribute(self, attrName):
        raise NotImplementedError

    @abstractmethod
    def addAttributeOperation(self, attrName, op, attr_value):
        raise NotImplementedError

    @abstractmethod
    def addPseudo(self, name):
        raise NotImplementedError

    @abstractmethod
    def addPseudoFunction(self, name, value):
        raise NotImplementedError


class CSSBuilderAbstract:
    """
    Outlines the interface between CSSParser and it's rule-builder.  Compose
    CSSParser with a concrete implementation of the builder to get usable
    results from the CSS parser.

    See css.CSSBuilder for an example implementation
    """

    # ~ css results ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @abstractmethod
    def beginStylesheet(self):
        raise NotImplementedError

    @abstractmethod
    def stylesheet(self, elements):
        raise NotImplementedError

    @abstractmethod
    def endStylesheet(self):
        raise NotImplementedError

    @abstractmethod
    def beginInline(self):
        raise NotImplementedError

    @abstractmethod
    def inline(self, declarations):
        raise NotImplementedError

    @abstractmethod
    def endInline(self):
        raise NotImplementedError

    @abstractmethod
    def ruleset(self, selectors, declarations):
        raise NotImplementedError

    # ~ css namespaces ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @abstractmethod
    def resolveNamespacePrefix(self, nsPrefix, name):
        raise NotImplementedError

    # ~ css @ directives ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @abstractmethod
    def atCharset(self, charset):
        raise NotImplementedError

    @abstractmethod
    def atImport(self, import_, mediums, cssParser):
        raise NotImplementedError

    @abstractmethod
    def atNamespace(self, nsPrefix, uri):
        raise NotImplementedError

    @abstractmethod
    def atMedia(self, mediums, ruleset):
        raise NotImplementedError

    @abstractmethod
    def atPage(
        self,
        name: str,
        pseudopage: str | None,
        data: dict,
        *,
        isLandscape: bool,
        pageBorder,
    ):
        raise NotImplementedError

    @abstractmethod
    def atFontFace(self, declarations):
        raise NotImplementedError

    @abstractmethod
    def atIdent(self, atIdent, cssParser, src):
        return src, NotImplemented

    # ~ css selectors ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @abstractmethod
    def combineSelectors(self, selectorA, combiner, selectorB):
        """Return value must implement CSSSelectorAbstract."""
        raise NotImplementedError

    @abstractmethod
    def selector(self, name):
        """Return value must implement CSSSelectorAbstract."""
        raise NotImplementedError

    # ~ css declarations ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @abstractmethod
    def property(self, name, value, *, important=False):
        raise NotImplementedError

    @abstractmethod
    def combineTerms(self, termA, combiner, termB):
        raise NotImplementedError

    @abstractmethod
    def termIdent(self, value):
        raise NotImplementedError

    @abstractmethod
    def termNumber(self, value, units=None):
        raise NotImplementedError

    @abstractmethod
    def termRGB(self, value):
        raise NotImplementedError

    @abstractmethod
    def termURI(self, value):
        raise NotImplementedError

    @abstractmethod
    def termString(self, value):
        raise NotImplementedError

    @abstractmethod
    def termUnicodeRange(self, value):
        raise NotImplementedError

    @abstractmethod
    def termFunction(self, name, value):
        raise NotImplementedError

    @abstractmethod
    def termUnknown(self, _src):
        raise NotImplementedError


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ CSS Parser
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class CSSParseError(Exception):
    src: str = ""
    ctxsrc: str = ""
    srcCtxIdx: int | None = None

    def __init__(self, msg, src, ctxsrc=None) -> None:
        super().__init__(msg)
        self.src = src
        self.ctxsrc = ctxsrc or src
        if self.ctxsrc:
            index = self.ctxsrc.find(self.src)
            self.srcCtxIdx = index if index >= 0 else None

    def __str__(self) -> str:
        if self.ctxsrc and self.srcCtxIdx is not None:
            return (
                super().__str__()
                + ":: ("
                + str(repr(self.ctxsrc[: self.srcCtxIdx]))
                + ", "
                + str(repr(self.ctxsrc[self.srcCtxIdx : self.srcCtxIdx + 20]))
                + ")"
            )
        return super().__str__() + ":: " + repr(self.src[:40])


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def regex_or(*args):
    """Small helper to join regex expressions"""
    return "|".join(args)


class CSSParser:
    """
    CSS-2.1 parser dependent only upon the re module.

    Implemented directly from http://www.w3.org/TR/CSS21/grammar.html
    Tested with some existing CSS stylesheets for portability.

    CSS Parsing API:
        * setCSSBuilder()
            To set your concrete implementation of CSSBuilderAbstract

        * parseFile()
            Use to parse external stylesheets using a file-like object

            >>> cssFile = open('test.css', 'r')
            >>> stylesheets = myCSSParser.parseFile(cssFile)

        * parse()
            Use to parse embedded stylesheets using source string

            >>> cssSrc = '''
                body,body.body {
                    font: 110%, "Times New Roman", Arial, Verdana, Helvetica, serif;
                    background: White;
                    color: Black;
                }
                a {text-decoration: underline;}
            '''
            >>> stylesheets = myCSSParser.parse(cssSrc)

        * parseInline()
            Use to parse inline stylesheets using attribute source string

            >>> style = 'font: 110%, "Times New Roman", Arial, Verdana, Helvetica, serif; background: White; color: Black'
            >>> stylesheets = myCSSParser.parseInline(style)

        * parseAttributes()
            Use to parse attribute string values into inline stylesheets

            >>> stylesheets = myCSSParser.parseAttributes(
                    font='110%, "Times New Roman", Arial, Verdana, Helvetica, serif',
                    background='White',
                    color='Black')

        * parseSingleAttr()
            Use to parse a single string value into a CSS expression

            >>> fontValue = myCSSParser.parseSingleAttr('110%, "Times New Roman", Arial, Verdana, Helvetica, serif')
    """

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ~ Constants / Variables / Etc.
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ParseError = CSSParseError

    # Selectors 3. "&=", "!=" and "<>" used to be accepted here too, and then
    # raised RuntimeError when matched, since nothing implements them.
    AttributeOperators: ClassVar[list[str]] = ["=", "~=", "|=", "^=", "$=", "*="]
    SelectorQualifiers: ClassVar[tuple[str, ...]] = ("#", ".", "[", ":")
    SelectorCombiners: ClassVar[list[str]] = ["+", ">", "~"]
    ExpressionOperators: ClassVar[tuple[str, ...]] = ("/", "+", ",")
    #: The pseudo pages that mean something here. A ``name_left`` /
    #: ``name_right`` pair is what ``handle_nextPageTemplate`` cycles between;
    #: :first and :blank have no equivalent in this model.
    PAGE_PSEUDO_CLASSES: ClassVar[frozenset[str]] = frozenset({"left", "right"})

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ~ Regular expressions
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    _reflags = re.IGNORECASE | re.MULTILINE | re.UNICODE
    i_hex = "[0-9a-fA-F]"
    # Any character past ASCII, as CSS 2.1 defines nonascii. This was
    # [\200-\377], Latin-1 only, so "宋体" was no string at all.
    i_nonascii = "[^\x00-\x7f]"
    # Both the digit count and the trailing space are pinned down rather than
    # left for the engine to try every way round. `{1,6}` next to a literal
    # class that also accepts hex digits, and a `\s?` next to a class that also
    # accepts a space, each give the engine a second way to divide the same
    # text; inside the starred body of i_string that multiplies out into
    # catastrophic backtracking. A seventh hex digit is a literal character per
    # CSS 2.1 4.1.3, so refusing to stop short of six loses nothing, and the
    # whitespace the spec swallows after an escape is exactly this set.
    i_unicode = (
        rf"\\(?:{i_hex}{{6}}|{i_hex}{{1,5}}(?!{i_hex}))"
        # "consume the space if there is one", not "try it both ways": the
        # plain `?` of a `\s?` is what `\1 ` repeated 24 times exploits.
        r"(?:[ \t\r\n\f]|(?![ \t\r\n\f]))"
    )
    # A backslash followed by a hex digit is i_unicode's alone; without this
    # lookahead both branches match it and every escape doubles the work.
    i_escape = regex_or(i_unicode, r"\\(?![0-9a-fA-F])[ -~\200-\377]")
    # i_nmstart = regex_or('[A-Za-z_]', i_nonascii, i_escape)
    i_nmstart = regex_or(
        r"\-[^0-9]|[A-Za-z_]", i_nonascii, i_escape
    )  # XXX Added hyphen, http://www.w3.org/TR/CSS21/syndata.html#value-def-identifier
    i_nmchar = regex_or("[-0-9A-Za-z_]", i_nonascii, i_escape)
    i_ident = f"((?:{i_nmstart})(?:{i_nmchar})*)"
    re_ident = re.compile(i_ident, _reflags)
    # Caution: treats all characters above 0x7f as legal for an identifier.
    i_element_name = rf"((?:{i_ident[1:-1]})|\*)"
    re_element_name = re.compile(i_element_name, _reflags)
    i_namespace_selector = rf"((?:{i_ident[1:-1]})|\*|)\|(?!=)"
    re_namespace_selector = re.compile(i_namespace_selector, _reflags)
    i_class = r"\." + i_ident
    re_class = re.compile(i_class, _reflags)
    i_hash = "#((?:%s)+)" % i_nmchar
    re_hash = re.compile(i_hash, _reflags)
    i_rgbcolor = f"(#{i_hex}{{8}}|#{i_hex}{{6}}|#{i_hex}{{3}})"
    re_rgbcolor = re.compile(i_rgbcolor, _reflags)
    i_nl = "\n|\r\n|\r|\f"
    i_escape_nl = r"\\(?:%s)" % i_nl
    # The literal class stops short of 0x5C and picks up after it, so a
    # backslash is i_escape_nl's and i_escape's alone. A class that spans it
    # gives the engine two ways to match every backslash, and inside a `*`
    # that costs exponential time on a string nobody closed: 40 backslashes
    # in a <style> hold a worker for three minutes.
    i_string_content = regex_or("[\t !#$%&(-[\\]-~]", i_escape_nl, i_nonascii, i_escape)
    i_string1 = '"((?:%s|\')*)"' % i_string_content
    i_string2 = "'((?:%s|\")*)'" % i_string_content
    i_string = regex_or(i_string1, i_string2)
    re_string = re.compile(i_string, _reflags)
    i_uri = r"url\(\s*(?:(?:{})|((?:{})+))\s*\)".format(
        i_string, regex_or("[!#$%&*-[\\]-~]", i_nonascii, i_escape)
    )
    # XXX For now
    # i_uri = '(url\\(.*?\\))'
    re_uri = re.compile(i_uri, _reflags)
    i_num = (  # XXX Added out parenthesis, because e.g. .5em was not parsed correctly
        r"(([-+]?[0-9]+(?:\.[0-9]+)?)|([-+]?\.[0-9]+))"
    )
    re_num = re.compile(i_num, _reflags)
    i_unit = "(%%|%s)?" % i_ident
    re_unit = re.compile(i_unit, _reflags)
    i_function = i_ident + r"\("
    re_function = re.compile(i_function, _reflags)
    i_functionterm = "[-+]?" + i_function
    re_functionterm = re.compile(i_functionterm, _reflags)
    i_unicoderange1 = rf"(?:U\+{i_hex}{{1,6}}-{i_hex}{{1,6}})"
    i_unicoderange2 = r"(?:U\+\?{1,6}|{h}(\?{0,5}|{h}(\?{0,4}|{h}(\?{0,3}|{h}(\?{0,2}|{h}(\??|{h}))))))"
    # In a group of its own: _getMatchResult returns group 1, and without it
    # every unicode-range -- in each @font-face Google Fonts serves -- raised
    # IndexError and took the document down.
    i_unicoderange = (
        f"({i_unicoderange1})"  # '(%s|%s)' % (i_unicoderange1, i_unicoderange2)
    )
    re_unicoderange = re.compile(i_unicoderange, _reflags)

    # i_comment = '(?:\/\*[^*]*\*+([^/*][^*]*\*+)*\/)|(?://.*)'
    # gabriel: only C convention for comments is allowed in CSS
    i_comment = r"(?:\/\*[^*]*\*+([^/*][^*]*\*+)*\/)"
    re_comment = re.compile(i_comment, _reflags)
    i_important = r"!\s*(important)"
    re_important = re.compile(i_important, _reflags)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ~ Public
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def __init__(self, cssBuilder=None) -> None:
        self.setCSSBuilder(cssBuilder)

    # ~ CSS Builder to delegate to ~~~~~~~~~~~~~~~~~~~~~~~~

    def getCSSBuilder(self):
        """A concrete instance implementing CSSBuilderAbstract."""
        return self._cssBuilder

    def setCSSBuilder(self, cssBuilder):
        """A concrete instance implementing CSSBuilderAbstract."""
        self._cssBuilder = cssBuilder

    cssBuilder = property(getCSSBuilder, setCSSBuilder)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ~ Public CSS Parsing API
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def parseFile(self, srcFile):
        """
        Parses CSS file-like objects using the current cssBuilder.
        Use for external stylesheets.
        """
        with open(srcFile, encoding="utf-8") as file_handler:
            file_content = file_handler.read()

        return self.parse(file_content)

    def parse(self, src):
        """
        Parses CSS string source using the current cssBuilder.
        Use for embedded stylesheets.
        """
        self.cssBuilder.beginStylesheet()
        try:
            # XXX Some simple preprocessing
            src = cssSpecial.cleanupCSS(src)

            src, stylesheet = self._parseStylesheet(src)
        finally:
            self.cssBuilder.endStylesheet()
        return stylesheet

    def parseInline(self, src):
        """
        Parses CSS inline source string using the current cssBuilder.
        Use to parse a tag's 'style'-like attribute.
        """
        self.cssBuilder.beginInline()
        try:
            src, properties = self._parseDeclarationGroup(src.strip(), braces=False)
            result = self.cssBuilder.inline(properties)
        finally:
            self.cssBuilder.endInline()
        return result

    def parseAttributes(self, attributes=None, **kwAttributes):
        """
        Parses CSS attribute source strings, and return as an inline stylesheet.
        Use to parse a tag's highly CSS-based attributes like 'font'.

        See also: parseSingleAttr
        """
        attributes = attributes if attributes is not None else {}
        if attributes:
            kwAttributes.update(attributes)

        self.cssBuilder.beginInline()
        try:
            properties = []
            for property_name, src in kwAttributes.items():
                src, single_property = self._parseDeclarationProperty(
                    src.strip(), property_name
                )
                properties.append(single_property)

            result = self.cssBuilder.inline(properties)
        finally:
            self.cssBuilder.endInline()
        return result

    def parseSingleAttr(self, attr_value):
        """
        Parse a single CSS attribute source string, and returns the built CSS expression.
        Use to parse a tag's highly CSS-based attributes like 'font'.

        See also: parseAttributes
        """
        results = self.parseAttributes(temp=attr_value)
        if "temp" in results[1]:
            return results[1]["temp"]
        return results[0]["temp"]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ~ Internal _parse methods
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @staticmethod
    def _skipMalformedRuleset(src):
        """
        Discard a ruleset whose selector could not be parsed, and return the
        rest of the stylesheet.

        CSS 2.1 4.2 requires a malformed selector to invalidate exactly one
        thing, the ruleset it introduces: "the user agent must ignore the
        whole rule". Letting the CSSParseError escape instead aborts the
        entire stylesheet, and with it the document, because neither
        pisaContext.parseCSS nor pisaParser catches it. One selector the
        parser happens not to understand then costs the caller every rule in
        the file.
        """
        brace = src.find("{")
        close = src.find("}")
        if brace < 0 or (0 <= close < brace):
            # No declaration block of our own to swallow: the next brace
            # closes whatever block this ruleset sits in. Hand it back so the
            # caller can close that block itself.
            return src[close:].lstrip() if close >= 0 else ""
        end = src.find("}", brace)
        if end < 0:
            return ""
        return src[end + 1 :].lstrip()

    @staticmethod
    def _skipBlock(src):
        """
        Return the source after the {} block that the first "{" in src opens,
        nested blocks included, or "" if that block never closes. A brace in
        a quoted string, as in content: "}", does not count.
        """
        start = src.find("{")
        if start < 0:
            return ""
        depth = 0
        quote = None
        i = start
        while i < len(src):
            char = src[i]
            if quote:
                if char == "\\":
                    i += 1
                elif char == quote:
                    quote = None
            elif char in {'"', "'"}:
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return src[i + 1 :].lstrip()
            i += 1
        return ""

    @staticmethod
    def _findAtTopLevel(src, stops):
        """
        Index of the first character of stops in src that is outside any
        quoted string and any (), [] or {} block, or -1. A "{" in stops stops
        the search where it would otherwise open a block; a closing bracket
        with no block open is only a stop.
        """
        depth = 0
        quote = None
        i = 0
        while i < len(src):
            char = src[i]
            if quote:
                if char == "\\":
                    i += 1
                elif char == quote:
                    quote = None
            elif char in {'"', "'"}:
                quote = char
            elif depth == 0 and char in stops:
                return i
            elif char in "([{":
                depth += 1
            elif char in ")]}" and depth:
                depth -= 1
            i += 1
        return -1

    def _skipAtRule(self, src):
        """
        Return the source after the at-rule src starts with: up to its ";",
        or through its {} block, whichever comes first (CSS Syntax 3, "consume
        an at-rule"). A "}" that closes an enclosing block ends it too, and is
        left for that block.
        """
        end = self._findAtTopLevel(src, {";", "{", "}"})
        if end < 0:
            return ""
        if src[end] == ";":
            return src[end + 1 :].lstrip()
        if src[end] == "{":
            return self._skipBlock(src[end:])
        return src[end:]

    def _skipDeclaration(self, src):
        """
        Return the source from the ";" or "}" that ends the declaration src
        starts with (CSS Syntax 3, "consume a list of declarations").
        """
        end = self._findAtTopLevel(src, {";", "}"})
        return src[end:] if end >= 0 else ""

    def _parseAtKeywordOrSkip(self, src, stylesheetElements):
        """Parse one at-rule, or drop it if it is malformed."""
        try:
            rest, atResults = self._parseAtKeyword(src)
        except self.ParseError as exc:
            log.warning("Ignoring CSS at-rule that could not be parsed: %s", exc)
            return self._skipAtRule(src)
        if atResults is not None and atResults is not NotImplemented:
            stylesheetElements.extend(atResults)
        return rest

    def _skipInvalidAtRule(self, msg, src, ctxsrc):
        """Drop the at-rule ctxsrc starts with, which msg says is malformed."""
        error = self.ParseError(msg, src, ctxsrc)
        log.warning("Ignoring CSS at-rule that could not be parsed: %s", error)
        return self._skipAtRule(ctxsrc)

    def _parseRulesetOrSkip(self, src, stylesheetElements):
        """Parse one ruleset, or drop it if its selector is malformed."""
        try:
            src, ruleset = self._parseRuleset(src)
        except self.ParseError as exc:
            log.warning("Ignoring CSS rule that could not be parsed: %s", exc)
            return self._skipMalformedRuleset(src)
        stylesheetElements.append(ruleset)
        return src

    def _parseStylesheet(self, src):
        """
        Stylesheet
        : [ CHARSET_SYM S* STRING S* ';' ]?
            [S|CDO|CDC]* [ import [S|CDO|CDC]* ]*
            [ [ ruleset | media | page | font_face ] [S|CDO|CDC]* ]*
        ;
        """
        # FIXME: BYTES to STR
        if isinstance(src, bytes):
            src = src.decode()
        # Get rid of the comments
        src = self.re_comment.sub("", src)

        # [ CHARSET_SYM S* STRING S* ';' ]?
        src = self._parseAtCharset(src)

        # [S|CDO|CDC]*
        src = self._parseSCDOCDC(src)
        #  [ import [S|CDO|CDC]* ]*
        src, stylesheetImports = self._parseAtImports(src)

        # [ namespace [S|CDO|CDC]* ]*
        src = self._parseAtNamespace(src)

        stylesheetElements = []

        # [ [ ruleset | atkeywords ] [S|CDO|CDC]* ]*
        while src:  # due to ending with ]*
            if src.startswith("@"):
                # @media, @page, @font-face
                src = self._parseAtKeywordOrSkip(src, stylesheetElements)
            elif src.startswith("}"):
                # No block is open at top level, so this "}" joins the prelude
                # of the next rule, which is dropped together with its block
                # (CSS Syntax 3, "consume a qualified rule").
                # _skipMalformedRuleset hands a leading "}" back unconsumed for
                # an enclosing block to close; here nothing would ever
                # consume it.
                log.warning("Ignoring CSS rule after an unmatched '}': %.40r", src)
                src = self._skipBlock(src[1:])
            else:
                # ruleset
                src = self._parseRulesetOrSkip(src, stylesheetElements)

            # [S|CDO|CDC]*
            src = self._parseSCDOCDC(src)

        stylesheet = self.cssBuilder.stylesheet(stylesheetElements, stylesheetImports)
        return src, stylesheet

    @staticmethod
    def _parseSCDOCDC(src):
        """[S|CDO|CDC]*."""
        while True:
            src = src.lstrip()
            if src.startswith("<!--"):
                src = src[4:]
            elif src.startswith("-->"):
                src = src[3:]
            else:
                break
        return src

    # ~ CSS @ directives ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _parseAtCharset(self, src):
        """[ CHARSET_SYM S* STRING S* ';' ]?."""
        if isAtRuleIdent(src, "charset"):
            ctxsrc = src
            src = stripAtRuleIdent(src)
            charset, src = self._getString(src)
            src = src.lstrip()
            if src[:1] != ";":
                msg = "@charset expected a terminating ';'"
                return self._skipInvalidAtRule(msg, src, ctxsrc)
            src = src[1:].lstrip()

            self.cssBuilder.atCharset(charset)
        return src

    def _parseAtImports(self, src):
        """[ import [S|CDO|CDC]* ]*."""
        result = []
        while isAtRuleIdent(src, "import"):
            ctxsrc = src
            src = stripAtRuleIdent(src)

            import_, src = self._getStringOrURI(src)
            if import_ is None:
                msg = "Import expecting string or url"
                src = self._skipInvalidAtRule(msg, src, ctxsrc)
                src = self._parseSCDOCDC(src)
                continue

            mediums = []
            medium, src = self._getIdent(src.lstrip())
            while medium is not None:
                mediums.append(medium)
                if src[:1] == ",":
                    src = src[1:].lstrip()
                    medium, src = self._getIdent(src)
                else:
                    break

            # XXX No medium inherits and then "all" is appropriate
            if not mediums:
                mediums = ["all"]

            if src[:1] != ";":
                msg = "@import expected a terminating ';'"
                src = self._skipInvalidAtRule(msg, src, ctxsrc)
                src = self._parseSCDOCDC(src)
                continue
            src = src[1:].lstrip()

            stylesheet = self.cssBuilder.atImport(import_, mediums, self)
            if stylesheet is not None:
                result.append(stylesheet)

            src = self._parseSCDOCDC(src)
        return src, result

    def _parseAtNamespace(self, src):
        """
        Namespace :

        @namespace S* [IDENT S*]? [STRING|URI] S* ';' S*
        """
        src = self._parseSCDOCDC(src)
        while isAtRuleIdent(src, "namespace"):
            ctxsrc = src
            src = stripAtRuleIdent(src)

            namespace, src = self._getStringOrURI(src)
            if namespace is None:
                nsPrefix, src = self._getIdent(src)
                if nsPrefix is None:
                    msg = "@namespace expected an identifier or a URI"
                else:
                    namespace, src = self._getStringOrURI(src.lstrip())
                    msg = "@namespace expected a URI"
            else:
                nsPrefix = None

            src = src.lstrip()
            if namespace is not None and src[:1] != ";":
                msg = "@namespace expected a terminating ';'"
                namespace = None
            if namespace is None:
                src = self._skipInvalidAtRule(msg, src, ctxsrc)
                src = self._parseSCDOCDC(src)
                continue
            src = src[1:].lstrip()

            self.cssBuilder.atNamespace(nsPrefix, namespace)

            src = self._parseSCDOCDC(src)
        return src

    def _parseAtKeyword(self, src):
        """[media | page | font_face | unknown_keyword]."""
        ctxsrc = src
        if isAtRuleIdent(src, "media"):
            src, result = self._parseAtMedia(src)
        elif isAtRuleIdent(src, "page"):
            src, result = self._parseAtPage(src)
        elif isAtRuleIdent(src, "font-face"):
            src, result = self._parseAtFontFace(src)
        elif isAtRuleIdent(src, "import"):
            # CSS 2.1 6.3: an @import after any rule other than @charset or
            # another @import is ignored.
            log.warning("Ignoring @import after the first rule: %.40r", src)
            src, result = self._skipAtRule(src), None
        elif isAtRuleIdent(src, "frame"):
            src, result = self._parseAtFrame(src)
        elif src.startswith("@"):
            src, result = self._parseAtIdent(src)
        else:
            msg = "Unknown state in atKeyword"
            raise self.ParseError(msg, src, ctxsrc)
        return src, result

    def _parseAtMedia(self, src):
        """
        Media
        : MEDIA_SYM S* medium [ ',' S* medium ]* '{' S* ruleset* '}' S*
        ;
        """
        ctxsrc = src
        src = src[len("@media ") :].lstrip()
        mediums = []
        while src and src[0] != "{":
            medium, src = self._getIdent(src)
            # make "and ... {" work
            if medium in {None, "and"}:
                # default to mediatype "all"
                if medium is None:
                    mediums.append("all")
                # strip up to curly bracket
                pattern = re.compile(r".*?[{]", re.DOTALL)

                match = re.match(pattern, src)
                src = src[match.end() - 1 :] if match else ""
                break
            mediums.append(medium)
            src = src[1:].lstrip() if src[:1] == "," else src.lstrip()

        if not src.startswith("{"):
            msg = "Ruleset opening '{' not found"
            raise self.ParseError(msg, src, ctxsrc)
        src = src[1:].lstrip()

        stylesheetElements = []
        # while src and not src.startswith('}'):
        #    src, ruleset = self._parseRuleset(src)
        #    stylesheetElements.append(ruleset)
        #    src = src.lstrip()

        # Containing @ where not found and parsed
        while src and not src.startswith("}"):
            if src.startswith("@"):
                # @media, @page, @font-face
                src = self._parseAtKeywordOrSkip(src, stylesheetElements)
            else:
                # ruleset
                src = self._parseRulesetOrSkip(src, stylesheetElements)
            src = src.lstrip()

        # The loop stops at the closing "}" or at the end of the stylesheet,
        # which closes any block still open (CSS Syntax 3), as it already did
        # for @page. Raising there used to cost the whole document.
        src = src[1:].lstrip()

        result = self.cssBuilder.atMedia(mediums, stylesheetElements)
        return src, result

    def _parseAtPage(self, src):
        """
        Page
        : PAGE_SYM S* IDENT? pseudo_page? S*
            '{' S* declaration [ ';' S* declaration ]* '}' S*
        ;
        """
        data = {}
        pageBorder = None
        isLandscape = False

        ctxsrc = src
        src = src[len("@page") :].lstrip()
        page, src = self._getIdent(src)
        if src[:1] == ":":
            pseudopage, src = self._getIdent(src[1:])
            # A pseudo-page written without a name -- "@page :left", which is
            # how CSS paged media spells it -- belongs to the page a plain
            # "@page" defines. This used to be "page + '_' + pseudopage" and
            # raised a TypeError on the standard form, aborting the document.
            page = f"{page or xhtml2pdf.default.DEFAULT_PAGE_NAME}_{pseudopage}"
            if pseudopage not in self.PAGE_PSEUDO_CLASSES:
                # Registered all the same, so that any @frame declared inside
                # is consumed and does not leak into the next @page, but
                # nothing will ever select it.
                log.warning(
                    "Unsupported pseudo page :%s, the rules in it will not be"
                    " used. Only :left and :right are honoured.",
                    pseudopage,
                )
        else:
            pseudopage = None

        # src, properties = self._parseDeclarationGroup(src.lstrip())

        # Containing @ where not found and parsed
        stylesheetElements = []
        src = src.lstrip()
        properties = []

        # XXX Extended for PDF use
        if not src.startswith("{"):
            msg = "Ruleset opening '{' not found"
            raise self.ParseError(msg, src, ctxsrc)
        src = src[1:].lstrip()

        while src and not src.startswith("}"):
            if src.startswith("@"):
                # @media, @page, @font-face
                src = self._parseAtKeywordOrSkip(src, stylesheetElements)
            else:
                src, nproperties = self._parseDeclarationGroup(
                    src.lstrip(), braces=False
                )
                properties += nproperties

                # Set pagesize, orientation (landscape, portrait)
                data = {}
                pageBorder = None

                if properties:
                    result = self.cssBuilder.ruleset(
                        [self.cssBuilder.selector("*")], properties
                    )
                    try:
                        data = result[0].values()[0]
                    except Exception:
                        data = result[0].popitem()[1]
                    pageBorder = data.get("-pdf-frame-border", None)

                if "-pdf-page-size" in data:
                    self.c.pageSize = xhtml2pdf.default.PML_PAGESIZES.get(
                        str(data["-pdf-page-size"]).lower(), self.c.pageSize
                    )

                isLandscape = False
                if "size" in data:
                    size = data["size"]
                    if not isinstance(size, list):
                        size = [size]
                    sizeList = []
                    for value in size:
                        valueStr = str(value).lower()
                        if isinstance(value, tuple):
                            sizeList.append(getSize(value))
                        elif valueStr == "landscape":
                            isLandscape = True
                        elif valueStr == "portrait":
                            isLandscape = False
                        elif valueStr in xhtml2pdf.default.PML_PAGESIZES:
                            self.c.pageSize = xhtml2pdf.default.PML_PAGESIZES[valueStr]
                        else:
                            # Not a paper name, not an orientation, not a
                            # length: nothing here can use it. Every other
                            # unreadable value in a stylesheet is dropped with
                            # a warning, and this used to be the one that threw
                            # the whole document away instead.
                            log.warning(
                                "Unknown size value for @page: %r, keeping %r",
                                value,
                                self.c.pageSize,
                            )

                    if len(sizeList) == 2:
                        self.c.pageSize = tuple(sizeList)

                    if isLandscape:
                        self.c.pageSize = landscape(self.c.pageSize)

            src = src.lstrip()

        result = [
            self.cssBuilder.atPage(
                page, pseudopage, data, isLandscape=isLandscape, pageBorder=pageBorder
            )
        ]

        return src[1:].lstrip(), result

    def _parseAtFrame(self, src):
        """XXX Proprietary for PDF."""
        src = src[len("@frame ") :].lstrip()
        box, src = self._getIdent(src)
        src, properties = self._parseDeclarationGroup(src.lstrip())
        result = [self.cssBuilder.atFrame(box, properties)]
        return src.lstrip(), result

    def _parseAtFontFace(self, src):
        src = src[len("@font-face") :].lstrip()
        src, properties = self._parseDeclarationGroup(src)
        result = [self.cssBuilder.atFontFace(properties)]
        return src, result

    def _parseAtIdent(self, src):
        ctxsrc = src
        atIdent, src = self._getIdent(src[1:])
        if atIdent is None:
            msg = "At-rule expected an identifier for the rule"
            raise self.ParseError(msg, src, ctxsrc)

        src, result = self.cssBuilder.atIdent(atIdent, self, src)

        if result is NotImplemented:
            # Nothing here uses the rule (@keyframes, @supports, @layer, ...),
            # so skip it whole. Parsing its block as a stylesheet used to read
            # the block's own "}" as a stray top-level one.
            src = self._skipAtRule(src)

        return src.lstrip(), result

    # ~ ruleset - see selector and declaration groups ~~~~

    def _parseRuleset(self, src):
        """
        Ruleset
        : selector [ ',' S* selector ]*
            '{' S* declaration [ ';' S* declaration ]* '}' S*
        ;
        """
        src, selectors = self._parseSelectorGroup(src)
        src, properties = self._parseDeclarationGroup(src.lstrip())
        result = self.cssBuilder.ruleset(selectors, properties)
        return src, result

    # ~ selector parsing ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _parseSelectorGroup(self, src):
        selectors = []
        while src[:1] not in {"{", "}", "]", "(", ")", ";", ""}:
            src, selector = self._parseSelector(src)
            if selector is None:
                break
            selectors.append(selector)
            if src.startswith(","):
                src = src[1:].lstrip()
        return src, selectors

    def _parseSelector(self, src):
        """
        Selector
        : simple_selector [ combinator simple_selector ]*
        ;
        """
        src, selector = self._parseSimpleSelector(src)
        srcLen = len(src)  # XXX
        while src[:1] not in {"", ",", ";", "{", "}", "[", "]", "(", ")"}:
            for combiner in self.SelectorCombiners:
                if src.startswith(combiner):
                    src = src[len(combiner) :].lstrip()
                    break
            else:
                combiner = " "
            src, selectorB = self._parseSimpleSelector(src)

            # XXX Fix a bug that occurred here e.g. : .1 {...}
            if len(src) >= srcLen:
                src = src[1:]
                while src and (
                    src[:1] not in {"", ",", ";", "{", "}", "[", "]", "(", ")"}
                ):
                    src = src[1:]
                return src.lstrip(), None

            selector = self.cssBuilder.combineSelectors(selector, combiner, selectorB)

        return src.lstrip(), selector

    def _parseSimpleSelector(self, src):
        """
        simple_selector
        : [ namespace_selector ]? element_name? [ HASH | class | attrib | pseudo ]* S*
        ;
        """
        ctxsrc = src.lstrip()
        nsPrefix, src = self._getMatchResult(self.re_namespace_selector, src)
        name, src = self._getMatchResult(self.re_element_name, src)
        if name:
            pass  # already *successfully* assigned
        elif src[:1] in self.SelectorQualifiers:
            name = "*"
        else:
            msg = "Selector name or qualifier expected"
            raise self.ParseError(msg, src, ctxsrc)

        name = self.cssBuilder.resolveNamespacePrefix(nsPrefix, name)
        selector = self.cssBuilder.selector(name)
        while src and src[:1] in self.SelectorQualifiers:
            hash_, src = self._getMatchResult(self.re_hash, src)
            if hash_ is not None:
                selector.addHashId(hash_)
                continue

            class_, src = self._getMatchResult(self.re_class, src)
            if class_ is not None:
                selector.addClass(class_)
                continue

            if src.startswith("["):
                src, selector = self._parseSelectorAttribute(src, selector)
            elif src.startswith(":"):
                src, selector = self._parseSelectorPseudo(src, selector)
            else:
                break

        return src.lstrip(), selector

    def _parseSelectorAttribute(self, src, selector):
        """
        Attrib
        : '[' S* [ namespace_selector ]? IDENT S* [ [ '=' | INCLUDES | DASHMATCH ] S*
            [ IDENT | STRING ] S* ]? ']'
        ;
        """
        ctxsrc = src
        if not src.startswith("["):
            msg = "Selector Attribute opening '[' not found"
            raise self.ParseError(msg, src, ctxsrc)
        src = src[1:].lstrip()

        nsPrefix, src = self._getMatchResult(self.re_namespace_selector, src)
        attrName, src = self._getIdent(src)

        src = src.lstrip()

        if attrName is None:
            msg = "Expected a selector attribute name"
            raise self.ParseError(msg, src, ctxsrc)
        if nsPrefix is not None:
            attrName = self.cssBuilder.resolveNamespacePrefix(nsPrefix, attrName)

        for op in self.AttributeOperators:
            if src.startswith(op):
                break
        else:
            op = ""
        src = src[len(op) :].lstrip()

        if op:
            attr_value, src = self._getIdent(src)
            if attr_value is None:
                attr_value, src = self._getString(src)
                if attr_value is None:
                    msg = "Expected a selector attribute value"
                    raise self.ParseError(msg, src, ctxsrc)
        else:
            attr_value = None

        if not src.startswith("]"):
            msg = "Selector Attribute closing ']' not found"
            raise self.ParseError(msg, src, ctxsrc)
        src = src[1:]

        if op:
            selector.addAttributeOperation(attrName, op, attr_value)
        else:
            selector.addAttribute(attrName)
        return src, selector

    def _parseSelectorPseudo(self, src, selector):
        """
        Pseudo
        : ':' [ IDENT | function ]
        ;
        """
        ctxsrc = src
        if not src.startswith(":"):
            msg = "Selector Pseudo ':' not found"
            raise self.ParseError(msg, src, ctxsrc)
        src = re.search(r"^:{1,2}(.*)", src, re.MULTILINE | re.DOTALL).group(1)

        name, src = self._getIdent(src)
        if not name:
            msg = "Selector Pseudo identifier not found"
            raise self.ParseError(msg, src, ctxsrc)

        if src.startswith("("):
            # function
            src = src[1:].lstrip()
            src, term = self._parseExpression(src, return_list=True)
            if not src.startswith(")"):
                msg = "Selector Pseudo Function closing ')' not found"
                raise self.ParseError(msg, src, ctxsrc)
            src = src[1:]
            selector.addPseudoFunction(name, term)
        else:
            selector.addPseudo(name)

        return src, selector

    # ~ declaration and expression parsing ~~~~~~~~~~~~~~~

    def _parseDeclarationGroup(self, src, *, braces=True):
        ctxsrc = src
        if src.startswith("{"):
            src, braces = src[1:], True
        elif braces:
            msg = "Declaration group opening '{' not found"
            raise self.ParseError(msg, src, ctxsrc)

        # A declaration list ends at its "}" or at the end of the source. Without
        # braces -- the body of @page -- an at-rule ends it too.
        ends = {"", "}"} if braces else {"", "}", "@"}
        properties = []
        src = src.lstrip()
        while src[:1] not in ends:
            if src.startswith(";"):
                # An empty declaration, as in "color: red;;" or "{;".
                src = src[1:].lstrip()
                continue
            start = src
            try:
                src, single_property = self._parseDeclaration(src)
            except self.ParseError:
                single_property = None
            if single_property is None or src[:1] not in ends | {";"}:
                # CSS Syntax 3: an invalid declaration is dropped, up to the
                # ";" that ends it, and the rest of the block still applies.
                # This used to drop the whole rule, or with an inline style
                # raise out of the document.
                log.warning(
                    "Ignoring CSS declaration that could not be parsed: %.40r", start
                )
                src = self._skipDeclaration(start).lstrip()
                if src.startswith(";"):
                    src = src[1:].lstrip()
                continue
            properties.append(single_property)

        if braces:
            # The end of the stylesheet closes the block, as for @media.
            src = src[1:]

        return src.lstrip(), properties

    def _parseDeclaration(self, src):
        """
        Declaration
        : ident S* ':' S* expr prio?
        | /* empty */
        ;
        """
        # property
        property_name, src = self._getIdent(src)

        if property_name is not None:
            src = src.lstrip()
            # S* : S*
            if src[:1] in {":", "="}:
                # Note: we are being fairly flexible here...  technically, the
                # ":" is *required*, but in the name of flexibility we
                # support a null transition, as well as an "=" transition
                src = src[1:].lstrip()

            src, single_property = self._parseDeclarationProperty(src, property_name)
        else:
            single_property = None

        return src, single_property

    def _parseDeclarationProperty(self, src, property_name):
        # expr
        src, expr = self._parseExpression(src)

        # prio?
        important, src = self._getMatchResult(self.re_important, src)
        src = src.lstrip()

        single_property = self.cssBuilder.property(
            property_name, expr, important=important
        )
        return src, single_property

    def _parseExpression(self, src, *, return_list=False):
        """
        Expr
        : term [ operator term ]*
        ;
        """
        src, term = self._parseExpressionTerm(src)
        operator = None
        while src[:1] not in {"", ";", "{", "}", "[", "]", ")"}:
            for operator in self.ExpressionOperators:
                if src.startswith(operator):
                    src = src[len(operator) :]
                    break
            else:
                operator = " "
            src, term2 = self._parseExpressionTerm(src.lstrip())
            if term2 is NotImplemented:
                break
            term = self.cssBuilder.combineTerms(term, operator, term2)

        if operator is None and return_list:
            term = self.cssBuilder.combineTerms(term, None, None)
            return src, term
        return src, term

    def _parseExpressionTerm(self, src):
        """
        Term
        : unary_operator?
            [ NUMBER S* | PERCENTAGE S* | LENGTH S* | EMS S* | EXS S* | ANGLE S* |
            TIME S* | FREQ S* | function ]
        | STRING S* | IDENT S* | URI S* | RGB S* | UNICODERANGE S* | hexcolor
        ;
        """
        ctxsrc = src

        result, src = self._getMatchResult(self.re_num, src)
        if result is not None:
            units, src = self._getMatchResult(self.re_unit, src)
            term = self.cssBuilder.termNumber(result, units)
            return src.lstrip(), term

        result, src = self._getString(src, self.re_uri)
        if result is not None:
            # XXX URL!!!!
            term = self.cssBuilder.termURI(result)
            return src.lstrip(), term

        result, src = self._getString(src)
        if result is not None:
            term = self.cssBuilder.termString(result)
            return src.lstrip(), term

        result, src = self._getMatchResult(self.re_functionterm, src)
        if result is not None:
            src, params = self._parseExpression(src, return_list=True)
            if src[:1] != ")":
                msg = "Terminal function expression expected closing ')'"
                raise self.ParseError(msg, src, ctxsrc)
            src = src[1:].lstrip()
            term = self.cssBuilder.termFunction(result, params)
            return src, term

        result, src = self._getMatchResult(self.re_rgbcolor, src)
        if result is not None:
            term = self.cssBuilder.termRGB(result)
            return src.lstrip(), term

        result, src = self._getMatchResult(self.re_unicoderange, src)
        if result is not None:
            term = self.cssBuilder.termUnicodeRange(result)
            return src.lstrip(), term

        nsPrefix, src = self._getMatchResult(self.re_namespace_selector, src)
        result, src = self._getIdent(src)
        if result is not None:
            if nsPrefix is not None:
                result = self.cssBuilder.resolveNamespacePrefix(nsPrefix, result)
            term = self.cssBuilder.termIdent(result)
            return src.lstrip(), term

        return self.cssBuilder.termUnknown(src)

    # ~ utility methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _getIdent(self, src, default=None):
        return self._getMatchResult(self.re_ident, src, default)

    def _getString(self, src, rexpression=None, default=None):
        if rexpression is None:
            rexpression = self.re_string
        result = rexpression.match(src)
        if result:
            strres = tuple(filter(None, result.groups()))
            if strres:
                try:
                    strres = strres[0]
                except Exception:
                    strres = result.groups()[0]
            else:
                strres = ""
            return strres, src[result.end() :]
        return default, src

    def _getStringOrURI(self, src):
        result, src = self._getString(src, self.re_uri)
        if result is None:
            result, src = self._getString(src)
        return result, src

    @staticmethod
    def _getMatchResult(rexpression, src, default=None, group=1):
        result = rexpression.match(src)
        if result:
            return result.group(group), src[result.end() :]
        return default, src
