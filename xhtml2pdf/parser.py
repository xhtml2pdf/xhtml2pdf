# -*- coding: utf-8 -*-

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

from html5lib import treebuilders, inputstream
from xhtml2pdf import tables
from xhtml2pdf import tags
from xhtml2pdf.default import TAGS, STRING, INT, BOOL, SIZE, COLOR, FILE
from xhtml2pdf.default import BOX, POS, MUST, FONT
from xhtml2pdf.util import getSize, getBool, toList, getColor, getAlign
from xhtml2pdf.util import getBox, getPos, pisaTempFile
from reportlab.platypus.doctemplate import NextPageTemplate, FrameBreak
from reportlab.platypus.flowables import PageBreak, KeepInFrame
from xhtml2pdf.xhtml2pdf_reportlab import PmlRightPageBreak, PmlLeftPageBreak
from xhtml2pdf.tags import * # TODO: Kill wild import!
from xhtml2pdf.tables import * # TODO: Kill wild import!
from xhtml2pdf.util import * # TODO: Kill wild import!
from xml.dom import Node
import copy
import html5lib
import logging
import re
import types
import xhtml2pdf.w3c.cssDOMElementInterface as cssDOMElementInterface
import xml.dom.minidom


CSSAttrCache = {}

log = logging.getLogger("xhtml2pdf")

rxhttpstrip = re.compile("https?://[^/]+(.*)", re.M | re.I)

PISA_TAGS = {}
for module in [tags, tables]:
    for key in dir(module):
        if key.startswith('pisaTag'):
            tag = key.split('pisaTag', 1)[1]
            PISA_TAGS[tag] = getattr(module, key)

DEFAULT_LOOP_KWARGS = {
    'margin-top': 0,
    'margin-bottom': 0,
    'margin-left': 0,
    'margin-right': 0,
    }

MISSING = object()
FRAME_MODE_TYPES = ('shrink', 'error', 'overflow', 'truncate')
ELEMENT_NODE = Node.ELEMENT_NODE
TEXT_NODE = Node.TEXT_NODE


class AttrContainer(dict):
    def __getattr__(self, name):
        try:
            return dict.__getattr__(self, name)
        except:
            return self[name]


def pisaGetAttributes(c, tag, attributes):
    global TAGS

    attrs = {}
    if attributes:
        for k, v in attributes.items():
            try:
                attrs[str(k)] = str(v)  # XXX no Unicode! Reportlab fails with template names
            except:
                attrs[k] = v

    nattrs = {}
    if tag in TAGS:
        block, adef = TAGS[tag]
        adef["id"] = STRING
        # print block, adef
        for k, v in adef.iteritems():
            nattrs[k] = None
            # print k, v
            # defaults, wenn vorhanden
            if type(v) == types.TupleType:
                if v[1] == MUST:
                    if k not in attrs:
                        log.warn(c.warning("Attribute '%s' must be set!", k))
                        nattrs[k] = None
                        continue
                nv = attrs.get(k, v[1])
                dfl = v[1]
                v = v[0]
            else:
                nv = attrs.get(k, None)
                dfl = None

            if nv is not None:
                if type(v) == types.ListType:
                    nv = nv.strip().lower()
                    if nv not in v:
                        #~ raise PML_EXCEPTION, "attribute '%s' of wrong value, allowed is one of: %s" % (k, repr(v))
                        log.warn(c.warning("Attribute '%s' of wrong value, allowed is one of: %s", k, repr(v)))
                        nv = dfl

                elif v == BOOL:
                    nv = nv.strip().lower()
                    nv = nv in ("1", "y", "yes", "true", str(k))

                elif v == SIZE:
                    try:
                        nv = getSize(nv)
                    except:
                        log.warn(c.warning("Attribute '%s' expects a size value", k))

                elif v == BOX:
                    nv = getBox(nv, c.pageSize)

                elif v == POS:
                    nv = getPos(nv, c.pageSize)

                elif v == INT:
                    nv = int(nv)

                elif v == COLOR:
                    nv = getColor(nv)

                elif v == FILE:
                    nv = c.getFile(nv)

                elif v == FONT:
                    nv = c.getFontName(nv)

                nattrs[k] = nv

    return AttrContainer(nattrs)


