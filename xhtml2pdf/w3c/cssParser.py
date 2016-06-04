#!/usr/bin/env python

##~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
##~ Copyright (C) 2002-2004  TechGame Networks, LLC.
##~
##~ This library is free software; you can redistribute it and/or
##~ modify it under the terms of the BSD style License as found in the
##~ LICENSE file included with this distribution.
##
##  Modified by Dirk Holtwick <holtwick@web.de>, 2007-2008
##~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
from __future__ import absolute_import


# Added by benjaoming to fix python3 tests
from __future__ import unicode_literals

"""CSS-2.1 parser.

The CSS 2.1 Specification this parser was derived from can be found at http://www.w3.org/TR/CSS21/

Primary Classes:
    * CSSParser
        Parses CSS source forms into results using a Builder Pattern.  Must
        provide concrete implemenation of CSSBuilderAbstract.

    * CSSBuilderAbstract
        Outlines the interface between CSSParser and it's rule-builder.
        Compose CSSParser with a concrete implementation of the builder to get
        usable results from the CSS parser.

Dependencies:
    python 2.3 (or greater)
    re
"""

import re
import six

from . import cssSpecial


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ Definitions
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def isAtRuleIdent(src, ident):
    return re.match(r'^@' + ident + r'\s*', src)


def stripAtRuleIdent(src):
    return re.sub(r'^@[a-z\-]+\s*', '', src)


class CSSSelectorAbstract(object):
    """Outlines the interface between CSSParser and it's rule-builder for selectors.

    CSSBuilderAbstract.selector and CSSBuilderAbstract.combineSelectors must
    return concrete implementations of this abstract.

    See css.CSSMutableSelector for an example implementation.
    """


    def addHashId(self, hashId):
        raise NotImplementedError('Subclass responsibility')


    def addClass(self, class_):
        raise NotImplementedError('Subclass responsibility')


    def addAttribute(self, attrName):
        raise NotImplementedError('Subclass responsibility')


    def addAttributeOperation(self, attrName, op, attrValue):
        raise NotImplementedError('Subclass responsibility')


    def addPseudo(self, name):
        raise NotImplementedError('Subclass responsibility')


    def addPseudoFunction(self, name, value):
        raise NotImplementedError('Subclass responsibility')


