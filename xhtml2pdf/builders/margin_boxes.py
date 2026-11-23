"""
The page-margin boxes of CSS Paged Media 3: @top-center and its fifteen kin.

An @page rule may hold @top-left { content: "..." } and the like. Each box
sits in the page's margin and draws its ``content`` -- strings,
``counter(page)``, ``counter(pages)`` -- in its own font, colour, alignment,
background, border, padding and opacity. The boxes are styled once, when the
document has been read, and drawn on every page the template is used for,
after the page's flow.

The sizes are simpler than the specification's. The boxes of a side share it
by which of them have content: a centre box with a neighbour may take the
middle third, and its neighbours what is left on either side; alone, it may
take the whole side, as may a lone side box; two side boxes share it in
halves. Across the top and the bottom a box is then as wide as its content
in that room, against its end of the side, or centred, as Chrome draws them;
down the left and the right it fills its share.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle

from xhtml2pdf.builders.opacity import paint_with_opacity
from xhtml2pdf.builders.strings import string_on_page
from xhtml2pdf.w3c.generated_content import (
    AttrItem,
    CounterItem,
    StringItem,
    format_counter,
    parse_content,
)

if TYPE_CHECKING:
    from xhtml2pdf.builders.flex import BoxStyle

log = logging.getLogger(__name__)

#: The three boxes of each side, in the order they run along it.
_SIDES: dict[str, tuple[str, str, str]] = {
    "top": ("top-left", "top-center", "top-right"),
    "bottom": ("bottom-left", "bottom-center", "bottom-right"),
    "left": ("left-top", "left-middle", "left-bottom"),
    "right": ("right-top", "right-middle", "right-bottom"),
}

#: CSS Paged Media 3, 4.2.4: text-align and vertical-align of each box when
#: its rule does not say.
_DEFAULT_ALIGN: dict[str, tuple[int, str]] = {
    "top-left-corner": (TA_RIGHT, "middle"),
    "top-left": (TA_LEFT, "middle"),
    "top-center": (TA_CENTER, "middle"),
    "top-right": (TA_RIGHT, "middle"),
    "top-right-corner": (TA_LEFT, "middle"),
    "bottom-left-corner": (TA_RIGHT, "middle"),
    "bottom-left": (TA_LEFT, "middle"),
    "bottom-center": (TA_CENTER, "middle"),
    "bottom-right": (TA_RIGHT, "middle"),
    "bottom-right-corner": (TA_LEFT, "middle"),
    "left-top": (TA_CENTER, "top"),
    "left-middle": (TA_CENTER, "middle"),
    "left-bottom": (TA_CENTER, "bottom"),
    "right-top": (TA_CENTER, "top"),
    "right-middle": (TA_CENTER, "middle"),
    "right-bottom": (TA_CENTER, "bottom"),
}


@dataclass
class MarginBox:
    """One styled page-margin box, ready to be drawn on any page."""

    name: str
    items: list
    style: ParagraphStyle
    frag: Any
    box: BoxStyle
    valign: str
    opacity: float = 1.0

    def text(self, doc) -> str:
        """The box's content on the page `doc` is drawing."""
        parts = []
        for item in self.items:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, CounterItem) and item.name == "page":
                parts.append(format_counter(doc.pageLabel(doc.page), item.style))
            elif isinstance(item, CounterItem) and item.name == "pages":
                count = getattr(doc, "_page_count", 0) or doc.page
                parts.append(format_counter(count, item.style))
            elif isinstance(item, StringItem):
                parts.append(string_on_page(doc, item.name, item.policy))
            elif isinstance(item, AttrItem | CounterItem):
                # A margin box has no element for attr() and no counters
                # but the page's.
                continue
        return "".join(parts)


def uses_page_count(boxes: list[MarginBox]) -> bool:
    return any(
        isinstance(item, CounterItem) and item.name == "pages"
        for box in boxes
        for item in box.items
    )


def build_margin_boxes(c, declared: dict[str, dict]) -> list[MarginBox]:
    """
    Style the boxes an @page declared, through the same cascade code as an
    element: CSS2Frag over a fresh frag, as pisaContext.addTOC does.
    """
    from xhtml2pdf import parser
    from xhtml2pdf.builders.flex import BoxStyle
    from xhtml2pdf.context import getParaFrag
    from xhtml2pdf.properties import LOOP_GROUPS, CSSAttrs, apply_uniform_groups

    boxes = []
    saved = c.frag, c.cssAttr
    try:
        for name, data in declared.items():
            items = parse_content(data.get("content", "none"))
            if items is None:
                continue
            frag = getParaFrag(ParagraphStyle(f"margin-box-{name}"))
            frag.fontSize = getattr(c, "rootFontSize", None) or frag.fontSize
            c.frag = frag
            c.cssAttr = CSSAttrs(data)
            parser.CSS2Frag(
                c,
                {
                    "margin-top": 0,
                    "margin-bottom": 0,
                    "margin-left": 0,
                    "margin-right": 0,
                },
                isBlock=True,
            )
            apply_uniform_groups(frag, c.cssAttr, LOOP_GROUPS)
            box = BoxStyle(frag, leftIndent=0.0, rightIndent=0.0)
            style = c.toParagraphStyle(frag)
            # The family and weight made into the font's name, as addFrag does.
            frag.fontName = frag.bulletFontName = style.fontName
            # The box draws its own background and border, round the whole
            # box, not round the text.
            style.backColor = None
            for side in ("Top", "Bottom", "Left", "Right"):
                setattr(style, f"border{side}Width", 0)
                setattr(style, f"padding{side}", 0)
            style.leftIndent = style.rightIndent = 0
            style.spaceBefore = style.spaceAfter = 0
            align, valign = _DEFAULT_ALIGN[name]
            if "text-align" not in data:
                style.alignment = frag.alignment = align
            declared_valign = str(data.get("vertical-align", "")).strip().lower()
            if declared_valign in {"top", "middle", "bottom"}:
                valign = declared_valign
            boxes.append(
                MarginBox(
                    name=name,
                    items=items,
                    style=style,
                    frag=frag,
                    box=box,
                    valign=valign,
                    opacity=getattr(frag, "opacity", 1.0),
                )
            )
    finally:
        c.frag, c.cssAttr = saved
    return boxes


