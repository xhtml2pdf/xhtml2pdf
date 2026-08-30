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
from __future__ import annotations

import copy
import json
import logging
import re
import string
import warnings
from typing import TYPE_CHECKING, ClassVar
from xml.dom import Node

from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.textlabels import Label
from reportlab.graphics.shapes import Rect
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.platypus.doctemplate import FrameBreak, NextPageTemplate
from reportlab.platypus.flowables import Flowable, HRFlowable, PageBreak, Spacer
from reportlab.platypus.frames import Frame
from reportlab.platypus.paraparser import ABag, tt2ps

from xhtml2pdf.charts import (
    BaseChart,
    DoughnutChart,
    HorizontalBar,
    HorizontalLine,
    LegendedPieChart,
    PieChart,
    VerticalBar,
)
from xhtml2pdf.paragraph import PageNumberFlowable
from xhtml2pdf.util import (
    DPI96,
    ImageWarning,
    getAlign,
    getColor,
    getKeepInFrameMode,
    getSize,
)
from xhtml2pdf.xhtml2pdf_reportlab import (
    PmlDrawing,
    PmlImage,
    PmlInput,
    PmlPageTemplate,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.dom.minidom import Element

    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus.paraparser import ParaFrag

    from xhtml2pdf.context import pisaContext
    from xhtml2pdf.files import pisaFileObject
    from xhtml2pdf.parser import AttrContainer

log = logging.getLogger(__name__)


def deprecation(message):
    warnings.warn(f"<{message}> is deprecated!", DeprecationWarning, stacklevel=2)


def nodeText(node) -> str:
    """
    The text an element holds directly, as written.

    Read from the DOM rather than from the context, because the context text
    has been through the transformations that belong to page content -- white
    space collapsing, text-transform -- and the value of a form field is not
    page content.
    """
    return "".join(
        child.data for child in node.childNodes if child.nodeType == Node.TEXT_NODE
    )


class pisaTag:
    """The default class for a tag definition."""

    def __init__(self, node: Element, attr: AttrContainer) -> None:
        self.node: Element = node
        self.tag: str = node.tagName
        self.attr: AttrContainer = attr

    def start(self, c: pisaContext) -> None:
        pass

    def end(self, c: pisaContext) -> None:
        pass


class pisaTagBODY(pisaTag):
    """
    We can also assume that there is a BODY tag because html5lib
    adds it for us. Here we take the base font size for later calculations
    in the FONT tag.
    """

    def start(self, c: pisaContext) -> None:
        c.baseFontSize = c.frag.fontSize
        # CSS 2.1 14.2: the background of body propagates to the canvas when
        # html declares none, so it covers the whole page rather than just the
        # area body's boxes happen to occupy. No separate check for an html
        # background is needed: html's own background would already have been
        # inherited into this frag, and by the same rule it also paints the
        # canvas.
        if c.frag.backColor:
            c.pageCanvasBackground = c.frag.backColor
        if self.attr.get("dir"):
            c.setDir(self.attr["dir"])
        # print("base font size", c.baseFontSize)


class pisaTagTITLE(pisaTag):
    def end(self, c: pisaContext) -> None:  # noqa: PLR6301
        c.meta["title"] = c.text
        c.clearFrag()


class pisaTagSTYLE(pisaTag):
    def start(self, c: pisaContext) -> None:  # noqa: PLR6301
        c.addPara()

    def end(self, c: pisaContext) -> None:  # noqa: PLR6301
        c.clearFrag()


class pisaTagMETA(pisaTag):
    def start(self, c: pisaContext) -> None:
        name: str = self.attr.name.lower()
        if name in {"author", "subject", "keywords"}:
            c.meta[name] = self.attr.content


class pisaTagSUP(pisaTag):
    def start(self, c: pisaContext) -> None:  # noqa: PLR6301
        c.frag.super = 1


class pisaTagSUB(pisaTag):
    def start(self, c: pisaContext) -> None:  # noqa: PLR6301
        c.frag.sub = 1


class pisaTagA(pisaTag):
    rxLink = r"^(#|[a-z]+\:).*"

    def start(self, c: pisaContext) -> None:
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
            afrag.cbDefn = ABag(kind="anchor", name=attr.name, label="anchor")
            c.fragAnchor.append(afrag)
            c.anchorName.append(attr.name)
        if attr.href and re.match(self.rxLink, attr.href):
            c.frag.link = attr.href

    def end(self, c: pisaContext) -> None:
        pass


class pisaTagFONT(pisaTag):
    # Source: http://www.w3.org/TR/CSS21/fonts.html#propdef-font-size

    def start(self, c: pisaContext) -> None:
        if self.attr["color"] is not None:
            c.frag.textColor = getColor(self.attr["color"])
        if self.attr["face"] is not None:
            c.frag.fontName = c.getFontName(self.attr["face"])
        if self.attr["size"] is not None:
            size = getSize(self.attr["size"], c.frag.fontSize, c.baseFontSize)
            c.frag.fontSize = max(size, 1.0)

    def end(self, c: pisaContext) -> None:
        pass


class pisaTagP(pisaTag):
    def start(self, c: pisaContext) -> None:
        # save the type of tag; it's used in PmlBaseDoc.afterFlowable()
        # to check if we need to add an outline-entry
        # c.frag.tag = self.tag
        if self.attr.get("dir"):
            c.setDir(self.attr["dir"])
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


def listDecimal(c: pisaContext) -> str:
    c.listCounter += 1
    return str("%d." % c.listCounter)


def listDecimalLeadingZero(c: pisaContext) -> str:
    c.listCounter += 1
    return f"{c.listCounter:02d}."


roman_numeral_map: tuple[tuple[int, str], ...] = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


def int_to_roman(i: int) -> str:
    result: list[str] = []
    for integer, numeral in roman_numeral_map:
        count: int = int(i / integer)
        result.append(numeral * count)
        i -= integer * count
    return "".join(result)


def listUpperRoman(c: pisaContext) -> str:
    c.listCounter += 1
    roman: str = int_to_roman(c.listCounter)
    return f"{roman}."


def listLowerRoman(c: pisaContext) -> str:
    return listUpperRoman(c).lower()


def listUpperAlpha(c: pisaContext) -> str:
    c.listCounter += 1
    index: int = c.listCounter - 1
    try:
        alpha: str = string.ascii_uppercase[index]
    except IndexError:
        # needs to start over and double the character
        # this will probably fail for anything past the 2nd time
        alpha = string.ascii_uppercase[index - 26]
        alpha *= 2
    return f"{alpha}."


def listLowerAlpha(c: pisaContext) -> str:
    return listUpperAlpha(c).lower()


#: CSS 2.1 lower-greek: the 24 letters of the alphabet, with no final sigma.
_greek_alphabet: str = "\u03b1\u03b2\u03b3\u03b4\u03b5\u03b6\u03b7\u03b8"
_greek_alphabet += "\u03b9\u03ba\u03bb\u03bc\u03bd\u03be\u03bf\u03c0"
_greek_alphabet += "\u03c1\u03c3\u03c4\u03c5\u03c6\u03c7\u03c8\u03c9"


def listLowerGreek(c: pisaContext) -> str:
    c.listCounter += 1
    index: int = (c.listCounter - 1) % len(_greek_alphabet)
    return f"{_greek_alphabet[index]}."


_bullet: str = "\u2022"
#: Black square, which no text font in the base-14 set carries but
#: ZapfDingbats does.
_black_square: str = "\u25a0"

_list_style_type: dict[str, str | Callable] = {
    "none": "",
    "disc": _bullet,
    # No base-14 font has a hollow circle, so circle still borrows the disc
    # bullet. Everything else here now draws what it says.
    "circle": _bullet,
    "square": _black_square,
    "decimal": listDecimal,
    "decimal-leading-zero": listDecimalLeadingZero,
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
    # CSS 2.1: lower-latin and lower-alpha are the same counter style, as are
    # upper-latin and upper-alpha. Both latin forms used to number instead.
    "lower-latin": listLowerAlpha,
    "lower-alpha": listLowerAlpha,
    "upper-latin": listUpperAlpha,
    "upper-alpha": listUpperAlpha,
    "lower-greek": listLowerGreek,
}

#: Font to draw a marker with, where the text font cannot.
#:
#: Symbol and ZapfDingbats are base-14, so a marker never depends on an
#: embedded font being available. Symbol is also how the disc bullet stops
#: being written as U+007F: ReportLab fills seven undefined WinAnsi slots with
#: `bullet` and its codec picks the lowest, 127, which the PDF then declares
#: as plain WinAnsiEncoding where 127 means nothing at all. In Symbol the
#: bullet has one code of its own.
#: The factor is a fraction of the text size. ZapfDingbats' black square fills
#: its em, while the marker CSS asks for is a small square: measured against
#: Chromium it comes out 5px where the unscaled glyph is 11px.
_list_style_font: dict[str, tuple[str, float]] = {
    "disc": ("Symbol", 1.0),
    "circle": ("Symbol", 1.0),
    "square": ("ZapfDingbats", 0.45),
    "lower-greek": ("Symbol", 1.0),
}


class pisaTagUL(pisaTagP):
    def start(self, c: pisaContext) -> None:
        self.counter, c.listCounter = c.listCounter, 0

    def end(self, c: pisaContext):
        c.addPara()
        # XXX Simulate margin for the moment
        c.addStory(Spacer(width=1, height=c.fragBlock.spaceAfter))
        c.listCounter = self.counter


class pisaTagOL(pisaTagUL):
    def start(self, c: pisaContext) -> None:
        start = self.attr.start - 1 if self.attr.start else 0
        self.counter, c.listCounter = c.listCounter, start


class pisaTagLI(pisaTag):
    def start(self, c: pisaContext) -> None:
        style_type: str = c.frag.listStyleType or "disc"
        lst: str | Callable = _list_style_type.get(style_type, _bullet)
        frag: ParaFrag = copy.copy(c.frag)

        self.offset: int = 0
        if frag.listStyleImage is not None:
            frag.text = ""
            f = frag.listStyleImage
            if f and (not f.notFound()):
                img = PmlImage(f.getData(), src=f.uri, width=None, height=None)
                img.drawHeight *= DPI96
                img.drawWidth *= DPI96
                img.pisaZoom = frag.zoom
                img.drawWidth *= img.pisaZoom
                img.drawHeight *= img.pisaZoom
                frag.image = img
                self.offset = max(0, img.drawHeight - c.frag.fontSize)
        elif isinstance(lst, str):
            frag.text = lst
        else:
            # XXX This should be the recent font, but it throws errors in Reportlab!
            frag.text = lst(c)

        # XXX This should usually be done in the context!!!
        frag.fontName = frag.bulletFontName = tt2ps(
            frag.fontName, frag.bold, frag.italic
        )

        # A marker the text font cannot draw is set in the base-14 font that
        # can. Not for an image marker, which is not text at all.
        marker = _list_style_font.get(style_type)
        if marker and frag.listStyleImage is None:
            marker_font, size_factor = marker
            frag.fontName = frag.bulletFontName = marker_font
            frag.fontSize *= size_factor

        c.frag.bulletText = [frag]

    def end(self, c: pisaContext) -> None:
        c.fragBlock.spaceBefore += self.offset


class pisaTagBR(pisaTag):
    def start(self, c: pisaContext) -> None:  # noqa: PLR6301
        c.frag.lineBreak = 1
        c.addFrag()
        c.fragStrip = True
        del c.frag.lineBreak
        c.force = True


class pisaTagIMG(pisaTag):
    def start(self, c: pisaContext) -> None:
        attr: AttrContainer = self.attr
        log.debug("Parsing img tag, src: %r", attr.src)
        log.debug("Attrs: %r", attr)

        if attr.src:
            filedata: pisaFileObject = attr.src.getData()
            if filedata:
                try:
                    align = attr.align or c.frag.vAlign or "baseline"
                    width = c.frag.width
                    height = c.frag.height

                    if attr.width:
                        width = attr.width * DPI96
                    if attr.height:
                        height = attr.height * DPI96

                    img = PmlImage(filedata, src=attr.src.uri, width=None, height=None)

                    img.pisaZoom = c.frag.zoom

                    img.drawHeight *= DPI96
                    img.drawWidth *= DPI96

                    if (width is None) and (height is not None):
                        factor = (
                            getSize(height, default=img.drawHeight) / img.drawHeight
                        )
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

                    """
                    TODO:

                    - Apply styles
                    - vspace etc.
                    - Borders
                    - Test inside tables
                    """

                    c.force = True
                    if align in {"left", "right"}:
                        c.image = img
                        c.imageData = {"align": align}

                    else:
                        # Important! Make sure that cbDefn is not inherited by other
                        # fragments because of a bug in Reportlab!
                        # afrag = c.frag.clone()

                        valign = align
                        if valign == "texttop":
                            valign = "top"
                        elif valign == "absmiddle":
                            valign = "middle"
                        elif valign in {"absbottom", "baseline"}:
                            valign = "bottom"

                        afrag = c.frag.clone()
                        afrag.text = ""
                        afrag.fontName = "Helvetica"  # Fix for a nasty bug!!!
                        afrag.cbDefn = ABag(
                            kind="img",
                            image=img,  # .getImage(), # XXX Inline?
                            valign=valign,
                            fontName="Helvetica",
                            fontSize=img.drawHeight,
                            width=img.drawWidth,
                            height=img.drawHeight,
                        )

                        c.fragList.append(afrag)
                        c.fontSize = img.drawHeight

                except ImageWarning as e:
                    log.warning(c.warning(f"{e}:"))
                except Exception:
                    log.warning(c.warning("Error in handling image:"), exc_info=True)
            else:
                log.warning(
                    c.warning(
                        f"Could not get image data from src attribute: {attr.src.uri}"
                    )
                )
        else:
            log.warning(c.warning("The src attribute of image tag is empty!"))


class pisaTagHR(pisaTag):
    def start(self, c: pisaContext) -> None:
        c.addPara()
        c.addStory(
            HRFlowable(
                color=self.attr.color,
                thickness=self.attr.size,
                width=self.attr.get("width", "100%") or "100%",
                spaceBefore=c.frag.spaceBefore,
                spaceAfter=c.frag.spaceAfter,
            )
        )


# --- Forms


class pisaTagINPUT(pisaTag):
    # An instance method although this one needs nothing from self: pisaTagFIELD
    # subclasses read the element they were built with to render their widget.
    def _render(self, c: pisaContext, attr: AttrContainer) -> None:  # noqa: PLR6301
        width: int = 10
        height: int = 10
        if attr.type == "text":
            width = 100
            height = 12
        c.addStory(
            PmlInput(
                attr.name,
                input_type=attr.type,
                default=attr.value,
                width=width,
                height=height,
            )
        )

    def end(self, c: pisaContext) -> None:
        c.addPara()
        attr = self.attr
        if attr.name:
            if attr.type == "radio":
                # reportlab's pdfform has no radio group, so this is a box on
                # the page and nothing more. Said once, rather than letting
                # the author work out why the buttons do nothing.
                log.warning(
                    "<input type=radio> is drawn but is not a form field: %r", attr.name
                )
            self._render(c, attr)
        c.addPara()


class pisaTagFIELD(pisaTagINPUT):
    """
    A control whose content describes the field rather than the page.

    What a <textarea> holds is the value of its field, and the labels inside a
    <select> are what the reader picks from: neither belongs in the story.
    Both used to be typeset as ordinary text alongside the widget.
    """

    def start(self, c: pisaContext) -> None:
        c.addPara()
        self.story = c.swapStory()

    def swallow_content(self, c: pisaContext) -> None:
        # addPara first, so that anything typeset inside lands in the story
        # that is about to be thrown away rather than in the real one.
        c.addPara()
        c.swapStory(self.story)


class pisaTagTEXTAREA(pisaTagFIELD):
    def end(self, c: pisaContext) -> None:
        self.swallow_content(c)
        if self.attr.name:
            self._render(c, self.attr)

    def _render(self, c: pisaContext, attr: AttrContainer) -> None:
        multiline: int = 1 if int(attr.rows) > 1 else 0
        height: int = int(attr.rows) * 15
        width: int = int(attr.cols) * 5

        c.addStory(
            PmlInput(
                attr.name,
                input_type="text",
                # What the element holds is what the field starts with. It
                # used to be dropped, with a comment saying so.
                default=nodeText(self.node),
                width=width,
                height=height,
                multiline=multiline,
            )
        )


class pisaTagSELECT(pisaTagFIELD):
    """<select name=""><option value="" selected="selected">Label</option></select>."""

    def end(self, c: pisaContext) -> None:
        self.swallow_content(c)

        attr = self.attr
        if not attr.name:
            log.warning("Ignoring a <select> with no name: it cannot be a field")
            return

        options, default = self.options()
        if not options:
            log.warning("Ignoring the <select> %r: it has no options", attr.name)
            return

        c.addPara()
        c.addStory(
            PmlInput(
                attr.name,
                input_type="select",
                default=default,
                options=options,
                width=100,
                height=40,
            )
        )
        c.addPara()

    def options(self) -> tuple[list[str], str]:
        """
        The labels of this select, and which one starts out chosen.

        A PDF choice field holds one string per option, so the value attribute
        cannot travel beside its label; the label is what the reader picks
        from, so the label is what is kept.
        """
        options: list[str] = []
        default: str | None = None
        renamed = False

        for node in self.node.getElementsByTagName("option"):
            label = nodeText(node).strip()
            if not label:
                continue
            options.append(label)
            renamed = renamed or (
                node.hasAttribute("value") and node.getAttribute("value") != label
            )
            if node.hasAttribute("selected"):
                default = label

        if renamed:
            log.warning(
                "A PDF choice field cannot carry an option's value apart from"
                " its label; using the labels of <select> %r",
                self.attr.name,
            )

        return options, (
            default if default is not None else options[0] if options else ""
        )


class pisaTagPDFNEXTPAGE(pisaTag):
    """<pdf:nextpage name="" />."""

    def start(self, c: pisaContext) -> None:
        c.addPara()
        if self.attr.name:
            c.addStory(NextPageTemplate(self.attr.name))
        c.addStory(PageBreak())


class pisaTagPDFNEXTTEMPLATE(pisaTag):
    """<pdf:nexttemplate name="" />."""

    def start(self, c: pisaContext) -> None:
        c.addStory(NextPageTemplate(self.attr["name"]))


class pisaTagPDFNEXTFRAME(pisaTag):
    """<pdf:nextframe name="" />."""

    def start(self, c: pisaContext) -> None:  # noqa: PLR6301
        c.addPara()
        c.addStory(FrameBreak())


class pisaTagPDFSPACER(pisaTag):
    """<pdf:spacer height="" />."""

    def start(self, c: pisaContext) -> None:
        if self.attr.height is None:
            # The attribute machinery has already said "Attribute 'height'
            # must be set!"; building the Spacer anyway raised a TypeError on
            # None + int and took the document with it.
            log.warning("Ignoring <pdf:spacer> with no height")
            return
        c.addPara()
        c.addStory(Spacer(1, self.attr.height))


class pisaTagPDFPAGENUMBER(pisaTag):
    """<pdf:pagenumber example="" />."""

    def start(self, c: pisaContext) -> None:
        flow = PageNumberFlowable()
        # The example is what the line is measured with before the page number
        # is known. It has been a declared attribute all along and nothing
        # ever read it.
        #
        # Only when the author writes it: the attribute carries a default of
        # "0", and a page number that never resolves -- inside a table cell,
        # say -- keeps whatever it was measured with, so a default would put a
        # stray 0 on the page.
        placeholder = self.attr.example if self.node.hasAttribute("example") else ""
        pageNumber = c.addPageNumber(flow, placeholder or "")
        c.addStory(flow)
        c.frag.pageNumber = True
        c.addFrag(pageNumber)
        c.frag.pageNumber = False


class pisaTagPDFPAGECOUNT(pisaTag):
    """<pdf:pagecount />."""

    def start(self, c: pisaContext) -> None:  # noqa: PLR6301
        flow = PageNumberFlowable()
        pageCount = c.getPageCount(flow)
        c.addStory(flow)
        c.frag.pageCount = True
        c.addFrag(pageCount)
        c.frag.pageCount = False

    def end(self, c: pisaContext) -> None:  # noqa: PLR6301
        c.addPageCount()


class pisaTagPDFTOC(pisaTag):
    """<pdf:toc />."""

    def start(self, c: pisaContext) -> None:  # noqa: PLR6301
        # In start, not in end, like <pdf:nextpage> and <pdf:nextframe>. The
        # HTML parser ignores the self-closing slash on an element it does not
        # know, so <pdf:toc /> stays open and takes the rest of the document
        # with it as children; emitting on the closing tag put the table of
        # contents at the very end of the PDF. Where the element opens is
        # where the author wrote it, whichever form they used.
        #
        # Closing every tag declared empty in TAGS would be the general fix,
        # but <pdf:frame static> is declared empty and swaps the story between
        # its start and its end, so it genuinely needs its children.
        c.multiBuild = True
        c.addTOC()


class pisaTagPDFFRAME(pisaTag):
    """<pdf:frame name="" static box="" />."""

    def start(self, c: pisaContext) -> None:
        deprecation("pdf:frame")
        attrs = self.attr

        name = attrs["name"]
        if name is None:
            name = f"frame{c.UID()}"

        x, y, w, h = attrs.box
        self.frame = Frame(
            x,
            y,
            w,
            h,
            id=name,
            leftPadding=0,
            rightPadding=0,
            bottomPadding=0,
            topPadding=0,
            showBoundary=attrs.border,
        )

        self.static = False
        if self.attr.static:
            self.static = True
            c.addPara()
            self.story = c.swapStory()
        else:
            c.frameList.append(self.frame)

    def end(self, c: pisaContext):
        if self.static:
            c.addPara()
            self.frame.pisaStaticStory = c.story
            # Same knob the @frame rule offers, so the two ways of declaring a
            # static frame behave alike when the content outgrows the box.
            self.frame.pisaStaticOverflowMode = getKeepInFrameMode(
                c.cssAttr.get("-pdf-keep-in-frame-mode", "shrink")
            )
            c.frameStaticList.append(self.frame)
            c.swapStory(self.story)


class pisaTagPDFTEMPLATE(pisaTag):
    """
    <pdf:template name="" static box="" >
        <pdf:frame...>
    </pdf:template>.
    """

    def start(self, c: pisaContext) -> None:
        deprecation("pdf:template")
        attrs = self.attr
        name = attrs["name"]
        c.frameList = []
        c.frameStaticList = []
        if name in c.templateList:
            log.warning(c.warning("template '%s' has already been defined", name))

    def end(self, c: pisaContext):
        attrs = self.attr
        name = attrs["name"]
        if len(c.frameList) <= 0:
            log.warning(c.warning("missing frame definitions for template"))

        pt = PmlPageTemplate(id=name, frames=c.frameList, pagesize=A4)
        pt.pisaStaticList = c.frameStaticList
        pt.pisaBackground = self.attr.background

        c.templateList[name] = pt
        c.template = None
        c.frameList = []
        c.frameStaticList = []


class pisaTagPDFLANGUAGE(pisaTag):
    """<pdf:language name=""/>."""

    def start(self, c: pisaContext) -> None:
        c.language = self.attr.name


class pisaTagPDFFONT(pisaTag):
    """<pdf:fontembed name="" src="" />."""

    def start(self, c: pisaContext) -> None:
        deprecation("pdf:font")
        c.loadFont(self.attr.name, self.attr.src, self.attr.encoding)


class pisaTagPDFBARCODE(pisaTag):
    _codeName: ClassVar[dict[str, str]] = {
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
        """Wrapper for barcode widget."""

        def __init__(self, codeName: str = "Code128", value: str = "", **kw) -> None:
            self.vertical: int = kw.get("vertical", 0)
            self.widget = createBarcodeDrawing(codeName, value=value, **kw)

        def draw(self, canvas: Canvas, xoffset: int = 0, **kw) -> None:
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

    def start(self, c: pisaContext) -> None:
        attr = self.attr
        codeName: str = attr.type or "Code128"
        codeName = pisaTagPDFBARCODE._codeName[codeName.upper().replace("-", "")]
        humanReadable: int = int(attr.humanreadable)
        vertical: int = int(attr.vertical)
        checksum: int = int(attr.checksum)
        barWidth: float = attr.barwidth or 0.01 * inch
        barHeight: float = attr.barheight or 0.5 * inch
        fontName: str = c.getFontName("OCRB10,OCR-B,OCR B,OCRB")  # or "Helvetica"
        fontSize: float = attr.fontsize or 2.75 * mm

        # Assure minimal size.
        if codeName in {"EAN13", "EAN8"}:
            barWidth = max(barWidth, 0.264 * mm)
            fontSize = max(fontSize, 2.75 * mm)
        else:  # Code39 etc.
            barWidth = max(barWidth, 0.0075 * inch)

        try:
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
        except Exception as exc:
            # Every symbology has its own rules about what it can encode, and
            # reportlab raises whatever it feels like when they are broken --
            # AttributeError for EAN, ValueError for the postal codes. A
            # mistyped barcode used to cost the whole document.
            log.warning("Cannot draw the %s barcode %r: %s", codeName, attr.value, exc)
            return

        width, height = barcode.wrap(c.frag.width, c.frag.height)
        c.force = True

        valign = attr.align or c.frag.vAlign or "baseline"
        if valign == "texttop":
            valign = "top"
        elif valign == "absmiddle":
            valign = "middle"
        elif valign in {"absbottom", "baseline"}:
            valign = "bottom"

        afrag = c.frag.clone()
        afrag.text = ""
        afrag.fontName = fontName
        afrag.cbDefn = ABag(
            kind="barcode", barcode=barcode, width=width, height=height, valign=valign
        )
        c.fragList.append(afrag)


class pisaTagCANVAS(pisaTag):
    #: Default size of the box a <canvas> reserves, in points.
    DEFAULT_WIDTH: int = 350
    DEFAULT_HEIGHT: int = 150
    #: Room left around the chart inside that box, for the axis labels and the
    #: tick marks reportlab draws outside the plot area.
    CHART_INSET: int = 20
    #: The keys that mean the JSON is placing the chart itself.
    GEOMETRY: ClassVar[set[str]] = {"x", "y", "width", "height"}

    def __init__(self, node: Element, attr: AttrContainer) -> None:
        super().__init__(node, attr)
        self.chart: BaseChart | None = None
        self.shapes = {
            "horizontalbar": HorizontalBar,
            "verticalbar": VerticalBar,
            "horizontalline": HorizontalLine,
            "pie": PieChart,
            "doughnut": DoughnutChart,
            "legendedPie": LegendedPieChart,
        }

    def start(self, c: pisaContext) -> None:
        pass

    @staticmethod
    def _length(value, default: float) -> float | None:
        """
        A CSS length in points, or None if there is no usable one.

        A percentage is a share of the frame, which is not known while the
        story is being built, so it is left to the flowable to fit itself.
        """
        if value is None:
            return None
        if isinstance(value, str) and (not value or value.endswith("%")):
            return None
        return getSize(value, default=default)

    def _box(self, c: pisaContext) -> tuple[float, float]:
        """
        The size of the box the canvas reserves.

        CSS first, the way an <img> reads it. The width and height attributes
        used to be the only thing looked at, so a stylesheet had no say in the
        size of a chart.
        """
        attributes = dict(c.node.attributes) if c.node else {}
        sizes = []
        for prop, default in (
            ("width", self.DEFAULT_WIDTH),
            ("height", self.DEFAULT_HEIGHT),
        ):
            size = self._length(getattr(c.frag, prop, None), default)
            if size is None and (declared := attributes.get(prop)):
                size = self._length(declared.nodeValue, default)
            sizes.append(size or default)
        return sizes[0], sizes[1]

    def end(self, c: pisaContext) -> None:
        data = None

        try:
            data = json.loads(c.text)
        except json.JSONDecodeError as exc:
            log.warning("Cannot read the JSON of a <canvas type=graph>: %s", exc)

        if data and c.node:
            nodetype = dict(c.node.attributes).get("type")
            canvastype = None

            if nodetype is not None:
                canvastype = nodetype.nodeValue

            if canvastype:
                c.clearFrag()

            width, height = self._box(c)

            charttype = data.get("type") if isinstance(data, dict) else None
            if charttype not in self.shapes:
                # Required by the documentation, and unchecked until now: a
                # JSON object that parses but names no chart, or names one
                # that does not exist, raised KeyError and aborted the
                # document.
                log.warning(
                    "Ignoring a <canvas type=graph> with chart type %r."
                    " Known types: %s",
                    charttype,
                    ", ".join(sorted(self.shapes)),
                )
                return

            self.chart = self.shapes[charttype]()
            draw = PmlDrawing(width, height)  # CONTAINER

            # A chart used to keep reportlab's default geometry -- 180x85 at
            # (20, 10) -- whatever size the canvas asked for, so it sat small
            # in a corner of its own box. It now fills the canvas instead,
            # but only when the JSON places nothing itself: a chart with its
            # own coordinates is laid out around them, and resizing it under
            # the author would move everything else out of place.
            if not self.GEOMETRY & set(data):
                self.chart.x = self.chart.y = self.CHART_INSET
                self.chart.width = max(width - 2 * self.CHART_INSET, 1)
                self.chart.height = max(height - 2 * self.CHART_INSET, 1)

            # No background unless one is asked for. There used to be a pale
            # rectangle pinned at (115, 25) and the size of the whole canvas,
            # so it always stuck out to the right and above the drawing and
            # painted over whatever was next to it.
            background = data.get("background")
            if background:
                draw.background = Rect(0, 0, width, height, **background)

            # REQUIRED DATA
            self.chart.set_properties(data)

            # OPTIONAL DATA
            if "title" in data:
                title = Label()
                self.chart.set_title_properties(data["title"], title)
                draw.add(title)

            if data.get("legend"):
                legend = Legend()
                self.chart.set_legend(data["legend"], legend)
                self.chart.load_data_legend(data, legend)
                draw.add(legend)

            # ADD CHART TO DRAW OBJECT
            draw.add(self.chart)
            draw.fit_contents("<canvas type=graph>")
            c.addStory(draw)