class CSSBuilderAbstract(object):
    """Outlines the interface between CSSParser and it's rule-builder.  Compose
    CSSParser with a concrete implementation of the builder to get usable
    results from the CSS parser.

    See css.CSSBuilder for an example implementation
    """


    def setCharset(self, charset):
        raise NotImplementedError('Subclass responsibility')


    #~ css results ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def beginStylesheet(self):
        raise NotImplementedError('Subclass responsibility')


    def stylesheet(self, elements):
        raise NotImplementedError('Subclass responsibility')


    def endStylesheet(self):
        raise NotImplementedError('Subclass responsibility')


    def beginInline(self):
        raise NotImplementedError('Subclass responsibility')


    def inline(self, declarations):
        raise NotImplementedError('Subclass responsibility')


    def endInline(self):
        raise NotImplementedError('Subclass responsibility')


    def ruleset(self, selectors, declarations):
        raise NotImplementedError('Subclass responsibility')


    #~ css namespaces ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def resolveNamespacePrefix(self, nsPrefix, name):
        raise NotImplementedError('Subclass responsibility')


    #~ css @ directives ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def atCharset(self, charset):
        raise NotImplementedError('Subclass responsibility')


    def atImport(self, import_, mediums, cssParser):
        raise NotImplementedError('Subclass responsibility')


    def atNamespace(self, nsPrefix, uri):
        raise NotImplementedError('Subclass responsibility')


    def atMedia(self, mediums, ruleset):
        raise NotImplementedError('Subclass responsibility')


    def atPage(self, page, pseudopage, declarations):
        raise NotImplementedError('Subclass responsibility')


    def atFontFace(self, declarations):
        raise NotImplementedError('Subclass responsibility')


    def atIdent(self, atIdent, cssParser, src):
        return src, NotImplemented


    #~ css selectors ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def combineSelectors(self, selectorA, combiner, selectorB):
        """Return value must implement CSSSelectorAbstract"""
        raise NotImplementedError('Subclass responsibility')


    def selector(self, name):
        """Return value must implement CSSSelectorAbstract"""
        raise NotImplementedError('Subclass responsibility')


    #~ css declarations ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def property(self, name, value, important=False):
        raise NotImplementedError('Subclass responsibility')


    def combineTerms(self, termA, combiner, termB):
        raise NotImplementedError('Subclass responsibility')


    def termIdent(self, value):
        raise NotImplementedError('Subclass responsibility')


    def termNumber(self, value, units=None):
        raise NotImplementedError('Subclass responsibility')


    def termRGB(self, value):
        raise NotImplementedError('Subclass responsibility')


    def termURI(self, value):
        raise NotImplementedError('Subclass responsibility')


    def termString(self, value):
        raise NotImplementedError('Subclass responsibility')


    def termUnicodeRange(self, value):
        raise NotImplementedError('Subclass responsibility')


    def termFunction(self, name, value):
        raise NotImplementedError('Subclass responsibility')


    def termUnknown(self, src):
        raise NotImplementedError('Subclass responsibility')

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ CSS Parser
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSParseError(Exception):
    src = None
    ctxsrc = None
    fullsrc = None
    inline = False
    srcCtxIdx = None
    srcFullIdx = None
    ctxsrcFullIdx = None


    def __init__(self, msg, src, ctxsrc=None):
        Exception.__init__(self, msg)
        self.src = src
        self.ctxsrc = ctxsrc or src
        if self.ctxsrc:
            self.srcCtxIdx = self.ctxsrc.find(self.src)
            if self.srcCtxIdx < 0:
                del self.srcCtxIdx


    def __str__(self):
        if self.ctxsrc:
            return Exception.__str__(self) + ':: (' + repr(self.ctxsrc[:self.srcCtxIdx]) + ', ' + repr(
                self.ctxsrc[self.srcCtxIdx:self.srcCtxIdx + 20]) + ')'
        else:
            return Exception.__str__(self) + ':: ' + repr(self.src[:40])


    def setFullCSSSource(self, fullsrc, inline=False):
        self.fullsrc = fullsrc
        if inline:
            self.inline = inline
        if self.fullsrc:
            self.srcFullIdx = self.fullsrc.find(self.src)
            if self.srcFullIdx < 0:
                del self.srcFullIdx
            self.ctxsrcFullIdx = self.fullsrc.find(self.ctxsrc)
            if self.ctxsrcFullIdx < 0:
                del self.ctxsrcFullIdx

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSParser(object):
    """CSS-2.1 parser dependent only upon the re module.

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

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~ Constants / Variables / Etc.
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ParseError = CSSParseError

    AttributeOperators = ['=', '~=', '|=', '&=', '^=', '!=', '<>']
    SelectorQualifiers = ('#', '.', '[', ':')
    SelectorCombiners = ['+', '>']
    ExpressionOperators = ('/', '+', ',')

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~ Regular expressions
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    if True: # makes the following code foldable
        _orRule = lambda *args: '|'.join(args)
        _reflags = re.I | re.M | re.U
        i_hex = '[0-9a-fA-F]'
        i_nonascii = '[\200-\377]'
        i_unicode = '\\\\(?:%s){1,6}\s?' % i_hex
        i_escape = _orRule(i_unicode, '\\\\[ -~\200-\377]')
        # i_nmstart = _orRule('[A-Za-z_]', i_nonascii, i_escape)
        i_nmstart = _orRule('\-[^0-9]|[A-Za-z_]', i_nonascii,
                            i_escape) # XXX Added hyphen, http://www.w3.org/TR/CSS21/syndata.html#value-def-identifier
        i_nmchar = _orRule('[-0-9A-Za-z_]', i_nonascii, i_escape)
        i_ident = '((?:%s)(?:%s)*)' % (i_nmstart, i_nmchar)
        re_ident = re.compile(i_ident, _reflags)
        # Caution: treats all characters above 0x7f as legal for an identifier.
        i_unicodeid = r'([^\u0000-\u007f]+)'
        re_unicodeid = re.compile(i_unicodeid, _reflags)
        i_unicodestr1 = r'(\'[^\u0000-\u007f]+\')'
        i_unicodestr2 = r'(\"[^\u0000-\u007f]+\")'
        i_unicodestr = _orRule(i_unicodestr1, i_unicodestr2)
        re_unicodestr = re.compile(i_unicodestr, _reflags)
        i_element_name = '((?:%s)|\*)' % (i_ident[1:-1],)
        re_element_name = re.compile(i_element_name, _reflags)
        i_namespace_selector = '((?:%s)|\*|)\|(?!=)' % (i_ident[1:-1],)
        re_namespace_selector = re.compile(i_namespace_selector, _reflags)
        i_class = '\\.' + i_ident
        re_class = re.compile(i_class, _reflags)
        i_hash = '#((?:%s)+)' % i_nmchar
        re_hash = re.compile(i_hash, _reflags)
        i_rgbcolor = '(#%s{6}|#%s{3})' % (i_hex, i_hex)
        re_rgbcolor = re.compile(i_rgbcolor, _reflags)
        i_nl = '\n|\r\n|\r|\f'
        i_escape_nl = '\\\\(?:%s)' % i_nl
        i_string_content = _orRule('[\t !#$%&(-~]', i_escape_nl, i_nonascii, i_escape)
        i_string1 = '\"((?:%s|\')*)\"' % i_string_content
        i_string2 = '\'((?:%s|\")*)\'' % i_string_content
        i_string = _orRule(i_string1, i_string2)
        re_string = re.compile(i_string, _reflags)
        i_uri = ('url\\(\s*(?:(?:%s)|((?:%s)+))\s*\\)'
                 % (i_string, _orRule('[!#$%&*-~]', i_nonascii, i_escape)))
        # XXX For now
        # i_uri = '(url\\(.*?\\))'
        re_uri = re.compile(i_uri, _reflags)
        i_num = '(([-+]?[0-9]+(?:\\.[0-9]+)?)|([-+]?\\.[0-9]+))' # XXX Added out paranthesis, because e.g. .5em was not parsed correctly
        re_num = re.compile(i_num, _reflags)
        i_unit = '(%%|%s)?' % i_ident
        re_unit = re.compile(i_unit, _reflags)
        i_function = i_ident + '\\('
        re_function = re.compile(i_function, _reflags)
        i_functionterm = '[-+]?' + i_function
        re_functionterm = re.compile(i_functionterm, _reflags)
        i_unicoderange1 = "(?:U\\+%s{1,6}-%s{1,6})" % (i_hex, i_hex)
        i_unicoderange2 = "(?:U\\+\?{1,6}|{h}(\?{0,5}|{h}(\?{0,4}|{h}(\?{0,3}|{h}(\?{0,2}|{h}(\??|{h}))))))"
        i_unicoderange = i_unicoderange1 # '(%s|%s)' % (i_unicoderange1, i_unicoderange2)
        re_unicoderange = re.compile(i_unicoderange, _reflags)

        # i_comment = '(?:\/\*[^*]*\*+([^/*][^*]*\*+)*\/)|(?://.*)'
        # gabriel: only C convention for comments is allowed in CSS
        i_comment = '(?:\/\*[^*]*\*+([^/*][^*]*\*+)*\/)'
        re_comment = re.compile(i_comment, _reflags)
        i_important = '!\s*(important)'
        re_important = re.compile(i_important, _reflags)
        del _orRule

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~ Public
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def __init__(self, cssBuilder=None):
        self.setCSSBuilder(cssBuilder)


    #~ CSS Builder to delegate to ~~~~~~~~~~~~~~~~~~~~~~~~

    def getCSSBuilder(self):
        """A concrete instance implementing CSSBuilderAbstract"""
        return self._cssBuilder


    def setCSSBuilder(self, cssBuilder):
        """A concrete instance implementing CSSBuilderAbstract"""
        self._cssBuilder = cssBuilder


    cssBuilder = property(getCSSBuilder, setCSSBuilder)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~ Public CSS Parsing API
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def parseFile(self, srcFile, closeFile=False):
        """Parses CSS file-like objects using the current cssBuilder.
        Use for external stylesheets."""

        try:
            result = self.parse(srcFile.read())
        finally:
            if closeFile:
                srcFile.close()
        return result


    def parse(self, src):
        """Parses CSS string source using the current cssBuilder.
        Use for embedded stylesheets."""

        self.cssBuilder.beginStylesheet()
        try:

            # XXX Some simple preprocessing
            src = cssSpecial.cleanupCSS(src)

            try:
                src, stylesheet = self._parseStylesheet(src)
            except self.ParseError as err:
                err.setFullCSSSource(src)
                raise
        finally:
            self.cssBuilder.endStylesheet()
        return stylesheet


    def parseInline(self, src):
        """Parses CSS inline source string using the current cssBuilder.
        Use to parse a tag's 'sytle'-like attribute."""

        self.cssBuilder.beginInline()
        try:
            try:
                src, properties = self._parseDeclarationGroup(src.strip(), braces=False)
            except self.ParseError as err:
                err.setFullCSSSource(src, inline=True)
                raise

            result = self.cssBuilder.inline(properties)
        finally:
            self.cssBuilder.endInline()
        return result

    def parseAttributes(self, attributes=None, **kwAttributes):
        """Parses CSS attribute source strings, and return as an inline stylesheet.
        Use to parse a tag's highly CSS-based attributes like 'font'.

        See also: parseSingleAttr
        """
        attributes = attributes if attributes is not None else {}
        if attributes:
            kwAttributes.update(attributes)

        self.cssBuilder.beginInline()
        try:
            properties = []
            try:
                for propertyName, src in six.iteritems(kwAttributes):
                    src, property = self._parseDeclarationProperty(src.strip(), propertyName)
                    properties.append(property)

            except self.ParseError as err:
                err.setFullCSSSource(src, inline=True)
                raise

            result = self.cssBuilder.inline(properties)
        finally:
            self.cssBuilder.endInline()
        return result


    def parseSingleAttr(self, attrValue):
        """Parse a single CSS attribute source string, and returns the built CSS expression.
        Use to parse a tag's highly CSS-based attributes like 'font'.

        See also: parseAttributes
        """

        results = self.parseAttributes(temp=attrValue)
        if 'temp' in results[1]:
            return results[1]['temp']
        else:
            return results[0]['temp']


    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~ Internal _parse methods
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _parseStylesheet(self, src):
        """stylesheet
        : [ CHARSET_SYM S* STRING S* ';' ]?
            [S|CDO|CDC]* [ import [S|CDO|CDC]* ]*
            [ [ ruleset | media | page | font_face ] [S|CDO|CDC]* ]*
        ;
        """
        # Get rid of the comments
        src = self.re_comment.sub('', src)

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
        while src: # due to ending with ]*
            if src.startswith('@'):
                # @media, @page, @font-face
                src, atResults = self._parseAtKeyword(src)
                if atResults is not None and atResults != NotImplemented:
                    stylesheetElements.extend(atResults)
            else:
                # ruleset
                src, ruleset = self._parseRuleset(src)
                stylesheetElements.append(ruleset)

            # [S|CDO|CDC]*
            src = self._parseSCDOCDC(src)

        stylesheet = self.cssBuilder.stylesheet(stylesheetElements, stylesheetImports)
        return src, stylesheet


    def _parseSCDOCDC(self, src):
        """[S|CDO|CDC]*"""
        while 1:
            src = src.lstrip()
            if src.startswith('<!--'):
                src = src[4:]
            elif src.startswith('-->'):
                src = src[3:]
            else:
                break
        return src


    #~ CSS @ directives ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _parseAtCharset(self, src):
        """[ CHARSET_SYM S* STRING S* ';' ]?"""
        if isAtRuleIdent(src, 'charset'):
            src = stripAtRuleIdent(src)
            charset, src = self._getString(src)
            src = src.lstrip()
            if src[:1] != ';':
                raise self.ParseError('@charset expected a terminating \';\'', src, self.ctxsrc)
            src = src[1:].lstrip()

            self.cssBuilder.atCharset(charset)
        return src


    def _parseAtImports(self, src):
        """[ import [S|CDO|CDC]* ]*"""
        result = []
        while isAtRuleIdent(src, 'import'):
            ctxsrc = src
            src = stripAtRuleIdent(src)

            import_, src = self._getStringOrURI(src)
            if import_ is None:
                raise self.ParseError('Import expecting string or url', src, ctxsrc)

            mediums = []
            medium, src = self._getIdent(src.lstrip())
            while medium is not None:
                mediums.append(medium)
                if src[:1] == ',':
                    src = src[1:].lstrip()
                    medium, src = self._getIdent(src)
                else:
                    break

            # XXX No medium inherits and then "all" is appropriate
            if not mediums:
                mediums = ["all"]

            if src[:1] != ';':
                raise self.ParseError('@import expected a terminating \';\'', src, ctxsrc)
            src = src[1:].lstrip()

            stylesheet = self.cssBuilder.atImport(import_, mediums, self)
            if stylesheet is not None:
                result.append(stylesheet)

            src = self._parseSCDOCDC(src)
        return src, result


    def _parseAtNamespace(self, src):
        """namespace :

        @namespace S* [IDENT S*]? [STRING|URI] S* ';' S*
        """

        src = self._parseSCDOCDC(src)
        while isAtRuleIdent(src, 'namespace'):
            ctxsrc = src
            src = stripAtRuleIdent(src)

            namespace, src = self._getStringOrURI(src)
            if namespace is None:
                nsPrefix, src = self._getIdent(src)
                if nsPrefix is None:
                    raise self.ParseError('@namespace expected an identifier or a URI', src, ctxsrc)
                namespace, src = self._getStringOrURI(src.lstrip())
                if namespace is None:
                    raise self.ParseError('@namespace expected a URI', src, ctxsrc)
            else:
                nsPrefix = None

            src = src.lstrip()
            if src[:1] != ';':
                raise self.ParseError('@namespace expected a terminating \';\'', src, ctxsrc)
            src = src[1:].lstrip()

            self.cssBuilder.atNamespace(nsPrefix, namespace)

            src = self._parseSCDOCDC(src)
        return src


    def _parseAtKeyword(self, src):
        """[media | page | font_face | unknown_keyword]"""
        ctxsrc = src
        if isAtRuleIdent(src, 'media'):
            src, result = self._parseAtMedia(src)
        elif isAtRuleIdent(src, 'page'):
            src, result = self._parseAtPage(src)
        elif isAtRuleIdent(src, 'font-face'):
            src, result = self._parseAtFontFace(src)
        # XXX added @import, was missing!
        elif isAtRuleIdent(src, 'import'):
            src, result = self._parseAtImports(src)
        elif isAtRuleIdent(src, 'frame'):
            src, result = self._parseAtFrame(src)
        elif src.startswith('@'):
            src, result = self._parseAtIdent(src)
        else:
            raise self.ParseError('Unknown state in atKeyword', src, ctxsrc)
        return src, result


    def _parseAtMedia(self, src):
        """media
        : MEDIA_SYM S* medium [ ',' S* medium ]* '{' S* ruleset* '}' S*
        ;
        """
        ctxsrc = src
        src = src[len('@media '):].lstrip()
        mediums = []
        while src and src[0] != '{':
            medium, src = self._getIdent(src)
            if medium is None:
                raise self.ParseError('@media rule expected media identifier', src, ctxsrc)
            # make "and ... {" work
            if medium == 'and':
                # strip up to curly bracket
                pattern = re.compile('.*({.*)')
                match = re.match(pattern, src)
                src = src[match.end()-1:]
                break
            mediums.append(medium)
            if src[0] == ',':
                src = src[1:].lstrip()
            else:
                src = src.lstrip()

        if not src.startswith('{'):
            raise self.ParseError('Ruleset opening \'{\' not found', src, ctxsrc)
        src = src[1:].lstrip()

        stylesheetElements = []
        #while src and not src.startswith('}'):
        #    src, ruleset = self._parseRuleset(src)
        #    stylesheetElements.append(ruleset)
        #    src = src.lstrip()

        # Containing @ where not found and parsed
        while src and not src.startswith('}'):
            if src.startswith('@'):
                # @media, @page, @font-face
                src, atResults = self._parseAtKeyword(src)
                if atResults is not None:
                    stylesheetElements.extend(atResults)
            else:
                # ruleset
                src, ruleset = self._parseRuleset(src)
                stylesheetElements.append(ruleset)
            src = src.lstrip()

        if not src.startswith('}'):
            raise self.ParseError('Ruleset closing \'}\' not found', src, ctxsrc)
        else:
            src = src[1:].lstrip()

        result = self.cssBuilder.atMedia(mediums, stylesheetElements)
        return src, result


    def _parseAtPage(self, src):
        """page
        : PAGE_SYM S* IDENT? pseudo_page? S*
            '{' S* declaration [ ';' S* declaration ]* '}' S*
        ;
        """
        ctxsrc = src
        src = src[len('@page'):].lstrip()
        page, src = self._getIdent(src)
        if src[:1] == ':':
            pseudopage, src = self._getIdent(src[1:])
            page = page + '_' + pseudopage
        else:
            pseudopage = None

        #src, properties = self._parseDeclarationGroup(src.lstrip())

        # Containing @ where not found and parsed
        stylesheetElements = []
        src = src.lstrip()
        properties = []

        # XXX Extended for PDF use
        if not src.startswith('{'):
            raise self.ParseError('Ruleset opening \'{\' not found', src, ctxsrc)
        else:
            src = src[1:].lstrip()

        while src and not src.startswith('}'):
            if src.startswith('@'):
                # @media, @page, @font-face
                src, atResults = self._parseAtKeyword(src)
                if atResults is not None:
                    stylesheetElements.extend(atResults)
            else:
                src, nproperties = self._parseDeclarationGroup(src.lstrip(), braces=False)
                properties += nproperties
            src = src.lstrip()

        result = [self.cssBuilder.atPage(page, pseudopage, properties)]

        return src[1:].lstrip(), result


    def _parseAtFrame(self, src):
        """
        XXX Proprietary for PDF
        """
        src = src[len('@frame '):].lstrip()
        box, src = self._getIdent(src)
        src, properties = self._parseDeclarationGroup(src.lstrip())
        result = [self.cssBuilder.atFrame(box, properties)]
        return src.lstrip(), result


    def _parseAtFontFace(self, src):
        src = src[len('@font-face '):].lstrip()
        src, properties = self._parseDeclarationGroup(src)
        result = [self.cssBuilder.atFontFace(properties)]
        return src, result


    def _parseAtIdent(self, src):
        ctxsrc = src
        atIdent, src = self._getIdent(src[1:])
        if atIdent is None:
            raise self.ParseError('At-rule expected an identifier for the rule', src, ctxsrc)

        src, result = self.cssBuilder.atIdent(atIdent, self, src)

        if result is NotImplemented:
            # An at-rule consists of everything up to and including the next semicolon (;) or the next block, whichever comes first

            semiIdx = src.find(';')
            if semiIdx < 0:
                semiIdx = None
            blockIdx = src[:semiIdx].find('{')
            if blockIdx < 0:
                blockIdx = None

            if semiIdx is not None and semiIdx < blockIdx:
                src = src[semiIdx + 1:].lstrip()
            elif blockIdx is None:
                # consume the rest of the content since we didn't find a block or a semicolon
                src = src[-1:-1]
            elif blockIdx is not None:
                # expecing a block...
                src = src[blockIdx:]
                try:
                    # try to parse it as a declarations block
                    src, declarations = self._parseDeclarationGroup(src)
                except self.ParseError:
                    # try to parse it as a stylesheet block
                    src, stylesheet = self._parseStylesheet(src)
            else:
                raise self.ParserError('Unable to ignore @-rule block', src, ctxsrc)

        return src.lstrip(), result


    #~ ruleset - see selector and declaration groups ~~~~

    def _parseRuleset(self, src):
        """ruleset
        : selector [ ',' S* selector ]*
            '{' S* declaration [ ';' S* declaration ]* '}' S*
        ;
        """
        src, selectors = self._parseSelectorGroup(src)
        src, properties = self._parseDeclarationGroup(src.lstrip())
        result = self.cssBuilder.ruleset(selectors, properties)
        return src, result


    #~ selector parsing ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _parseSelectorGroup(self, src):
        selectors = []
        while src[:1] not in ('{', '}', ']', '(', ')', ';', ''):
            src, selector = self._parseSelector(src)
            if selector is None:
                break
            selectors.append(selector)
            if src.startswith(','):
                src = src[1:].lstrip()
        return src, selectors


    def _parseSelector(self, src):
        """selector
        : simple_selector [ combinator simple_selector ]*
        ;
        """
        src, selector = self._parseSimpleSelector(src)
        srcLen = len(src) # XXX
        while src[:1] not in ('', ',', ';', '{', '}', '[', ']', '(', ')'):
            for combiner in self.SelectorCombiners:
                if src.startswith(combiner):
                    src = src[len(combiner):].lstrip()
                    break
            else:
                combiner = ' '
            src, selectorB = self._parseSimpleSelector(src)

            # XXX Fix a bug that occured here e.g. : .1 {...}
            if len(src) >= srcLen:
                src = src[1:]
                while src and (src[:1] not in ('', ',', ';', '{', '}', '[', ']', '(', ')')):
                    src = src[1:]
                return src.lstrip(), None

            selector = self.cssBuilder.combineSelectors(selector, combiner, selectorB)

        return src.lstrip(), selector


    def _parseSimpleSelector(self, src):
        """simple_selector
        : [ namespace_selector ]? element_name? [ HASH | class | attrib | pseudo ]* S*
        ;
        """
        ctxsrc = src.lstrip()
        nsPrefix, src = self._getMatchResult(self.re_namespace_selector, src)
        name, src = self._getMatchResult(self.re_element_name, src)
        if name:
            pass # already *successfully* assigned
        elif src[:1] in self.SelectorQualifiers:
            name = '*'
        else:
            raise self.ParseError('Selector name or qualifier expected', src, ctxsrc)

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

            if src.startswith('['):
                src, selector = self._parseSelectorAttribute(src, selector)
            elif src.startswith(':'):
                src, selector = self._parseSelectorPseudo(src, selector)
            else:
                break

        return src.lstrip(), selector


    def _parseSelectorAttribute(self, src, selector):
        """attrib
        : '[' S* [ namespace_selector ]? IDENT S* [ [ '=' | INCLUDES | DASHMATCH ] S*
            [ IDENT | STRING ] S* ]? ']'
        ;
        """
        ctxsrc = src
        if not src.startswith('['):
            raise self.ParseError('Selector Attribute opening \'[\' not found', src, ctxsrc)
        src = src[1:].lstrip()

        nsPrefix, src = self._getMatchResult(self.re_namespace_selector, src)
        attrName, src = self._getIdent(src)

        src = src.lstrip()

        if attrName is None:
            raise self.ParseError('Expected a selector attribute name', src, ctxsrc)
        if nsPrefix is not None:
            attrName = self.cssBuilder.resolveNamespacePrefix(nsPrefix, attrName)

        for op in self.AttributeOperators:
            if src.startswith(op):
                break
        else:
            op = ''
        src = src[len(op):].lstrip()

        if op:
            attrValue, src = self._getIdent(src)
            if attrValue is None:
                attrValue, src = self._getString(src)
                if attrValue is None:
                    raise self.ParseError('Expected a selector attribute value', src, ctxsrc)
        else:
            attrValue = None

        if not src.startswith(']'):
            raise self.ParseError('Selector Attribute closing \']\' not found', src, ctxsrc)
        else:
            src = src[1:]

        if op:
            selector.addAttributeOperation(attrName, op, attrValue)
        else:
            selector.addAttribute(attrName)
        return src, selector


    def _parseSelectorPseudo(self, src, selector):
        """pseudo
        : ':' [ IDENT | function ]
        ;
        """
        ctxsrc = src
        if not src.startswith(':'):
            raise self.ParseError('Selector Pseudo \':\' not found', src, ctxsrc)
        src = re.search('^:{1,2}(.*)', src, re.M | re.S).group(1)

        name, src = self._getIdent(src)
        if not name:
            raise self.ParseError('Selector Pseudo identifier not found', src, ctxsrc)

        if src.startswith('('):
            # function
            src = src[1:].lstrip()
            src, term = self._parseExpression(src, True)
            if not src.startswith(')'):
                raise self.ParseError('Selector Pseudo Function closing \')\' not found', src, ctxsrc)
            src = src[1:]
            selector.addPseudoFunction(name, term)
        else:
            selector.addPseudo(name)

        return src, selector


    #~ declaration and expression parsing ~~~~~~~~~~~~~~~

    def _parseDeclarationGroup(self, src, braces=True):
        ctxsrc = src
        if src.startswith('{'):
            src, braces = src[1:], True
        elif braces:
            raise self.ParseError('Declaration group opening \'{\' not found', src, ctxsrc)

        properties = []
        src = src.lstrip()
        while src[:1] not in ('', ',', '{', '}', '[', ']', '(', ')', '@'): # XXX @?
            src, property = self._parseDeclaration(src)

            # XXX Workaround for styles like "*font: smaller"
            if src.startswith("*"):
                src = "-nothing-" + src[1:]
                continue

            if property is None:
                src = src[1:].lstrip()
                break
            properties.append(property)
            if src.startswith(';'):
                src = src[1:].lstrip()
            else:
                break

        if braces:
            if not src.startswith('}'):
                raise self.ParseError('Declaration group closing \'}\' not found', src, ctxsrc)
            src = src[1:]

        return src.lstrip(), properties


    def _parseDeclaration(self, src):
        """declaration
        : ident S* ':' S* expr prio?
        | /* empty */
        ;
        """
        # property
        propertyName, src = self._getIdent(src)

        if propertyName is not None:
            src = src.lstrip()
            # S* : S*
            if src[:1] in (':', '='):
                # Note: we are being fairly flexable here...  technically, the
                # ":" is *required*, but in the name of flexibility we
                # suppor a null transition, as well as an "=" transition
                src = src[1:].lstrip()

            src, property = self._parseDeclarationProperty(src, propertyName)
        else:
            property = None

        return src, property


    def _parseDeclarationProperty(self, src, propertyName):
        # expr
        src, expr = self._parseExpression(src)

        # prio?
        important, src = self._getMatchResult(self.re_important, src)
        src = src.lstrip()

        property = self.cssBuilder.property(propertyName, expr, important)
        return src, property


    def _parseExpression(self, src, returnList=False):
        """
        expr
        : term [ operator term ]*
        ;
        """
        src, term = self._parseExpressionTerm(src)
        operator = None
        while src[:1] not in ('', ';', '{', '}', '[', ']', ')'):
            for operator in self.ExpressionOperators:
                if src.startswith(operator):
                    src = src[len(operator):]
                    break
            else:
                operator = ' '
            src, term2 = self._parseExpressionTerm(src.lstrip())
            if term2 is NotImplemented:
                break
            else:
                term = self.cssBuilder.combineTerms(term, operator, term2)

        if operator is None and returnList:
            term = self.cssBuilder.combineTerms(term, None, None)
            return src, term
        else:
            return src, term


    def _parseExpressionTerm(self, src):
        """term
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
            src, params = self._parseExpression(src, True)
            if src[0] != ')':
                raise self.ParseError('Terminal function expression expected closing \')\'', src, ctxsrc)
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

        result, src = self._getMatchResult(self.re_unicodeid, src)
        if result is not None:
            term = self.cssBuilder.termIdent(result)
            return src.lstrip(), term

        result, src = self._getMatchResult(self.re_unicodestr, src)
        if result is not None:
            term = self.cssBuilder.termString(result)
            return src.lstrip(), term

        return self.cssBuilder.termUnknown(src)


    #~ utility methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _getIdent(self, src, default=None):
        return self._getMatchResult(self.re_ident, src, default)


    def _getString(self, src, rexpression=None, default=None):
        if rexpression is None:
            rexpression = self.re_string
        result = rexpression.match(src)
        if result:
            strres = filter(None, result.groups())
            if strres:
                try:
                    strres = strres[0]
                except Exception:
                    strres = result.groups()[0]
            else:
                strres = ''
            return strres, src[result.end():]
        else:
            return default, src


    def _getStringOrURI(self, src):
        result, src = self._getString(src, self.re_uri)
        if result is None:
            result, src = self._getString(src)
        return result, src


    def _getMatchResult(self, rexpression, src, default=None, group=1):
        result = rexpression.match(src)
        if result:
            return result.group(group), src[result.end():]
        else:
            return default, src