attrNames = '''
    color
    font-family
    font-size
    font-weight
    font-style
    text-decoration
    line-height
    letter-spacing
    background-color
    display
    margin-left
    margin-right
    margin-top
    margin-bottom
    padding-left
    padding-right
    padding-top
    padding-bottom
    border-top-color
    border-top-style
    border-top-width
    border-bottom-color
    border-bottom-style
    border-bottom-width
    border-left-color
    border-left-style
    border-left-width
    border-right-color
    border-right-style
    border-right-width
    text-align
    vertical-align
    width
    height
    zoom
    page-break-after
    page-break-before
    list-style-type
    list-style-image
    white-space
    text-indent
    -pdf-page-break
    -pdf-frame-break
    -pdf-next-page
    -pdf-keep-with-next
    -pdf-outline
    -pdf-outline-level
    -pdf-outline-open
    -pdf-line-spacing
    -pdf-keep-in-frame-mode
    -pdf-word-wrap
    '''.strip().split()


def getCSSAttr(self, cssCascade, attrName, default=NotImplemented):
    if attrName in self.cssAttrs:
        return self.cssAttrs[attrName]

    try:
        result = cssCascade.findStyleFor(self.cssElement, attrName, default)
    except LookupError:
        result = None

    # XXX Workaround for inline styles
    try:
        style = self.cssStyle
    except:
        style = self.cssStyle = cssCascade.parser.parseInline(self.cssElement.getStyleAttr() or '')[0]
    if attrName in style:
        result = style[attrName]

    if result == 'inherit':
        if hasattr(self.parentNode, 'getCSSAttr'):
            result = self.parentNode.getCSSAttr(cssCascade, attrName, default)
        elif default is not NotImplemented:
            return default
        raise LookupError("Could not find inherited CSS attribute value for '%s'" % (attrName,))

    if result is not None:
        self.cssAttrs[attrName] = result
    return result


#TODO: Monkeypatching standard lib should go away.
xml.dom.minidom.Element.getCSSAttr = getCSSAttr

# Create an aliasing system.  Many sources use non-standard tags, because browsers allow
# them to.  This allows us to map a nonstandard name to the standard one.
nonStandardAttrNames = {
    'bgcolor': 'background-color',
}

def mapNonStandardAttrs(c, n, attrList):
    for attr in nonStandardAttrNames:
        if attr in attrList and nonStandardAttrNames[attr] not in c:
            c[nonStandardAttrNames[attr]] = attrList[attr]
    return c

def getCSSAttrCacheKey(node):
    _cl = _id = _st = ''
    for k, v in node.attributes.items():
        if k == 'class':
            _cl = v
        elif k == 'id':
            _id = v
        elif k == 'style':
            _st = v
    return "%s#%s#%s#%s#%s" % (id(node.parentNode), node.tagName.lower(), _cl, _id, _st)

def CSSCollect(node, c):
    #node.cssAttrs = {}
    #return node.cssAttrs

    if c.css:

        _key = getCSSAttrCacheKey(node)

        if hasattr(node.parentNode, "tagName"):
            if node.parentNode.tagName.lower() != "html":
                CachedCSSAttr = CSSAttrCache.get(_key, None)
                if CachedCSSAttr is not None:
                    node.cssAttrs = CachedCSSAttr
                    return CachedCSSAttr

        node.cssElement = cssDOMElementInterface.CSSDOMElementInterface(node)
        node.cssAttrs = {}
        # node.cssElement.onCSSParserVisit(c.cssCascade.parser)
        cssAttrMap = {}
        for cssAttrName in attrNames:
            try:
                cssAttrMap[cssAttrName] = node.getCSSAttr(c.cssCascade, cssAttrName)
            #except LookupError:
            #    pass
            except Exception: # TODO: Kill this catch-all!
                log.debug("CSS error '%s'", cssAttrName, exc_info=1)

        CSSAttrCache[_key] = node.cssAttrs

    return node.cssAttrs

