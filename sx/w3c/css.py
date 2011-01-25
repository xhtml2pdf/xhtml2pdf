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

"""CSS-2.1 engine

Primary classes:
    * CSSElementInterfaceAbstract
        Provide a concrete implementation for the XML element model used.

    * CSSCascadeStrategy
        Implements the CSS-2.1 engine's attribute lookup rules.

    * CSSParser
        Parses CSS source forms into usable results using CSSBuilder and
        CSSMutableSelector.  You may want to override parseExternal()

    * CSSBuilder (and CSSMutableSelector)
        A concrete implementation for cssParser.CSSBuilderAbstract (and
        cssParser.CSSSelectorAbstract) to provide usable results to
        CSSParser requests.

Dependencies:
    python 2.3 (or greater)
    sets, cssParser, re (via cssParser)
"""

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ Imports
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

import copy
import sets
import cssParser
import cssSpecial

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ Constants / Variables / Etc.
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CSSParseError = cssParser.CSSParseError

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ Definitions
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSElementInterfaceAbstract(object):
    def getAttr(self, name, default=NotImplemented):
        raise NotImplementedError('Subclass responsibility')
    def getIdAttr(self):
        return self.getAttr('id', '')
    def getClassAttr(self):
        return self.getAttr('class', '')

    def getInlineStyle(self):
        raise NotImplementedError('Subclass responsibility')

    def matchesNode(self):
        raise NotImplementedError('Subclass responsibility')

    def inPseudoState(self, name, params=()):
        raise NotImplementedError('Subclass responsibility')

    def iterXMLParents(self):
        """Results must be compatible with CSSElementInterfaceAbstract"""
        raise NotImplementedError('Subclass responsibility')

    def getPreviousSibling(self):
        raise NotImplementedError('Subclass responsibility')

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSCascadeStrategy(object):
    author = None
    user = None
    userAgenr = None

    def __init__(self, author=None, user=None, userAgent=None):
        if author is not None:
            self.author = author
        if user is not None:
            self.user = user
        if userAgent is not None:
            self.userAgenr = userAgent

    def copyWithUpdate(self, author=None, user=None, userAgent=None):
        if author is None:
            author = self.author
        if user is None:
            user = self.user
        if userAgent is None:
            userAgent = self.userAgenr
        return self.__class__(author, user, userAgent)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def iterCSSRulesets(self, inline=None):
        if self.userAgenr is not None:
            yield self.userAgenr[0]
            yield self.userAgenr[1]

        if self.user is not None:
            yield self.user[0]

        if self.author is not None:
            yield self.author[0]
            yield self.author[1]

        if inline:
            yield inline[0]
            yield inline[1]

        if self.user is not None:
            yield self.user[1]

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def findStyleFor(self, element, attrName, default=NotImplemented):
        """Attempts to find the style setting for attrName in the CSSRulesets.

        Note: This method does not attempt to resolve rules that return
        "inherited", "default", or values that have units (including "%").
        This is left up to the client app to re-query the CSS in order to
        implement these semantics.
        """
        rule = self.findCSSRulesFor(element, attrName)
        return self._extractStyleForRule(rule, attrName, default)

    def findStylesForEach(self, element, attrNames, default=NotImplemented):
        """Attempts to find the style setting for attrName in the CSSRulesets.

        Note: This method does not attempt to resolve rules that return
        "inherited", "default", or values that have units (including "%").
        This is left up to the client app to re-query the CSS in order to
        implement these semantics.
        """
        rules = self.findCSSRulesForEach(element, attrNames)
        return [(attrName, self._extractStyleForRule(rule, attrName, default))
                for attrName, rule in rules.iteritems()]

    def findCSSRulesFor(self, element, attrName):
        rules = []

        inline = element.getInlineStyle()
        for ruleset in self.iterCSSRulesets(inline):
            rules += ruleset.findCSSRuleFor(element, attrName)

        rules.sort()
        return rules

    def findCSSRulesForEach(self, element, attrNames):
        rules = dict([(name, []) for name in attrNames])

        inline = element.getInlineStyle()
        for ruleset in self.iterCSSRulesets(inline):
            for attrName, attrRules in rules.iteritems():
                attrRules += ruleset.findCSSRuleFor(element, attrName)

        for attrRules in rules.itervalues():
            attrRules.sort()
        return rules

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _extractStyleForRule(self, rule, attrName, default=NotImplemented):
        if rule:
            # rule is packed in a list to differentiate from "no rule" vs "rule
            # whose value evalutates as False"
            style = rule[-1][1]
            return style[attrName]
        elif default is not NotImplemented:
            return default
        else:
            raise LookupError("Could not find style for '%s' in %r" % (attrName, rule))

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ CSS Selectors
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSSelectorBase(object):
    inline = False
    _hash = None
    _specificity = None

    def __init__(self, completeName='*'):
        if not isinstance(completeName, tuple):
            completeName = (None, '*', completeName)
        self.completeName = completeName

    def _updateHash(self):
        self._hash = hash((self.fullName, self.specificity(), self.qualifiers))
    def __hash__(self):
        if self._hash is None:
            return object.__hash__(self)
        else:
            return self._hash

    def getNSPrefix(self):
        return self.completeName[0]
    nsPrefix = property(getNSPrefix)

    def getName(self):
        return self.completeName[2]
    name = property(getName)

    def getNamespace(self):
        return self.completeName[1]
    namespace = property(getNamespace)

    def getFullName(self):
        return self.completeName[1:3]
    fullName = property(getFullName)

    def __repr__(self):
        strArgs = (self.__class__.__name__,)+self.specificity()+(self.asString(),)
        return '<%s %d:%d:%d:%d %s >' % strArgs

    def __str__(self):
        return self.asString()

    def __cmp__(self, other):
        result = cmp(self.specificity(), other.specificity())
        if result != 0:
            return result
        result = cmp(self.fullName, other.fullName)
        if result != 0:
            return result
        result = cmp(self.qualifiers, other.qualifiers)
        return result

    def specificity(self):
        if self._specificity is None:
            self._specificity = self._calcSpecificity()
        return self._specificity

    def _calcSpecificity(self):
        """from http://www.w3.org/TR/CSS21/cascade.html#specificity"""
        hashCount = 0
        qualifierCount = 0
        elementCount = int(self.name != '*')
        for q in self.qualifiers:
            if q.isHash(): hashCount += 1
            elif q.isClass(): qualifierCount += 1
            elif q.isAttr(): qualifierCount += 1
            elif q.isPseudo(): elementCount += 1
            elif q.isCombiner():
                i,h,q,e = q.selector.specificity()
                hashCount += h
                qualifierCount += q
                elementCount += e
        return self.inline, hashCount, qualifierCount, elementCount

    def matches(self, element=None):
        if element is None:
            return False

        if not element.matchesNode(self.fullName):
            return False

        for qualifier in self.qualifiers:
            if not qualifier.matches(element):
                return False
        else:
            return True

    def asString(self):
        result = []
        if self.nsPrefix is not None:
            result.append('%s|%s' % (self.nsPrefix, self.name))
        else: result.append(self.name)

        for q in self.qualifiers:
            if q.isCombiner():
                result.insert(0, q.asString())
            else:
                result.append(q.asString())
        return ''.join(result)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSInlineSelector(CSSSelectorBase):
    inline = True

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSMutableSelector(CSSSelectorBase, cssParser.CSSSelectorAbstract):
    qualifiers = []

    def asImmutable(self):
        return CSSImmutableSelector(self.completeName, [q.asImmutable() for q in self.qualifiers])

    def combineSelectors(klass, selectorA, op, selectorB):
        selectorB.addCombination(op, selectorA)
        return selectorB
    combineSelectors = classmethod(combineSelectors)

    def addCombination(self, op, other):
        self._addQualifier(CSSSelectorCombinationQualifier(op, other))
    def addHashId(self, hashId):
        self._addQualifier(CSSSelectorHashQualifier(hashId))
    def addClass(self, class_):
        self._addQualifier(CSSSelectorClassQualifier(class_))
    def addAttribute(self, attrName):
        self._addQualifier(CSSSelectorAttributeQualifier(attrName))
    def addAttributeOperation(self, attrName, op, attrValue):
        self._addQualifier(CSSSelectorAttributeQualifier(attrName, op, attrValue))
    def addPseudo(self, name):
        self._addQualifier(CSSSelectorPseudoQualifier(name))
    def addPseudoFunction(self, name, params):
        self._addQualifier(CSSSelectorPseudoQualifier(name, params))

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _addQualifier(self, qualifier):
        if self.qualifiers:
            self.qualifiers.append(qualifier)
        else:
            self.qualifiers = [qualifier]

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSImmutableSelector(CSSSelectorBase):
    def __init__(self, completeName='*', qualifiers=()):
        # print completeName, qualifiers
        self.qualifiers = tuple(qualifiers)
        CSSSelectorBase.__init__(self, completeName)
        self._updateHash()

    def fromSelector(klass, selector):
        return klass(selector.completeName, selector.qualifiers)
    fromSelector = classmethod(fromSelector)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ CSS Selector Qualifiers -- see CSSImmutableSelector
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSSelectorQualifierBase(object):
    def isHash(self):
        return False
    def isClass(self):
        return False
    def isAttr(self):
        return False
    def isPseudo(self):
        return False
    def isCombiner(self):
        return False
    def asImmutable(self):
        return self
    def __str__(self):
        return self.asString()