def prepare_margin_boxes(c) -> None:
    """Style the margin boxes of every page template, once the document is read."""
    for template in c.templateList.values():
        declared = getattr(template, "pisaMarginBoxes", None)
        if not declared:
            continue
        template.pisaMarginBoxes = build_margin_boxes(c, declared)
        if uses_page_count(template.pisaMarginBoxes):
            # The total is known after a first pass, as for <pdf:pagecount>.
            c.addPageCount()


def _share(start: float, length: float, present: tuple[bool, bool, bool]):
    """(offset, length) along a side for each of its three boxes, or None."""
    first, centre, last = present
    if centre:
        width = length / 3 if (first or last) else length
        offset = start + (length - width) / 2
        return (
            (start, offset - start) if first else None,
            (offset, width),
            (offset + width, start + length - offset - width) if last else None,
        )
    if first and last:
        return (start, length / 2), None, (start + length / 2, length / 2)
    return ((start, length) if first else None, None, (start, length) if last else None)


def margin_box_rects(pagesize, margins, names) -> dict[str, tuple]:
    """
    (x, y, width, height) of each box in `names`, from the bottom left of the
    page, for a page of `pagesize` with `margins` (top, right, bottom, left).
    """
    width, height = pagesize
    top, right, bottom, left = margins
    rects: dict[str, tuple] = {
        "top-left-corner": (0, height - top, left, top),
        "top-right-corner": (width - right, height - top, right, top),
        "bottom-left-corner": (0, 0, left, bottom),
        "bottom-right-corner": (width - right, 0, right, bottom),
    }
    across = width - left - right
    down = height - top - bottom
    for side, boxes in _SIDES.items():
        present = (boxes[0] in names, boxes[1] in names, boxes[2] in names)
        if not any(present):
            continue
        if side in {"top", "bottom"}:
            spans = _share(left, across, present)
            y, h = (height - top, top) if side == "top" else (0, bottom)
            for name, span in zip(boxes, spans, strict=True):
                if span is not None:
                    rects[name] = (span[0], y, span[1], h)
        else:
            spans = _share(0, down, present)
            x, w = (0, left) if side == "left" else (width - right, right)
            for name, span in zip(boxes, spans, strict=True):
                if span is not None:
                    offset, length = span
                    rects[name] = (x, height - top - offset - length, w, length)
    return {name: rect for name, rect in rects.items() if name in names}


def paint_margin_boxes(canvas, doc, template) -> None:
    """Draw the template's margin boxes on the page being finished."""
    boxes = getattr(template, "pisaMarginBoxes", None)
    if not boxes or not isinstance(boxes, list):
        return
    rects = margin_box_rects(
        template.pagesize, template.pisaPageMargins, {box.name for box in boxes}
    )
    for box in boxes:
        x, y, w, h = rects[box.name]
        if w <= 0 or h <= 0:
            continue
        paint_with_opacity(
            canvas, box.opacity, partial(_paint, canvas, doc, box, (x, y, w, h))
        )


def _paint(canvas, doc, box: MarginBox, rect) -> None:
    from xhtml2pdf.util import drawBoxBackground, drawBoxBorders, stringWidth
    from xhtml2pdf.xhtml2pdf_reportlab import PmlParagraph

    x, y, w, h = rect
    style = box.box
    text = box.text(doc)
    if box.name.split("-")[0] in {"top", "bottom"} and not box.name.endswith("corner"):
        # A box across the top or the bottom is as wide as its content, in
        # the room its slot gives it, against its end of the side.
        natural = (
            stringWidth(text, box.frag.fontName, box.frag.fontSize)
            + style.horizontal
            + 0.01
        )
        if natural < w:
            if box.name.endswith("-right"):
                x += w - natural
            elif box.name.endswith("-center"):
                x += (w - natural) / 2
            w = natural
    canvas.saveState()
    drawBoxBackground(canvas, x, y, w, h, style)
    drawBoxBorders(canvas, x, y, w, h, style)
    if text:
        inner_w = max(w - style.horizontal, 1.0)
        inner_h = h - style.vertical
        # Built as addPara builds a document's paragraphs, so it is laid out
        # and aligned the same way.
        para = PmlParagraph(
            text, box.style, frags=[box.frag.clone(text=text), box.frag.clone(text="")]
        )
        para.autoLeading = "max"
        _pw, ph = para.wrap(inner_w, max(inner_h, 1.0))
        bottom = y + style.paddingBottom + style.border("Bottom")
        if box.valign == "top":
            py = bottom + inner_h - ph
        elif box.valign == "bottom":
            py = bottom
        else:
            py = bottom + (inner_h - ph) / 2
        para.drawOn(canvas, x + style.content_left, py)
    canvas.restoreState()
