# -*- coding: utf-8 -*-
import copy
import logging
import os
import re

import reportlab
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus.frames import Frame, ShowBoundaryValue
from reportlab.platypus.paraparser import ParaFrag, ps2tt, tt2ps
import six

import xhtml2pdf.default
import xhtml2pdf.parser
from xhtml2pdf.util import getSize, getCoords, getFile, pisaFileObject, \
    getFrameDimensions, getColor, set_value, copy_attrs
from xhtml2pdf.w3c import css
from xhtml2pdf.xhtml2pdf_reportlab import PmlPageTemplate, PmlTableOfContents, \
    PmlParagraph, PmlParagraphAndImage, PmlPageCount


TupleType = tuple
ListType = list
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

# Copyright 2010 Dirk Holtwick, holtwick.it
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

reportlab.rl_config.warnOnMissingFontGlyphs = 0

log = logging.getLogger("xhtml2pdf")

sizeDelta = 2       # amount to reduce font size by for super and sub script
subFraction = 0.4   # fraction of font size that a sub script should be lowered
superFraction = 0.4

NBSP = u"\u00a0"


def clone(self, **kwargs):
    n = ParaFrag(**self.__dict__)
    if kwargs:
        d = n.__dict__
        d.update(kwargs)
        # This else could cause trouble in Paragraphs with images etc.
        if "cbDefn" in d:
            del d["cbDefn"]
    n.bulletText = None
    return n


ParaFrag.clone = clone


def getParaFrag(style):
    frag = ParaFrag()

    set_value(frag,
              ('sub', 'super', 'rise', 'underline', 'strike', 'greek',
               'leading', 'leadingSpace', 'spaceBefore',
               'spaceAfter', 'leftIndent', 'rightIndent', 'firstLineIndent',
               'borderPadding', 'paddingLeft', 'paddingRight',
               'paddingTop', 'paddingBottom', 'bulletIndent',
               'insideStaticFrame', 'outlineLevel'
               ),
              0)

    set_value(frag,
              ('backColor', 'vAlign', 'link', 'borderStyle',
               'borderColor', 'listStyleType', 'listStyleImage',
               'wordWrap', 'height', 'width', 'bulletText'
               ),
              None
              )
    set_value(frag,
              ('pageNumber', 'pageCount', 'outline',
               'outlineOpen', 'keepWithNext'),
              False)

    frag.text = ""
    frag.fontName = "Times-Roman"
    frag.fontName, frag.bold, frag.italic = ps2tt(style.fontName)
    frag.fontSize = style.fontSize
    frag.textColor = style.textColor

    # Extras
    frag.letterSpacing = "normal"
    frag.leadingSource = "150%"
    frag.alignment = TA_LEFT
    frag.borderWidth = 1

    frag.borderLeftWidth = frag.borderWidth
    frag.borderLeftColor = frag.borderColor
    frag.borderLeftStyle = frag.borderStyle
    frag.borderRightWidth = frag.borderWidth
    frag.borderRightColor = frag.borderColor
    frag.borderRightStyle = frag.borderStyle
    frag.borderTopWidth = frag.borderWidth
    frag.borderTopColor = frag.borderColor
    frag.borderTopStyle = frag.borderStyle
    frag.borderBottomWidth = frag.borderWidth
    frag.borderBottomColor = frag.borderColor
    frag.borderBottomStyle = frag.borderStyle

    frag.whiteSpace = "normal"
    frag.bulletFontName = "Helvetica"
    frag.zoom = 1.0

    return frag


def getDirName(path):
    parts = urlparse.urlparse(path)
    if parts.scheme:
        return path
    else:
        return os.path.dirname(os.path.abspath(path))


