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

from __future__ import print_function, unicode_literals

import copy
import json
import logging
import re
import string
import warnings

from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.textlabels import Label
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.platypus.doctemplate import FrameBreak, NextPageTemplate
from reportlab.platypus.flowables import Flowable, HRFlowable, PageBreak, Spacer
from reportlab.platypus.frames import Frame
from reportlab.platypus.paraparser import ABag, tt2ps

from .charts import DoughnutChart, PieChart, HorizontalLine, VerticalBar, HorizontalBar, LegendedPieChart
from xhtml2pdf import xhtml2pdf_reportlab
from xhtml2pdf.util import dpi96, getAlign, getColor, getSize
from xhtml2pdf.xhtml2pdf_reportlab import PmlImage, PmlPageTemplate

log = logging.getLogger("xhtml2pdf")


def deprecation(message):
    warnings.warn("<" + message + "> is deprecated!", DeprecationWarning, stacklevel=2)


class pisaTag:
    """
    The default class for a tag definition
    """

    def __init__(self, node, attr):
        self.node = node
        self.tag = node.tagName
        self.attr = attr

    def start(self, c):
        pass

    def end(self, c):
        pass


class pisaTagBODY(pisaTag):
    """
    We can also asume that there is a BODY tag because html5lib
    adds it for us. Here we take the base font size for later calculations
    in the FONT tag.
    """

    def start(self, c):
        c.baseFontSize = c.frag.fontSize
        # print("base font size", c.baseFontSize)


class pisaTagTITLE(pisaTag):
    def end(self, c):
        c.meta["title"] = c.text
        c.clearFrag()


class pisaTagSTYLE(pisaTag):
    def start(self, c):
        c.addPara()


    def end(self, c):
        c.clearFrag()


class pisaTagMETA(pisaTag):
    def start(self, c):
        name = self.attr.name.lower()
        if name in ("author", "subject", "keywords"):
            c.meta[name] = self.attr.content


class pisaTagSUP(pisaTag):
    def start(self, c):
        c.frag.super = 1


class pisaTagSUB(pisaTag):
    def start(self, c):
        c.frag.sub = 1


class pisaTagA(pisaTag):
    rxLink = r"^(#|[a-z]+\:).*"


    def start(self, c):
        attr = self.attr
        # XXX Also support attr.id ?
        if attr.name:
            # Important! Make sure that cbDefn is not inherited by other
            # fragments because of a bug in Reportlab!
            afrag = c.frag.clone()
            # These 3 lines are needed to fix an error with non internal fonts
            afrag.fontName = "Helvetica"
            afrag.bold = 0
            afrag.italic = 0
            afrag.cbDefn = ABag(
                kind="anchor",
                name=attr.name,
                label="anchor")
            c.fragAnchor.append(afrag)
            c.anchorName.append(attr.name)
        if attr.href and re.match(self.rxLink, attr.href):
            c.frag.link = attr.href

    def end(self, c):
        pass


class pisaTagFONT(pisaTag):
    # Source: http://www.w3.org/TR/CSS21/fonts.html#propdef-font-size

    def start(self, c):
        if self.attr["color"] is not None:
            c.frag.textColor = getColor(self.attr["color"])
        if self.attr["face"] is not None:
            c.frag.fontName = c.getFontName(self.attr["face"])
        if self.attr["size"] is not None:
            size = getSize(self.attr["size"], c.frag.fontSize, c.baseFontSize)
            c.frag.fontSize = max(size, 1.0)

    def end(self, c):
        pass


class pisaTagP(pisaTag):
    def start(self, c):
        # save the type of tag; it's used in PmlBaseDoc.afterFlowable()
        # to check if we need to add an outline-entry
        # c.frag.tag = self.tag
        if self.attr.align is not None:
            c.frag.alignment = getAlign(self.attr.align)


class pisaTagDIV(pisaTagP):
    pass


class pisaTagH1(pisaTagP):
    pass


class pisaTagH2(pisaTagP):
    pass


class pisaTagH3(pisaTagP):
    pass


class pisaTagH4(pisaTagP):
    pass


class pisaTagH5(pisaTagP):
    pass


class pisaTagH6(pisaTagP):
    pass


def listDecimal(c):
    c.listCounter += 1
    return str("%d." % c.listCounter)