def CSS2Frag(c, kw, isBlock):
    # COLORS
    if "color" in c.cssAttr:
        c.frag.textColor = getColor(c.cssAttr["color"])
    if "background-color" in c.cssAttr:
        c.frag.backColor = getColor(c.cssAttr["background-color"])
        # FONT SIZE, STYLE, WEIGHT
    if "font-family" in c.cssAttr:
        c.frag.fontName = c.getFontName(c.cssAttr["font-family"])
    if "font-size" in c.cssAttr:
        # XXX inherit
        c.frag.fontSize = max(getSize("".join(c.cssAttr["font-size"]), c.frag.fontSize, c.baseFontSize), 1.0)
    if "line-height" in c.cssAttr:
        leading = "".join(c.cssAttr["line-height"])
        c.frag.leading = getSize(leading, c.frag.fontSize)
        c.frag.leadingSource = leading
    else:
        c.frag.leading = getSize(c.frag.leadingSource, c.frag.fontSize)
    if "letter-spacing" in c.cssAttr:
        c.frag.letterSpacing = c.cssAttr["letter-spacing"]
    if "-pdf-line-spacing" in c.cssAttr:
        c.frag.leadingSpace = getSize("".join(c.cssAttr["-pdf-line-spacing"]))
        # print "line-spacing", c.cssAttr["-pdf-line-spacing"], c.frag.leading
    if "font-weight" in c.cssAttr:
        value = c.cssAttr["font-weight"].lower()
        if value in ("bold", "bolder", "500", "600", "700", "800", "900"):
            c.frag.bold = 1
        else:
            c.frag.bold = 0
    for value in toList(c.cssAttr.get("text-decoration", "")):
        if "underline" in value:
            c.frag.underline = 1
        if "line-through" in value:
            c.frag.strike = 1
        if "none" in value:
            c.frag.underline = 0
            c.frag.strike = 0
    if "font-style" in c.cssAttr:
        value = c.cssAttr["font-style"].lower()
        if value in ("italic", "oblique"):
            c.frag.italic = 1
        else:
            c.frag.italic = 0
    if "white-space" in c.cssAttr:
        # normal | pre | nowrap
        c.frag.whiteSpace = str(c.cssAttr["white-space"]).lower()
        # ALIGN & VALIGN
    if "text-align" in c.cssAttr:
        c.frag.alignment = getAlign(c.cssAttr["text-align"])
    if "vertical-align" in c.cssAttr:
        c.frag.vAlign = c.cssAttr["vertical-align"]
        # HEIGHT & WIDTH
    if "height" in c.cssAttr:
        c.frag.height = "".join(toList(c.cssAttr["height"]))  # XXX Relative is not correct!
        if c.frag.height in ("auto",):
            c.frag.height = None
    if "width" in c.cssAttr:
        c.frag.width = "".join(toList(c.cssAttr["width"]))  # XXX Relative is not correct!
        if c.frag.width in ("auto",):
            c.frag.width = None
        # ZOOM
    if "zoom" in c.cssAttr:
        zoom = "".join(toList(c.cssAttr["zoom"]))  # XXX Relative is not correct!
        if zoom.endswith("%"):
            zoom = float(zoom[: - 1]) / 100.0
        c.frag.zoom = float(zoom)
        # MARGINS & LIST INDENT, STYLE
    if isBlock:
        if "margin-top" in c.cssAttr:
            c.frag.spaceBefore = getSize(c.cssAttr["margin-top"], c.frag.fontSize)
        if "margin-bottom" in c.cssAttr:
            c.frag.spaceAfter = getSize(c.cssAttr["margin-bottom"], c.frag.fontSize)
        if "margin-left" in c.cssAttr:
            c.frag.bulletIndent = kw["margin-left"]  # For lists
            kw["margin-left"] += getSize(c.cssAttr["margin-left"], c.frag.fontSize)
            c.frag.leftIndent = kw["margin-left"]
        if "margin-right" in c.cssAttr:
            kw["margin-right"] += getSize(c.cssAttr["margin-right"], c.frag.fontSize)
            c.frag.rightIndent = kw["margin-right"]
        if "text-indent" in c.cssAttr:
            c.frag.firstLineIndent = getSize(c.cssAttr["text-indent"], c.frag.fontSize)
        if "list-style-type" in c.cssAttr:
            c.frag.listStyleType = str(c.cssAttr["list-style-type"]).lower()
        if "list-style-image" in c.cssAttr:
            c.frag.listStyleImage = c.getFile(c.cssAttr["list-style-image"])
        # PADDINGS
    if isBlock:
        if "padding-top" in c.cssAttr:
            c.frag.paddingTop = getSize(c.cssAttr["padding-top"], c.frag.fontSize)
        if "padding-bottom" in c.cssAttr:
            c.frag.paddingBottom = getSize(c.cssAttr["padding-bottom"], c.frag.fontSize)
        if "padding-left" in c.cssAttr:
            c.frag.paddingLeft = getSize(c.cssAttr["padding-left"], c.frag.fontSize)
        if "padding-right" in c.cssAttr:
            c.frag.paddingRight = getSize(c.cssAttr["padding-right"], c.frag.fontSize)
        # BORDERS
    if isBlock:
        if "border-top-width" in c.cssAttr:
            c.frag.borderTopWidth = getSize(c.cssAttr["border-top-width"], c.frag.fontSize)
        if "border-bottom-width" in c.cssAttr:
            c.frag.borderBottomWidth = getSize(c.cssAttr["border-bottom-width"], c.frag.fontSize)
        if "border-left-width" in c.cssAttr:
            c.frag.borderLeftWidth = getSize(c.cssAttr["border-left-width"], c.frag.fontSize)
        if "border-right-width" in c.cssAttr:
            c.frag.borderRightWidth = getSize(c.cssAttr["border-right-width"], c.frag.fontSize)
        if "border-top-style" in c.cssAttr:
            c.frag.borderTopStyle = c.cssAttr["border-top-style"]
        if "border-bottom-style" in c.cssAttr:
            c.frag.borderBottomStyle = c.cssAttr["border-bottom-style"]
        if "border-left-style" in c.cssAttr:
            c.frag.borderLeftStyle = c.cssAttr["border-left-style"]
        if "border-right-style" in c.cssAttr:
            c.frag.borderRightStyle = c.cssAttr["border-right-style"]
        if "border-top-color" in c.cssAttr:
            c.frag.borderTopColor = getColor(c.cssAttr["border-top-color"])
        if "border-bottom-color" in c.cssAttr:
            c.frag.borderBottomColor = getColor(c.cssAttr["border-bottom-color"])
        if "border-left-color" in c.cssAttr:
            c.frag.borderLeftColor = getColor(c.cssAttr["border-left-color"])
        if "border-right-color" in c.cssAttr:
            c.frag.borderRightColor = getColor(c.cssAttr["border-right-color"])