class CSSSelectorHashQualifier(CSSSelectorQualifierBase):
    def __init__(self, hashId):
        self.hashId = hashId
    def isHash(self):
        return True
    def __hash__(self):
        return hash((self.hashId,))
    def asString(self):
        return '#'+self.hashId
    def matches(self, element):
        return element.getIdAttr() == self.hashId

class CSSSelectorClassQualifier(CSSSelectorQualifierBase):
    def __init__(self, classId):
        self.classId = classId
    def isClass(self):
        return True
    def __hash__(self):
        return hash((self.classId,))
    def asString(self):
        return '.'+self.classId
    def matches(self, element):
        return self.classId in element.getClassAttr().split()

class CSSSelectorAttributeQualifier(CSSSelectorQualifierBase):
    name, op, value = None, None, NotImplemented

    def __init__(self, attrName, op=None, attrValue=NotImplemented):
        self.name = attrName
        if op is not self.op:
            self.op = op
        if attrValue is not self.value:
            self.value = attrValue
    def isAttr(self):
        return True
    def __hash__(self):
        return hash((self.name, self.op, self.value))
    def asString(self):
        if self.value is NotImplemented:
            return '[%s]' % (self.name,)
        else: return '[%s%s%s]' % (self.name, self.op, self.value)
    def matches(self, element):
        op = self.op
        if op is None:
            return element.getAttr(self.name, NotImplemented) != NotImplemented
        elif op == '=':
            return self.value == element.getAttr(self.name, NotImplemented)
        elif op == '~=':
            return self.value in element.getAttr(self.name, '').split()
        elif op == '|=':
            return self.value in element.getAttr(self.name, '').split('-')
        else:
            raise RuntimeError("Unknown operator %r for %r" % (self.op, self))