roman_numeral_map = (
    (1000, 'M'),
    (900, 'CM'),
    (500, 'D'),
    (400, 'CD'),
    (100, 'C'),
    (90, 'XC'),
    (50, 'L'),
    (40, 'XL'),
    (10, 'X'),
    (9, 'IX'),
    (5, 'V'),
    (4, 'IV'),
    (1, 'I'),
)


def int_to_roman(i):
    result = []
    for integer, numeral in roman_numeral_map:
        count = int(i / integer)
        result.append(numeral * count)
        i -= integer * count
    return ''.join(result)


def listUpperRoman(c):
    c.listCounter += 1
    roman = int_to_roman(c.listCounter)
    return str("%s." % roman)


def listLowerRoman(c):
    return listUpperRoman(c).lower()


def listUpperAlpha(c):
    c.listCounter += 1
    index = c.listCounter - 1
    try:
        alpha = string.ascii_uppercase[index]
    except IndexError:
        # needs to start over and double the character
        # this will probably fail for anything past the 2nd time
        alpha = string.ascii_uppercase[index - 26]
        alpha *= 2
    return str("%s." % alpha)


def listLowerAlpha(c):
    return listUpperAlpha(c).lower()


_bullet = u"\u2022"
_list_style_type = {
    "none": u"",
    "disc": _bullet,
    "circle": _bullet,  # XXX PDF has no equivalent
    "square": _bullet,  # XXX PDF has no equivalent
    "decimal": listDecimal,
    "decimal-leading-zero": listDecimal,
    "lower-roman": listLowerRoman,
    "upper-roman": listUpperRoman,
    "hebrew": listDecimal,
    "georgian": listDecimal,
    "armenian": listDecimal,
    "cjk-ideographic": listDecimal,
    "hiragana": listDecimal,
    "katakana": listDecimal,
    "hiragana-iroha": listDecimal,
    "katakana-iroha": listDecimal,
    "lower-latin": listDecimal,
    "lower-alpha": listLowerAlpha,
    "upper-latin": listDecimal,
    "upper-alpha": listUpperAlpha,
    "lower-greek": listDecimal,
}


class pisaTagUL(pisaTagP):
    def start(self, c):
        self.counter, c.listCounter = c.listCounter, 0

    def end(self, c):
        c.addPara()
        # XXX Simulate margin for the moment
        c.addStory(Spacer(width=1, height=c.fragBlock.spaceAfter))
        c.listCounter = self.counter


class pisaTagOL(pisaTagUL):
    pass


class pisaTagLI(pisaTag):
    def start(self, c):
        lst = _list_style_type.get(c.frag.listStyleType or "disc", _bullet)
        frag = copy.copy(c.frag)

        self.offset = 0
        if frag.listStyleImage is not None:
            frag.text = u""
            f = frag.listStyleImage
            if f and (not f.notFound()):
                img = PmlImage(
                    f.getData(),
                    width=None,
                    height=None)
                img.drawHeight *= dpi96
                img.drawWidth *= dpi96
                img.pisaZoom = frag.zoom
                img.drawWidth *= img.pisaZoom
                img.drawHeight *= img.pisaZoom
                frag.image = img
                self.offset = max(0, img.drawHeight - c.frag.fontSize)
        else:
            if type(lst) == type(u""):
                frag.text = lst
            else:
                # XXX This should be the recent font, but it throws errors in Reportlab!
                frag.text = lst(c)

        # XXX This should usually be done in the context!!!
        frag.fontName = frag.bulletFontName = tt2ps(frag.fontName, frag.bold, frag.italic)
        c.frag.bulletText = [frag]

    def end(self, c):
        c.fragBlock.spaceBefore += self.offset


class pisaTagBR(pisaTag):
    def start(self, c):
        c.frag.lineBreak = 1
        c.addFrag()
        c.fragStrip = True
        del c.frag.lineBreak
        c.force = True