def pisaPreLoop(node, context, collect=False):
    """
    Collect all CSS definitions
    """
    css_data = []
    add_data = css_data.append
    actions = [(node, collect)]

    while True:
        if not actions:
            break

        node, collect = actions.pop(0)

        for child in reversed(node.childNodes):
            actions.insert(0, (child, collect))

        if node.nodeType == TEXT_NODE:
            if collect:
                add_data(node.data)

        elif node.nodeType == ELEMENT_NODE:
            name = node.tagName.lower()

            if name in ("style", "link"):
                attr = pisaGetAttributes(context, name, node.attributes)
                media = [x.strip() for x in attr.media.lower().split(",") if x.strip()]

                if attr.get("type", "").lower() in ("", "text/css") and \
                   (not media or "all" in media or "print" in media or "pdf" in media):

                    if name == "style":
                        for child in reversed(node.childNodes):
                            actions.insert(0, (child, True))

                    elif name == "link" and attr.href and attr.rel.lower() == "stylesheet":
                        # print "CSS LINK", attr
                        add_data(u'\n@import "%s" %s;' % (attr.href, u",".join(media)))

    if css_data:
        data = u''.join(css_data)
        context.addCSS(data)
        return data
    else:
        return u''


def pisaLoop(node, context, path=None, **kw):
    actions = [(node, kw, None)]
    #paths = [path]  # DEBUG LINE

    while True:
        if not actions:
            break

        node, kw, options = actions.pop(0)

        #path = list(paths.pop(0) or [])  # DEBUG LINE
        #indent = ' ' * len(path)  # DEBUG LINE

        # TEXT
        if node.nodeType == TEXT_NODE:
            context.addFrag(node.data)

            #print indent, "#", repr(node.data) #, context.frag  # DEBUG LINE
            #context.text.append(node.value)

        # ELEMENT
        elif node.nodeType == ELEMENT_NODE:
            if not options:
                node.tagName = node.tagName.replace(":", "").lower()
                if node.tagName in ("style", "script"):
                    continue

                # Prepare attributes
                attr = pisaGetAttributes(context, node.tagName, node.attributes)
                #log.debug(indent + "<%s %s>" % (node.tagName, attr) + repr(node.attributes.items())) #, path  # DEBUG LINE

                # Calculate styles
                context.cssAttr = CSSCollect(node, context)
                context.cssAttr = mapNonStandardAttrs(context.cssAttr, node, attr)
                context.node = node

                options = {}
                display = context.cssAttr.get("display", "inline").lower()
                isBlock = (display == "block")

                #print indent, node.tagName, display, context.cssAttr.get("background-color", None), attr  # DEBUG LINE

                if isBlock:
                    context.addPara()

                    # Page break by CSS
                    pdf_next_page = context.cssAttr.get('-pdf-next-page')
                    if pdf_next_page:
                        pdf_next_page = str(pdf_next_page)
                        context.addStory(NextPageTemplate(pdf_next_page))

                    pdf_page_break = context.cssAttr.get('-pdf-page-break')
                    if pdf_page_break:
                        if str(pdf_page_break).lower() == "before":
                            context.addStory(PageBreak())

                    pdf_frame_break = context.cssAttr.get('-pdf-frame-break')
                    if pdf_frame_break:
                        pdf_frame_break = str(pdf_frame_break).lower()
                        if pdf_frame_break == "before":
                            context.addStory(FrameBreak())
                        elif pdf_frame_break == "after":
                            options['frameBreakAfter'] = True

                    page_break_before = context.cssAttr.get('page-break-before')
                    if page_break_before:
                        page_break_before = str(page_break_before).lower()
                        if page_break_before == "always":
                            context.addStory(PageBreak())
                        elif page_break_before == "right":
                            context.addStory(PageBreak())
                            context.addStory(PmlRightPageBreak())
                        elif page_break_before == "left":
                            context.addStory(PageBreak())
                            context.addStory(PmlLeftPageBreak())

                if display == "none":
                    continue

                if isBlock:
                    options['isBlock'] = isBlock
                    page_break_after = context.cssAttr.get('page-break-after')
                    if page_break_after:
                        options['page_break_after'] = str(page_break_after).lower()

                # Translate CSS to frags

                # Save previous frag styles
                context.pushFrag()

                # Map styles to Reportlab fragment properties
                kw = (kw or DEFAULT_LOOP_KWARGS).copy()
                CSS2Frag(context, kw, isBlock)

                # EXTRAS
                pdf_keep_with_next = context.cssAttr.get('-pdf-keep-with-next', MISSING)
                if pdf_keep_with_next is not MISSING:
                    context.frag.keepWithNext = getBool(pdf_keep_with_next)

                pdf_outline = context.cssAttr.get('-pdf-outline', MISSING)
                if pdf_outline is not MISSING:
                    context.frag.outline = getBool(pdf_outline)

                pdf_outline_level = context.cssAttr.get('-pdf-outline-level', MISSING)
                if pdf_outline_level is not MISSING:
                    context.frag.outlineLevel = int(pdf_outline_level)

                pdf_outline_open = context.cssAttr.get('-pdf-outline-open', MISSING)
                if pdf_outline_open is not MISSING:
                    context.frag.outlineOpen = getBool(pdf_outline_open)

                pdf_word_wrap = context.cssAttr.get('-pdf-word-wrap', MISSING)
                if pdf_word_wrap is not MISSING:
                    context.frag.wordWrap = pdf_word_wrap

                # handle keep-in-frame
                keepInFrameMode = None
                pdf_keep_in_frame_mode = context.cssAttr.get('-pdf-keep-in-frame-mode')
                if pdf_keep_in_frame_mode:
                    pdf_keep_in_frame_mode = str(pdf_keep_in_frame_mode).strip().lower()
                    if pdf_keep_in_frame_mode in FRAME_MODE_TYPES:
                        keepInFrameMode = pdf_keep_in_frame_mode

                # ignore nested keep-in-frames, tables have their own KIF handling
                keepInFrame = bool(keepInFrameMode is not None and \
                                   context.keepInFrameIndex is None)
                if keepInFrame:
                    options['keepInFrame'] = True
                    # keep track of current story index, so we can wrap everythink
                    # added after this point in a KeepInFrame
                    context.keepInFrameIndex = len(context.story)

                    max_width = context.cssAttr.get('-pdf-keep-in-frame-max-width')
                    if max_width:
                        max_width = getSize("".join(max_width))
                    options['keepInFrameMaxWidth'] = max_width or 0

                    max_height = context.cssAttr.get('-pdf-keep-in-frame-max-height')
                    if max_height:
                        max_height = getSize("".join(max_height))
                    options['keepInFrameMaxHeight'] = max_height or 0

                # BEGIN tag
                klass = PISA_TAGS.get(node.tagName.upper())

                # Static block
                elementId = attr.get("id", None)
                staticFrame = context.frameStatic.get(elementId, None)
                if staticFrame:
                    context.frag.insideStaticFrame += 1
                    options.update((
                        ('oldStory', context.swapStory()),
                        ('staticFrame', staticFrame),
                        ))

                # Tag specific operations
                if klass is not None:
                    obj = klass(node, attr)
                    obj.start(context)
                    options['obj'] = obj

                context.fragBlock = options['fragBlock'] = copy.copy(context.frag)
                actions.insert(0, (node, kw, options))

                #path.append(node.tagName)  # DEBUG LINE
                #paths.insert(0, path)  # DEBUG LINE

                # Visit child nodes
                for child in reversed(node.childNodes):
                    actions.insert(0, (child, kw, None))
                    #paths.insert(0, path)  # DEBUG LINE

            else:
                context.fragBlock = options['fragBlock']

                # END tag
                obj = options.get('obj')
                if obj:
                    obj.end(context)

                # Block?
                if options.get('isBlock'):
                    context.addPara()

                    # XXX Buggy!

                    # Page break by CSS
                    page_break_after = options.get('page_break_after')
                    if page_break_after:
                        context.addStory(PageBreak())

                        if page_break_after == 'right':
                            context.addStory(PmlRightPageBreak())
                        elif page_break_after == 'left':
                            context.addStory(PmlLeftPageBreak())

                    if options.get('frameBreakAfter'):
                        context.addStory(FrameBreak())

                if options.get('keepInFrame'):
                    # get all content added after start of -pdf-keep-in-frame and wrap
                    # it in a KeepInFrame
                    substory = context.story[context.keepInFrameIndex:]
                    context.story = context.story[:context.keepInFrameIndex]
                    context.story.append(
                        KeepInFrame(
                            content=substory,
                            maxWidth=options['keepInFrameMaxWidth'],
                            maxHeight=options['keepInFrameMaxHeight']))
                    context.keepInFrameIndex = None

                # Static block, END
                staticFrame = options.get('staticFrame')
                if staticFrame:
                    context.addPara()
                    for frame in staticFrame:
                        frame.pisaStaticStory = context.story
                    context.swapStory(options['oldStory'])
                    context.frag.insideStaticFrame -= 1

                #log.debug(1, indent, "</%s>" % (node.tagName))  # DEBUG LINE

                # Reset frag style
                context.pullFrag()

        # Unknown or not handled
        else:
            for child in reversed(node.childNodes):
                actions.insert(0, (child, kw, None))
                #paths.insert(0, path)  # DEBUG LINE