class pisaCSSBuilder(css.CSSBuilder):

    def atFontFace(self, declarations):
        """
        Embed fonts
        """
        result = self.ruleset([self.selector('*')], declarations)
        data = list(result[0].values())[0]
        if "src" not in data:
            # invalid - source is required, ignore this specification
            return {}, {}
        names = data["font-family"]

        # Font weight
        fweight = str(data.get("font-weight", "normal")).lower()
        bold = fweight in ("bold", "bolder", "500", "600", "700", "800", "900")
        if not bold and fweight != "normal":
            log.warn(
                self.c.warning("@fontface, unknown value font-weight '%s'", fweight))

        # Font style
        italic = str(
            data.get("font-style", "")).lower() in ("italic", "oblique")

        # The "src" attribute can be a CSS group but in that case
        # ignore everything except the font URI
        uri = data['src']
        if not isinstance(data['src'], str):
            for part in uri:
                if isinstance(part, str):
                    uri = part
                    break

        src = self.c.getFile(uri, relative=self.c.cssParser.rootPath)
        self.c.loadFont(
            names,
            src,
            bold=bold,
            italic=italic)
        return {}, {}

    def _pisaAddFrame(self, name, data, first=False, border=None, size=(0, 0)):
        c = self.c
        if not name:
            name = "-pdf-frame-%d" % c.UID()
        if data.get('is_landscape', False):
            size = (size[1], size[0])
        x, y, w, h = getFrameDimensions(data, size[0], size[1])
        # print name, x, y, w, h
        # if not (w and h):
        #    return None
        if first:
            return name, None, data.get("-pdf-frame-border", border), x, y, w, h, data

        return (name, data.get("-pdf-frame-content", None),
                data.get("-pdf-frame-border", border), x, y, w, h, data)

    def _getFromData(self, data, attr, default=None, func=None):
        if not func:
            func = lambda x: x

        if type(attr) in (list, tuple):
            for a in attr:
                if a in data:
                    return func(data[a])
                return default
        else:
            if attr in data:
                return func(data[attr])
            return default

    def atPage(self, name, pseudopage, declarations):
        c = self.c
        data = {}
        name = name or "body"
        pageBorder = None

        if declarations:
            result = self.ruleset([self.selector('*')], declarations)

            if declarations:
                try:
                    data = result[0].values()[0]
                except Exception:
                    data = result[0].popitem()[1]
                pageBorder = data.get("-pdf-frame-border", None)

        if name in c.templateList:
            log.warn(
                self.c.warning("template '%s' has already been defined", name))

        if "-pdf-page-size" in data:
            c.pageSize = xhtml2pdf.default.PML_PAGESIZES.get(
                str(data["-pdf-page-size"]).lower(), c.pageSize)

        isLandscape = False
        if "size" in data:
            size = data["size"]
            if type(size) is not ListType:
                size = [size]
            sizeList = []
            for value in size:
                valueStr = str(value).lower()
                if type(value) is TupleType:
                    sizeList.append(getSize(value))
                elif valueStr == "landscape":
                    isLandscape = True
                elif valueStr == "portrait":
                    isLandscape = False
                elif valueStr in xhtml2pdf.default.PML_PAGESIZES:
                    c.pageSize = xhtml2pdf.default.PML_PAGESIZES[valueStr]
                else:
                    raise RuntimeError("Unknown size value for @page")

            if len(sizeList) == 2:
                c.pageSize = tuple(sizeList)
            if isLandscape:
                c.pageSize = landscape(c.pageSize)

        padding_top = self._getFromData(data, 'padding-top', 0, getSize)
        padding_left = self._getFromData(data, 'padding-left', 0, getSize)
        padding_right = self._getFromData(data, 'padding-right', 0, getSize)
        padding_bottom = self._getFromData(data, 'padding-bottom', 0, getSize)
        border_color = self._getFromData(data, ('border-top-color', 'border-bottom-color',
                                                'border-left-color', 'border-right-color'), None, getColor)
        border_width = self._getFromData(data, ('border-top-width', 'border-bottom-width',
                                                'border-left-width', 'border-right-width'), 0, getSize)

        for prop in ("margin-top", "margin-left", "margin-right", "margin-bottom",
                     "top", "left", "right", "bottom", "width", "height"):
            if prop in data:
                c.frameList.append(
                    self._pisaAddFrame(name, data, first=True, border=pageBorder, size=c.pageSize))
                break

        # Frames have to be calculated after we know the pagesize
        frameList = []
        staticList = []
        for fname, static, border, x, y, w, h, fdata in c.frameList:
            fpadding_top = self._getFromData(
                fdata, 'padding-top', padding_top, getSize)
            fpadding_left = self._getFromData(
                fdata, 'padding-left', padding_left, getSize)
            fpadding_right = self._getFromData(
                fdata, 'padding-right', padding_right, getSize)
            fpadding_bottom = self._getFromData(
                fdata, 'padding-bottom', padding_bottom, getSize)
            fborder_color = self._getFromData(fdata, ('border-top-color', 'border-bottom-color',
                                                      'border-left-color', 'border-right-color'), border_color, getColor)
            fborder_width = self._getFromData(fdata, ('border-top-width', 'border-bottom-width',
                                                      'border-left-width', 'border-right-width'), border_width, getSize)

            if border or pageBorder:
                frame_border = ShowBoundaryValue()
            else:
                frame_border = ShowBoundaryValue(
                    color=fborder_color, width=fborder_width)

            # fix frame sizing problem.
            if static:
                x, y, w, h = getFrameDimensions(
                    fdata, c.pageSize[0], c.pageSize[1])
            x, y, w, h = getCoords(x, y, w, h, c.pageSize)
            if w <= 0 or h <= 0:
                log.warn(
                    self.c.warning("Negative width or height of frame. Check @frame definitions."))

            frame = Frame(
                x, y, w, h,
                id=fname,
                leftPadding=fpadding_left,
                rightPadding=fpadding_right,
                bottomPadding=fpadding_bottom,
                topPadding=fpadding_top,
                showBoundary=frame_border)

            if static:
                frame.pisaStaticStory = []
                c.frameStatic[static] = [frame] + c.frameStatic.get(static, [])
                staticList.append(frame)
            else:
                frameList.append(frame)

        background = data.get("background-image", None)
        if background:
            # should be relative to the css file
            background = self.c.getFile(
                background, relative=self.c.cssParser.rootPath)

        if not frameList:
            log.warn(
                c.warning("missing explicit frame definition for content or just static frames"))
            fname, static, border, x, y, w, h, data = self._pisaAddFrame(name, data, first=True, border=pageBorder,
                                                                         size=c.pageSize)
            x, y, w, h = getCoords(x, y, w, h, c.pageSize)
            if w <= 0 or h <= 0:
                log.warn(
                    c.warning("Negative width or height of frame. Check @page definitions."))

            if border or pageBorder:
                frame_border = ShowBoundaryValue()
            else:
                frame_border = ShowBoundaryValue(
                    color=border_color, width=border_width)

            frameList.append(Frame(
                x, y, w, h,
                id=fname,
                leftPadding=padding_left,
                rightPadding=padding_right,
                bottomPadding=padding_bottom,
                topPadding=padding_top,
                showBoundary=frame_border))

        pt = PmlPageTemplate(
            id=name,
            frames=frameList,
            pagesize=c.pageSize,
        )
        pt.pisaStaticList = staticList
        pt.pisaBackground = background
        pt.pisaBackgroundList = c.pisaBackgroundList

        if isLandscape:
            pt.pageorientation = pt.LANDSCAPE

        c.templateList[name] = pt
        c.template = None
        c.frameList = []
        c.frameStaticList = []

        return {}, {}

    def atFrame(self, name, declarations):
        if declarations:
            result = self.ruleset([self.selector('*')], declarations)
            # print "@BOX", name, declarations, result

            data = result[0]
            if data:
                try:
                    data = data.values()[0]
                except Exception:
                    data = data.popitem()[1]
                self.c.frameList.append(
                    self._pisaAddFrame(name, data, size=self.c.pageSize))

        return {}, {}  # TODO: It always returns empty dicts?