class pisaTagIMG(pisaTag):
    def start(self, c):
        attr = self.attr
        log.debug("Parsing img tag, src: {}".format(attr.src))
        log.debug("Attrs: {}".format(attr))

        if attr.src:
            filedata = attr.src.getData()
            if filedata:
                try:
                    align = attr.align or c.frag.vAlign or "baseline"
                    width = c.frag.width
                    height = c.frag.height

                    if attr.width:
                        width = attr.width * dpi96
                    if attr.height:
                        height = attr.height * dpi96

                    img = PmlImage(
                        filedata,
                        width=None,
                        height=None)

                    img.pisaZoom = c.frag.zoom

                    img.drawHeight *= dpi96
                    img.drawWidth *= dpi96

                    if (width is None) and (height is not None):
                        factor = getSize(height, default=img.drawHeight) / img.drawHeight
                        img.drawWidth *= factor
                        img.drawHeight = getSize(height, default=img.drawHeight)
                    elif (height is None) and (width is not None):
                        factor = getSize(width, default=img.drawWidth) / img.drawWidth
                        img.drawHeight *= factor
                        img.drawWidth = getSize(width, default=img.drawWidth)
                    elif (width is not None) and (height is not None):
                        img.drawWidth = getSize(width, default=img.drawWidth)
                        img.drawHeight = getSize(height, default=img.drawHeight)

                    img.drawWidth *= img.pisaZoom
                    img.drawHeight *= img.pisaZoom

                    img.spaceBefore = c.frag.spaceBefore
                    img.spaceAfter = c.frag.spaceAfter

                    # print "image", id(img), img.drawWidth, img.drawHeight

                    '''
                    TODO:
    
                    - Apply styles
                    - vspace etc.
                    - Borders
                    - Test inside tables
                    '''

                    c.force = True
                    if align in ["left", "right"]:

                        c.image = img
                        c.imageData = dict(
                            align=align
                        )

                    else:

                        # Important! Make sure that cbDefn is not inherited by other
                        # fragments because of a bug in Reportlab!
                        # afrag = c.frag.clone()

                        valign = align
                        if valign in ["texttop"]:
                            valign = "top"
                        elif valign in ["absmiddle"]:
                            valign = "middle"
                        elif valign in ["absbottom", "baseline"]:
                            valign = "bottom"

                        afrag = c.frag.clone()
                        afrag.text = ""
                        afrag.fontName = "Helvetica" # Fix for a nasty bug!!!
                        afrag.cbDefn = ABag(
                            kind="img",
                            image=img, # .getImage(), # XXX Inline?
                            valign=valign,
                            fontName="Helvetica",
                            fontSize=img.drawHeight,
                            width=img.drawWidth,
                            height=img.drawHeight)

                        c.fragList.append(afrag)
                        c.fontSize = img.drawHeight

                except Exception:  # TODO: Kill catch-all
                    log.warning(c.warning("Error in handling image"), exc_info=1)
            else:
                log.warning(c.warning("Need a valid file name!"))
        else:
            log.warning(c.warning("Need a valid file name!"))

class pisaTagHR(pisaTag):
    def start(self, c):
        c.addPara()
        c.addStory(HRFlowable(
            color=self.attr.color,
            thickness=self.attr.size,
            width=self.attr.get('width', "100%") or "100%",
            spaceBefore=c.frag.spaceBefore,
            spaceAfter=c.frag.spaceAfter
        ))

# --- Forms


if 0:

    class pisaTagINPUT(pisaTag):

        def _render(self, c, attr):
            width = 10
            height = 10
            if attr.type == "text":
                width = 100
                height = 12
            c.addStory(xhtml2pdf_reportlab.PmlInput(attr.name,
                                                    type=attr.type,
                                                    default=attr.value,
                                                    width=width,
                                                    height=height,
            ))

        def end(self, c):
            c.addPara()
            attr = self.attr
            if attr.name:
                self._render(c, attr)
            c.addPara()

    class pisaTagTEXTAREA(pisaTagINPUT):

        def _render(self, c, attr):
            c.addStory(xhtml2pdf_reportlab.PmlInput(attr.name,
                                                    default="",
                                                    width=100,
                                                    height=100))

    class pisaTagSELECT(pisaTagINPUT):

        def start(self, c):
            c.select_options = ["One", "Two", "Three"]

        def _render(self, c, attr):
            c.addStory(xhtml2pdf_reportlab.PmlInput(attr.name,
                                                    type="select",
                                                    default=c.select_options[0],
                                                    options=c.select_options,
                                                    width=100,
                                                    height=40))
            c.select_options = None

    class pisaTagOPTION(pisaTag):

        pass


class pisaTagPDFNEXTPAGE(pisaTag):
    """
    <pdf:nextpage name="" />
    """

    def start(self, c):
        c.addPara()
        if self.attr.name:
            c.addStory(NextPageTemplate(self.attr.name))
        c.addStory(PageBreak())