class CSSSelectorPseudoQualifier(CSSSelectorQualifierBase):
    def __init__(self, attrName, params=()):
        self.name = attrName
        self.params = tuple(params)
    def isPseudo(self):
        return True
    def __hash__(self):
        return hash((self.name, self.params))
    def asString(self):
        if self.params:
            return ':'+self.name
        else:
            return ':%s(%s)' % (self.name, self.params)
    def matches(self, element):
        return element.inPseudoState(self.name, self.params)

class CSSSelectorCombinationQualifier(CSSSelectorQualifierBase):
    def __init__(self, op, selector):
        self.op = op
        self.selector = selector
    def isCombiner(self):
        return True
    def __hash__(self):
        return hash((self.op, self.selector))
    def asImmutable(self):
        return self.__class__(self.op, self.selector.asImmutable())
    def asString(self):
        return '%s%s' % (self.selector.asString(), self.op)
    def matches(self, element):
        op, selector = self.op, self.selector
        if op == ' ':
            for parent in element.iterXMLParents():
                if selector.matches(parent):
                    return True
            else:
                return False
        elif op == '>':
            for parent in element.iterXMLParents():
                if selector.matches(parent):
                    return True
                else:
                    return False
        elif op == '+':
            return selector.matches(element.getPreviousSibling())

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ CSS Misc
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSTerminalFunction(object):
    def __init__(self, name, params):
        self.name = name
        self.params = params

    def __repr__(self):
        return '<CSS function: %s(%s)>' % (self.name, ', '.join(self.params))