def pisaParser(src, context, default_css="", xhtml=False, encoding=None, xml_output=None):
    """
    - Parse HTML and get miniDOM
    - Extract CSS informations, add default CSS, parse CSS
    - Handle the document DOM itself and build reportlab story
    - Return Context object
    """

    global CSSAttrCache
    CSSAttrCache = {}

    if xhtml:
        #TODO: XHTMLParser doesn't see to exist...
        parser = html5lib.XHTMLParser(tree=treebuilders.getTreeBuilder("dom"))
    else:
        parser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder("dom"))

    if type(src) in types.StringTypes:
        if type(src) is types.UnicodeType:
            # If an encoding was provided, do not change it.
            if not encoding:
                encoding = "utf-8"
            src = src.encode(encoding)
        src = pisaTempFile(src, capacity=context.capacity)

    # Test for the restrictions of html5lib
    if encoding:
        # Workaround for html5lib<0.11.1
        if hasattr(inputstream, "isValidEncoding"):
            if encoding.strip().lower() == "utf8":
                encoding = "utf-8"
            if not inputstream.isValidEncoding(encoding):
                log.error("%r is not a valid encoding e.g. 'utf8' is not valid but 'utf-8' is!", encoding)
        else:
            if inputstream.codecName(encoding) is None:
                log.error("%r is not a valid encoding", encoding)
    document = parser.parse(
        src,
        encoding=encoding)

    if xml_output:
        if encoding:
            xml_output.write(document.toprettyxml(encoding=encoding))
        else:
            xml_output.write(document.toprettyxml(encoding="utf8"))


    if default_css:
        context.addDefaultCSS(default_css)

    pisaPreLoop(document, context)
    #try:
    context.parseCSS()
    #except:
    #    context.cssText = DEFAULT_CSS
    #    context.parseCSS()
    # context.debug(9, pprint.pformat(context.css))

    pisaLoop(document, context)
    return context


# Shortcuts

HTML2PDF = pisaParser


def XHTML2PDF(*a, **kw):
    kw["xhtml"] = True
    return HTML2PDF(*a, **kw)


XML2PDF = XHTML2PDF