class pisaTagPDFNEXTTEMPLATE(pisaTag):
    """
    <pdf:nexttemplate name="" />
    """

    def start(self, c):
        c.addStory(NextPageTemplate(self.attr["name"]))


class pisaTagPDFNEXTFRAME(pisaTag):
    """
    <pdf:nextframe name="" />
    """

    def start(self, c):
        c.addPara()
        c.addStory(FrameBreak())


class pisaTagPDFSPACER(pisaTag):
    """
    <pdf:spacer height="" />
    """

    def start(self, c):
        c.addPara()
        c.addStory(Spacer(1, self.attr.height))


class pisaTagPDFPAGENUMBER(pisaTag):
    """
    <pdf:pagenumber example="" />
    """

    def start(self, c):
        c.frag.pageNumber = True
        c.addFrag(self.attr.example)
        c.frag.pageNumber = False


class pisaTagPDFPAGECOUNT(pisaTag):
    """
    <pdf:pagecount />
    """

    def start(self, c):
        c.frag.pageCount = True
        c.addFrag()
        c.frag.pageCount = False

    def end(self, c):
        c.addPageCount()


class pisaTagPDFTOC(pisaTag):
    """
    <pdf:toc />
    """

    def end(self, c):
        c.multiBuild = True
        c.addTOC()


class pisaTagPDFFRAME(pisaTag):
    """
    <pdf:frame name="" static box="" />
    """

    def start(self, c):
        deprecation("pdf:frame")
        attrs = self.attr

        name = attrs["name"]
        if name is None:
            name = "frame%d" % c.UID()

        x, y, w, h = attrs.box
        self.frame = Frame(
            x, y, w, h,
            id=name,
            leftPadding=0,
            rightPadding=0,
            bottomPadding=0,
            topPadding=0,
            showBoundary=attrs.border)

        self.static = False
        if self.attr.static:
            self.static = True
            c.addPara()
            self.story = c.swapStory()
        else:
            c.frameList.append(self.frame)

    def end(self, c):
        if self.static:
            c.addPara()
            self.frame.pisaStaticStory = c.story
            c.frameStaticList.append(self.frame)
            c.swapStory(self.story)


class pisaTagPDFTEMPLATE(pisaTag):
    """
    <pdf:template name="" static box="" >
        <pdf:frame...>
    </pdf:template>
    """

    def start(self, c):
        deprecation("pdf:template")
        attrs = self.attr
        name = attrs["name"]
        c.frameList = []
        c.frameStaticList = []
        if name in c.templateList:
            log.warning(c.warning("template '%s' has already been defined", name))

    def end(self, c):
        attrs = self.attr
        name = attrs["name"]
        if len(c.frameList) <= 0:
            log.warning(c.warning("missing frame definitions for template"))

        pt = PmlPageTemplate(
            id=name,
            frames=c.frameList,
            pagesize=A4,
        )
        pt.pisaStaticList = c.frameStaticList
        pt.pisaBackgroundList = c.pisaBackgroundList
        pt.pisaBackground = self.attr.background

        c.templateList[name] = pt
        c.template = None
        c.frameList = []
        c.frameStaticList = []

class pisaTagPDFLANGUAGE(pisaTag):
    """
    <pdf:language name=""/>
    """
    def start(self, c):
        setattr(c,'language',self.attr.name)

class pisaTagPDFFONT(pisaTag):
    """
    <pdf:fontembed name="" src="" />
    """
    def start(self, c):
        deprecation("pdf:font")
        c.loadFont(self.attr.name, self.attr.src, self.attr.encoding)