class pisaCSSParser(css.CSSParser):

    def parseExternal(self, cssResourceName):
        result=None
        oldRootPath = self.rootPath
        cssFile = self.c.getFile(cssResourceName, relative=self.rootPath)
        if not cssFile:
            return None
        if self.rootPath and urlparse.urlparse(self.rootPath).scheme:
            self.rootPath = urlparse.urljoin(self.rootPath, cssResourceName)
        else:
            self.rootPath = getDirName(cssFile.uri)
        try:
            result = self.parse(cssFile.getData())
            self.rootPath = oldRootPath
        except Exception as e:
            print(e)
        return result


class pisaContext(object):
    """
    Helper class for creation of reportlab story and container for
    various data.
    """

    def __init__(self, path, debug=0, capacity=-1):
        self.fontList = copy.copy(xhtml2pdf.default.DEFAULT_FONT)
        set_value(self,
                  ('path', 'story', 'text', 'log', 'frameStaticList',
                   'pisaBackgroundList', 'frameList', 'anchorFrag',
                   'anchorName', 'fragList', 'fragAnchor', 'fragStack'
                   ), [],  _copy=True)

        set_value(self, ('node', 'indexing_story',
                         'template', 'keepInFrameIndex',
                         'tableData', 'image'),
                  None)
        set_value(self, ('err', 'warn', 'uidctr', 'listCounter'), 0)
        set_value(self, ('text', 'cssText', 'cssDefaultText'), "")
        set_value(self, ('templateList', 'frameStatic', 'imageData'),
                  {}, _copy=True)

        self.capacity = capacity
        self.toc = PmlTableOfContents()
        self.multiBuild = False
        self.pageSize = A4
        self.baseFontSize = getSize("12pt")
        self.frag = self.fragBlock = getParaFrag(
            ParagraphStyle('default%d' % self.UID()))
        self.fragStrip = True
        self.force = False

        # External callback function for path calculations
        self.pathCallback = None

        # Store path to document
        self.pathDocument = path or "__dummy__"
        parts = urlparse.urlparse(self.pathDocument)
        if not parts.scheme:
            self.pathDocument = os.path.abspath(self.pathDocument)
        self.pathDirectory = getDirName(self.pathDocument)

        self.meta = dict(
            author="",
            title="",
            subject="",
            keywords="",
            pagesize=A4,
        )

    def UID(self):
        self.uidctr += 1
        return self.uidctr

    # METHODS FOR CSS
    def addCSS(self, value):
        value = value.strip()
        if value.startswith("<![CDATA["):
            value = value[9: - 3]
        if value.startswith("<!--"):
            value = value[4: - 3]
        self.cssText += value.strip() + "\n"

    # METHODS FOR CSS
    def addDefaultCSS(self, value):
        value = value.strip()
        if value.startswith("<![CDATA["):
            value = value[9: - 3]
        if value.startswith("<!--"):
            value = value[4: - 3]
        self.cssDefaultText += value.strip() + "\n"

    def parseCSS(self):
        # This self-reference really should be refactored. But for now
        # we'll settle for using weak references. This avoids memory
        # leaks because the garbage collector (at least on cPython
        # 2.7.3) isn't aggressive enough.
        import weakref

        self.cssBuilder = pisaCSSBuilder(mediumSet=["all", "print", "pdf"])
        #self.cssBuilder.c = self
        self.cssBuilder._c = weakref.ref(self)
        pisaCSSBuilder.c = property(lambda self: self._c())

        self.cssParser = pisaCSSParser(self.cssBuilder)
        self.cssParser.rootPath = self.pathDirectory
        #self.cssParser.c = self
        self.cssParser._c = weakref.ref(self)
        pisaCSSParser.c = property(lambda self: self._c())

        self.css = self.cssParser.parse(self.cssText)
        self.cssDefault = self.cssParser.parse(self.cssDefaultText)
        self.cssCascade = css.CSSCascadeStrategy(
            userAgent=self.cssDefault, user=self.css)
        self.cssCascade.parser = self.cssParser

    # METHODS FOR STORY
    def addStory(self, data):
        self.story.append(data)

    def swapStory(self, story=None):
        story = story if story is not None else []
        self.story, story = copy.copy(story), copy.copy(self.story)
        return story

    def toParagraphStyle(self, first):
        style = ParagraphStyle(
            'default%d' % self.UID(), keepWithNext=first.keepWithNext)

        copy_attrs(style, first,
                   ('fontName', 'fontSize', 'letterSpacing', 'backColor',
                    'spaceBefore', 'spaceAfter', 'leftIndent', 'rightIndent',
                       'firstLineIndent', 'textColor', 'alignment',
                       'bulletIndent', 'wordWrap', 'borderTopStyle',
                       'borderTopWidth', 'borderTopColor',
                       'borderBottomStyle', 'borderBottomWidth',
                       'borderBottomColor', 'borderLeftStyle',
                       'borderLeftWidth', 'borderLeftColor',
                       'borderRightStyle', 'borderRightWidth',
                       'borderRightColor', 'paddingTop', 'paddingBottom',
                       'paddingLeft', 'paddingRight', 'borderPadding'
                    )
                   )

        style.leading = max(
            first.leading + first.leadingSpace, first.fontSize * 1.25)
        style.bulletFontName = first.bulletFontName or first.fontName
        style.bulletFontSize = first.fontSize

        # Border handling for Paragraph

        # Transfer the styles for each side of the border, *not* the whole
        # border values that reportlab supports. We'll draw them ourselves in
        # PmlParagraph.

        # If no border color is given, the text color is used (XXX Tables!)
        if (style.borderTopColor is None) and style.borderTopWidth:
            style.borderTopColor = first.textColor
        if (style.borderBottomColor is None) and style.borderBottomWidth:
            style.borderBottomColor = first.textColor
        if (style.borderLeftColor is None) and style.borderLeftWidth:
            style.borderLeftColor = first.textColor
        if (style.borderRightColor is None) and style.borderRightWidth:
            style.borderRightColor = first.textColor

        style.fontName = tt2ps(first.fontName, first.bold, first.italic)

        return style

    def addTOC(self):
        styles = []
        for i in six.moves.range(20):
            self.node.attributes["class"] = "pdftoclevel%d" % i
            self.cssAttr = xhtml2pdf.parser.CSSCollect(self.node, self)
            xhtml2pdf.parser.CSS2Frag(self, {
                "margin-top": 0,
                "margin-bottom": 0,
                "margin-left": 0,
                "margin-right": 0,
            }, True)
            pstyle = self.toParagraphStyle(self.frag)
            styles.append(pstyle)

        self.toc.levelStyles = styles
        self.addStory(self.toc)
        self.indexing_story = None

    def addPageCount(self):
        if not self.multiBuild:
            self.indexing_story = PmlPageCount()
            self.multiBuild = True

    def dumpPara(self, frags, style):
        return

    def addPara(self, force=False):

        force = (force or self.force)
        self.force = False

        # Cleanup the trail
        rfragList = reversed(self.fragList)

        # Find maximum lead
        maxLeading = 0
        #fontSize = 0
        for frag in self.fragList:
            leading = getSize(
                frag.leadingSource, frag.fontSize) + frag.leadingSpace
            maxLeading = max(
                leading, frag.fontSize + frag.leadingSpace, maxLeading)
            frag.leading = leading

        if force or (self.text.strip() and self.fragList):

            # Update paragraph style by style of first fragment
            first = self.fragBlock
            style = self.toParagraphStyle(first)
            # style.leading = first.leading + first.leadingSpace
            if first.leadingSpace:
                style.leading = maxLeading
            else:
                style.leading = getSize(
                    first.leadingSource, first.fontSize) + first.leadingSpace

            bulletText = copy.copy(first.bulletText)
            first.bulletText = None

            # Add paragraph to story
            if force or len(self.fragAnchor + self.fragList) > 0:

                # We need this empty fragment to work around problems in
                # Reportlab paragraphs regarding backGround etc.
                if self.fragList:
                    self.fragList.append(self.fragList[- 1].clone(text=''))
                else:
                    blank = self.frag.clone()
                    blank.fontName = "Helvetica"
                    blank.text = ''
                    self.fragList.append(blank)

                self.dumpPara(self.fragAnchor + self.fragList, style)
                para = PmlParagraph(
                    self.text,
                    style,
                    frags=self.fragAnchor + self.fragList,
                    bulletText=bulletText)

                para.outline = first.outline
                para.outlineLevel = first.outlineLevel
                para.outlineOpen = first.outlineOpen
                para.keepWithNext = first.keepWithNext
                para.autoLeading = "max"

                if self.image:
                    para = PmlParagraphAndImage(
                        para,
                        self.image,
                        side=self.imageData.get("align", "left"))

                self.addStory(para)

            self.fragAnchor = []
            first.bulletText = None

        # Reset data

        self.image = None
        self.imageData = {}

        self.clearFrag()

    # METHODS FOR FRAG
    def clearFrag(self):
        self.fragList = []
        self.fragStrip = True
        self.text = u""

    def copyFrag(self, **kw):
        return self.frag.clone(**kw)

    def newFrag(self, **kw):
        self.frag = self.frag.clone(**kw)
        return self.frag

    def _appendFrag(self, frag):
        if frag.link and frag.link.startswith("#"):
            self.anchorFrag.append((frag, frag.link[1:]))
        self.fragList.append(frag)

    # XXX Argument frag is useless!
    def addFrag(self, text="", frag=None):

        frag = baseFrag = self.frag.clone()

        # if sub and super are both on they will cancel each other out
        if frag.sub == 1 and frag.super == 1:
            frag.sub = 0
            frag.super = 0

        # XXX Has to be replaced by CSS styles like vertical-align and
        # font-size
        if frag.sub:
            frag.rise = - frag.fontSize * subFraction
            frag.fontSize = max(frag.fontSize - sizeDelta, 3)
        elif frag.super:
            frag.rise = frag.fontSize * superFraction
            frag.fontSize = max(frag.fontSize - sizeDelta, 3)

       # bold, italic, and underline
        frag.fontName = frag.bulletFontName = tt2ps(
            frag.fontName, frag.bold, frag.italic)

        # Replace &shy; with empty and normalize NBSP
        text = (text
                .replace(u"\xad", u"")
                .replace(u"\xc2\xa0", NBSP)
                .replace(u"\xa0", NBSP))

        if frag.whiteSpace == "pre":

            # Handle by lines
            for text in re.split(r'(\r\n|\n|\r)', text):
                # This is an exceptionally expensive piece of code
                self.text += text
                if ("\n" in text) or ("\r" in text):
                    # If EOL insert a linebreak
                    frag = baseFrag.clone()
                    frag.text = ""
                    frag.lineBreak = 1
                    self._appendFrag(frag)
                else:
                    # Handle tabs in a simple way
                    text = text.replace(u"\t", 8 * u" ")
                    # Somehow for Reportlab NBSP have to be inserted
                    # as single character fragments
                    for text in re.split(r'(\ )', text):
                        frag = baseFrag.clone()
                        if text == " ":
                            text = NBSP
                        frag.text = text
                        self._appendFrag(frag)
        else:
            for text in re.split(u'(' + NBSP + u')', text):
                frag = baseFrag.clone()
                if text == NBSP:
                    self.force = True
                    frag.text = NBSP
                    self.text += text
                    self._appendFrag(frag)
                else:
                    frag.text = " ".join(("x" + text + "x").split())[1: - 1]
                    if self.fragStrip:
                        frag.text = frag.text.lstrip()
                        if frag.text:
                            self.fragStrip = False
                    self.text += frag.text
                    self._appendFrag(frag)

    def pushFrag(self):
        self.fragStack.append(self.frag)
        self.newFrag()

    def pullFrag(self):
        self.frag = self.fragStack.pop()

    # XXX
    def _getFragment(self, l=20):
        try:
            return repr(" ".join(self.node.toxml().split()[:l]))
        except:
            return ""

    def _getLineNumber(self):
        return 0

    def context(self, msg):
        return "%s\n%s" % (
            str(msg),
            self._getFragment(50))

    def warning(self, msg, *args):
        self.warn += 1
        self.log.append((xhtml2pdf.default.PML_WARNING, self._getLineNumber(), str(
            msg), self._getFragment(50)))
        try:
            return self.context(msg % args)
        except:
            return self.context(msg)

    def error(self, msg, *args):
        self.err += 1
        self.log.append((xhtml2pdf.default.PML_ERROR, self._getLineNumber(), str(
            msg), self._getFragment(50)))
        try:
            return self.context(msg % args)
        except:
            return self.context(msg)

    # UTILS
    def _getFileDeprecated(self, name, relative):
        try:
            path = relative or self.pathDirectory
            if name.startswith("data:"):
                return name
            if self.pathCallback is not None:
                nv = self.pathCallback(name, relative)
            else:
                if path is None:
                    log.warn(
                        "Could not find main directory for getting filename. Use CWD")
                    path = os.getcwd()
                nv = os.path.normpath(os.path.join(path, name))
                if not (nv and os.path.isfile(nv)):
                    nv = None
            if nv is None:
                log.warn(self.warning("File '%s' does not exist", name))
            return nv
        except:
            log.warn(
                self.warning("getFile %r %r %r", name, relative, path), exc_info=1)

    def getFile(self, name, relative=None):
        """
        Returns a file name or None
        """
        if self.pathCallback is not None:
            return getFile(self._getFileDeprecated(name, relative))
        return getFile(name, relative or self.pathDirectory)

    def getFontName(self, names, default="helvetica"):
        """
        Name of a font
        """
        # print names, self.fontList
        if type(names) is not ListType:
            if type(names) not in six.string_types:
                names = str(names)
            names = names.strip().split(",")
        for name in names:
            if type(name) not in six.string_types:
                name = str(name)
            font = self.fontList.get(name.strip().lower(), None)
            if font is not None:
                return font
        return self.fontList.get(default, None)

    def registerFont(self, fontname, alias=None):
        alias = alias if alias is not None else []
        self.fontList[str(fontname).lower()] = str(fontname)
        for a in alias:
            if type(fontname) not in six.string_types:
                fontname = str(fontname)
            self.fontList[str(a)] = fontname

    def loadFont(self, names, src, encoding="WinAnsiEncoding", bold=0, italic=0):

        # XXX Just works for local filenames!
        if names and src:

            file = src
            src = file.uri

            log.debug("Load font %r", src)

            if type(names) is ListType:
                fontAlias = names
            else:
                fontAlias = (x.lower().strip() for x in names.split(",") if x)

            # XXX Problems with unicode here
            fontAlias = [str(x) for x in fontAlias]

            fontName = fontAlias[0]
            parts = src.split(".")
            baseName, suffix = ".".join(parts[: - 1]), parts[- 1]
            suffix = suffix.lower()

            if suffix in ["ttc", "ttf"]:

                # determine full font name according to weight and style
                fullFontName = "%s_%d%d" % (fontName, bold, italic)

                # check if font has already been registered
                if fullFontName in self.fontList:
                    log.warn(
                        self.warning("Repeated font embed for %s, skip new embed ", fullFontName))
                else:

                    # Register TTF font and special name
                    filename = file.getNamedFile()
                    pdfmetrics.registerFont(TTFont(fullFontName, filename))

                    # Add or replace missing styles
                    for bold in (0, 1):
                        for italic in (0, 1):
                            if ("%s_%d%d" % (fontName, bold, italic)) not in self.fontList:
                                addMapping(
                                    fontName, bold, italic, fullFontName)

                    # Register "normal" name and the place holder for style
                    self.registerFont(fontName, fontAlias + [fullFontName])

            elif suffix in ("afm", "pfb"):

                if suffix == "afm":
                    afm = file.getNamedFile()
                    tfile = pisaFileObject(baseName + ".pfb")
                    pfb = tfile.getNamedFile()
                else:
                    pfb = file.getNamedFile()
                    tfile = pisaFileObject(baseName + ".afm")
                    afm = tfile.getNamedFile()

                # determine full font name according to weight and style
                fullFontName = "%s_%d%d" % (fontName, bold, italic)

                # check if font has already been registered
                if fullFontName in self.fontList:
                    log.warn(
                        self.warning("Repeated font embed for %s, skip new embed", fontName))
                else:

                    # Include font
                    face = pdfmetrics.EmbeddedType1Face(afm, pfb)
                    fontNameOriginal = face.name
                    pdfmetrics.registerTypeFace(face)
                    # print fontName, fontNameOriginal, fullFontName
                    justFont = pdfmetrics.Font(
                        fullFontName, fontNameOriginal, encoding)
                    pdfmetrics.registerFont(justFont)

                    # Add or replace missing styles
                    for bold in (0, 1):
                        for italic in (0, 1):
                            if ("%s_%d%d" % (fontName, bold, italic)) not in self.fontList:
                                addMapping(
                                    fontName, bold, italic, fontNameOriginal)

                    # Register "normal" name and the place holder for style
                    self.registerFont(
                        fontName, fontAlias + [fullFontName, fontNameOriginal])
            else:
                log.warning(self.warning("wrong attributes for <pdf:font>"))