class CSSTerminalOperator(tuple):
    def __new__(klass, *args):
        return tuple.__new__(klass, args)

    def __repr__(self):
        return 'op' + tuple.__repr__(self)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ CSS Objects
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSDeclarations(dict):
    pass

class CSSRuleset(dict):
    def findCSSRulesFor(self, element, attrName):
        ruleResults = []
        append = ruleResults.append
        for nodeFilter, declarations in self.iteritems():
            if (attrName in declarations) and (nodeFilter.matches(element)):
                append((nodeFilter, declarations))
        ruleResults.sort()
        return ruleResults

    def findCSSRuleFor(self, *args, **kw):
        # rule is packed in a list to differentiate from "no rule" vs "rule
        # whose value evalutates as False"
        return self.findCSSRulesFor(*args, **kw)[-1:]

    def mergeStyles(self, styles):
        " XXX Bugfix for use in PISA "
        for k, v in styles.items():
            if self.has_key(k) and self[k]:
                self[k] = copy.copy(self[k])
                self[k].update(v)
            else:
                self[k] = v

class CSSInlineRuleset(CSSRuleset, CSSDeclarations):
    def findCSSRulesFor(self, element, attrName):
        if attrName in self:
            return [(CSSInlineSelector(), self)]
        else:
            return []
    def findCSSRuleFor(self, *args, **kw):
        # rule is packed in a list to differentiate from "no rule" vs "rule
        # whose value evalutates as False"
        return self.findCSSRulesFor(*args, **kw)[-1:]

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ CSS Builder
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSBuilder(cssParser.CSSBuilderAbstract):
    RulesetFactory = CSSRuleset
    SelectorFactory = CSSMutableSelector
    MediumSetFactory = sets.Set
    DeclarationsFactory = CSSDeclarations
    TermFunctionFactory = CSSTerminalFunction
    TermOperatorFactory = CSSTerminalOperator
    xmlnsSynonyms = {}
    mediumSet = None
    trackImportance = True
    charset = None

    def __init__(self, mediumSet=mediumSet, trackImportance=trackImportance):
        self.setMediumSet(mediumSet)
        self.setTrackImportance(trackImportance)

    def isValidMedium(self, mediums):
        if not mediums:
            return False
        if 'all' in mediums:
            return True

        mediums = self.MediumSetFactory(mediums)
        return bool(self.getMediumSet().intersection(mediums))

    def getMediumSet(self):
        return self.mediumSet
    def setMediumSet(self, mediumSet):
        self.mediumSet = self.MediumSetFactory(mediumSet)
    def updateMediumSet(self, mediumSet):
        self.getMediumSet().update(mediumSet)

    def getTrackImportance(self):
        return self.trackImportance
    def setTrackImportance(self, trackImportance=True):
        self.trackImportance = trackImportance

    #~ helpers ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _pushState(self):
        _restoreState = self.__dict__
        self.__dict__ = self.__dict__.copy()
        self._restoreState = _restoreState
        self.namespaces = {}
    def _popState(self):
        self.__dict__ = self._restoreState

    def _declarations(self, declarations, DeclarationsFactory=None):
        DeclarationsFactory = DeclarationsFactory or self.DeclarationsFactory
        if self.trackImportance:
            normal, important = [], []
            for d in declarations:
                if d[-1]:
                    important.append(d[:-1])
                else: normal.append(d[:-1])
            return DeclarationsFactory(normal), DeclarationsFactory(important)
        else:
            return DeclarationsFactory(declarations)

    def _xmlnsGetSynonym(self, uri):
        # Don't forget to substitute our namespace synonyms!
        return self.xmlnsSynonyms.get(uri or None, uri) or None

    #~ css results ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def beginStylesheet(self):
        self._pushState()
    def endStylesheet(self):
        self._popState()
    def stylesheet(self, stylesheetElements, stylesheetImports):
        # XXX Updated for PISA
        if self.trackImportance:
            normal, important = self.RulesetFactory(), self.RulesetFactory()
            for normalStylesheet, importantStylesheet in stylesheetImports:
                normal.mergeStyles(normalStylesheet)
                important.mergeStyles(importantStylesheet)
            for normalStyleElement, importantStyleElement in stylesheetElements:
                normal.mergeStyles(normalStyleElement)
                important.mergeStyles(importantStyleElement)
            return normal, important
        else:
            result = self.RulesetFactory()
            for stylesheet in stylesheetImports:
                result.mergeStyles(stylesheet)

            for styleElement in stylesheetElements:
                result.mergeStyles(styleElement)
            return result

    def beginInline(self):
        self._pushState()
    def endInline(self):
        self._popState()

    def specialRules(self, declarations):
        return cssSpecial.parseSpecialRules(declarations)

    def inline(self, declarations):
        declarations = self.specialRules(declarations)
        return self._declarations(declarations, CSSInlineRuleset)

    def ruleset(self, selectors, declarations):

        # XXX Modified for pisa!
        declarations = self.specialRules(declarations)
        # XXX Modified for pisa!

        if self.trackImportance:
            normalDecl, importantDecl = self._declarations(declarations)
            normal, important = self.RulesetFactory(), self.RulesetFactory()
            for s in selectors:
                s = s.asImmutable()
                if normalDecl:
                    normal[s] = normalDecl
                if importantDecl:
                    important[s] = importantDecl
            return normal, important
        else:
            declarations = self._declarations(declarations)
            result = [(s.asImmutable(), declarations) for s in selectors]
            return self.RulesetFactory(result)

    #~ css namespaces ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def resolveNamespacePrefix(self, nsPrefix, name):
        if nsPrefix == '*':
            return (nsPrefix, '*', name)
        xmlns = self.namespaces.get(nsPrefix, None)
        xmlns = self._xmlnsGetSynonym(xmlns)
        return (nsPrefix, xmlns, name)

    #~ css @ directives ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def atCharset(self, charset):
        self.charset = charset

    def atImport(self, import_, mediums, cssParser):
        if self.isValidMedium(mediums):
            return cssParser.parseExternal(import_)
        return None

    def atNamespace(self, nsprefix, uri):
        self.namespaces[nsprefix] = uri

    def atMedia(self, mediums, ruleset):
        if self.isValidMedium(mediums):
            return ruleset
        return None

    def atPage(self, page, pseudopage, declarations):
        return self.ruleset([self.selector('*')], declarations)

    def atFontFace(self, declarations):
        return self.ruleset([self.selector('*')], declarations)

    def atIdent(self, atIdent, cssParser, src):
        return src, NotImplemented

    #~ css selectors ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def selector(self, name):
        return self.SelectorFactory(name)

    def combineSelectors(self, selectorA, op, selectorB):
        return self.SelectorFactory.combineSelectors(selectorA, op, selectorB)

    #~ css declarations ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def property(self, name, value, important=False):
        if self.trackImportance:
            return (name, value, important)
        else:
            return (name, value)

    def combineTerms(self, termA, op, termB):
        if op in (',', ' '):
            if isinstance(termA, list):
                termA.append(termB)
                return termA
            else:
                return [termA, termB]
        elif op is None and termB is None:
            return [termA]
        else:
            if isinstance(termA, list):
                # Bind these "closer" than the list operators -- i.e. work on
                # the (recursively) last element of the list
                termA[-1] = self.combineTerms(termA[-1], op, termB)
                return termA
            else:
                return self.TermOperatorFactory(termA, op, termB)

    def termIdent(self, value):
        return value

    def termNumber(self, value, units=None):
        if units:
            return value, units
        else:
            return value

    def termRGB(self, value):
        return value

    def termURI(self, value):
        return value

    def termString(self, value):
        return value

    def termUnicodeRange(self, value):
        return value

    def termFunction(self, name, value):
        return self.TermFunctionFactory(name, value)

    def termUnknown(self, src):
        return src, NotImplemented

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~ CSS Parser -- finally!
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CSSParser(cssParser.CSSParser):
    CSSBuilderFactory = CSSBuilder

    def __init__(self, cssBuilder=None, create=True, **kw):
        if not cssBuilder and create:
            assert cssBuilder is None
            cssBuilder = self.createCSSBuilder(**kw)
        cssParser.CSSParser.__init__(self, cssBuilder)

    def createCSSBuilder(self, **kw):
        return self.CSSBuilderFactory(**kw)

    def parseExternal(self, cssResourceName):
        if os.path.isfile(cssResourceName):
            cssFile = file(cssResourceName, 'r')
            return self.parseFile(cssFile, True)
        else:
            raise RuntimeError("Cannot resolve external CSS file: \"%s\"" % cssResourceName)