class pisaTagPDFBARCODE(pisaTag):
    _codeName = {
        "I2OF5": "I2of5",
        "ITF": "I2of5",
        "CODE39": "Standard39",
        "EXTENDEDCODE39": "Extended39",
        "CODE93": "Standard93",
        "EXTENDEDCODE93": "Extended93",
        "MSI": "MSI",
        "CODABAR": "Codabar",
        "NW7": "Codabar",
        "CODE11": "Code11",
        "FIM": "FIM",
        "POSTNET": "POSTNET",
        "USPS4S": "USPS_4State",
        "CODE128": "Code128",
        "EAN13": "EAN13",
        "EAN8": "EAN8",
        "QR": "QR",
    }

    class _barcodeWrapper(Flowable):
        """
        Wrapper for barcode widget
        """
        def __init__(self, codeName="Code128", value="", **kw):
            self.vertical = kw.get('vertical', 0)
            self.widget = createBarcodeDrawing(codeName, value=value, **kw)

        def draw(self, canvas, xoffset=0, **kw):
            # NOTE: 'canvas' is mutable, so canvas.restoreState() is a MUST.
            canvas.saveState()
            # NOTE: checking vertical value to rotate the barcode
            if self.vertical:
                width, height = self.wrap(0, 0)
                # Note: moving our canvas to the new origin
                canvas.translate(height, -width)
                canvas.rotate(90)
            else:
                canvas.translate(xoffset, 0)
            self.widget.canv = canvas
            self.widget.draw()
            canvas.restoreState()

        def wrap(self, aW, aH):
            return self.widget.wrap(aW, aH)

    def start(self, c):
        attr = self.attr
        codeName = attr.type or "Code128"
        codeName = pisaTagPDFBARCODE._codeName[codeName.upper().replace("-", "")]
        humanReadable = int(attr.humanreadable)
        vertical = int(attr.vertical)
        checksum = int(attr.checksum)
        barWidth = attr.barwidth or 0.01 * inch
        barHeight = attr.barheight or 0.5 * inch
        fontName = c.getFontName("OCRB10,OCR-B,OCR B,OCRB")  # or "Helvetica"
        fontSize = attr.fontsize or 2.75 * mm

        # Assure minimal size.
        if codeName in ("EAN13", "EAN8"):
            barWidth = max(barWidth, 0.264 * mm)
            fontSize = max(fontSize, 2.75 * mm)
        else:  # Code39 etc.
            barWidth = max(barWidth, 0.0075 * inch)

        barcode = pisaTagPDFBARCODE._barcodeWrapper(
            codeName=codeName,
            value=attr.value,
            barWidth=barWidth,
            barHeight=barHeight,
            humanReadable=humanReadable,
            vertical=vertical,
            checksum=checksum,
            fontName=fontName,
            fontSize=fontSize,
        )

        width, height = barcode.wrap(c.frag.width, c.frag.height)
        c.force = True

        valign = attr.align or c.frag.vAlign or "baseline"
        if valign in ["texttop"]:
            valign = "top"
        elif valign in ["absmiddle"]:
            valign = "middle"
        elif valign in ["absbottom", "baseline"]:
            valign = "bottom"

        afrag = c.frag.clone()
        afrag.text = ""
        afrag.fontName = fontName
        afrag.cbDefn = ABag(
            kind="barcode",
            barcode=barcode,
            width=width,
            height=height,
            valign=valign,
        )
        c.fragList.append(afrag)


class pisaTagCANVAS(pisaTag):

    def __init__(self, node, attr):
        super().__init__(node, attr)
        self.chart = None
        self.shapes = {
            'horizontalbar': HorizontalBar,
            'verticalbar': VerticalBar,
            'horizontalline': HorizontalLine,
            'pie': PieChart,
            'doughnut': DoughnutChart,
            'legendedPie': LegendedPieChart
        }

    def start(self, c):
        pass

    def end(self, c):

        data = None
        width = 350
        height = 150

        try:
            data = json.loads(c.text)
        except json.JSONDecodeError:
            print("JSON Decode Error")

        if data:

            nodetype = dict(c.node.attributes).get('type')
            nodewidth = dict(c.node.attributes).get('width')
            nodeheight = dict(c.node.attributes).get('height')
            canvastype = None

            if nodetype is not None:
                canvastype = nodetype.nodeValue

            if canvastype:
                c.clearFrag()

            if nodewidth:
                width = int(nodewidth.nodeValue)
            if nodeheight:
                height = int(nodeheight.nodeValue)

            self.chart = self.shapes[data['type']]()
            draw = Drawing(width, height)  # CONTAINER
            draw.background = Rect(115, 25, width, height, strokeWidth=1, strokeColor="#868686", fillColor="#f8fce8")

            # REQUIRED DATA
            self.chart.set_properties(data)


            #OPTIONAL DATA
            if "title" in data:
                title = Label()
                self.chart.set_title_properties(data['title'], title)
                draw.add(title)

            if "legend" in data:
                if data["legend"]:
                    legend = Legend()
                    self.chart.set_legend(data['legend'], legend)
                    self.chart.load_data_legend(data, legend)
                    draw.add(legend)

            # ADD CHART TO DRAW OBJECT
            draw.add(self.chart)
            c.addStory(draw)