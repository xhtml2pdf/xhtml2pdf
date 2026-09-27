"""
CSS positioning: `position: relative | absolute | fixed`, and `z-index`.

A relatively positioned block keeps its place in the flow and is only drawn
somewhere else: its flowables are laid out, paginated and split exactly as
before, and moved by top/left (or bottom/right) when they are drawn.

An absolutely positioned or fixed box leaves the flow. Its content is
collected into a box of its own (an InlineBox: shrink-to-fit, painting its
own padding, borders and background), a zero-size anchor stays where the
element was, and the page template paints the box once the page's flow has
been drawn -- in z-index order, over everything in the flow.
"""

from __future__ import annotations

import logging
from operator import itemgetter
from typing import TYPE_CHECKING, Any

from reportlab.platypus.flowables import Flowable

from xhtml2pdf.util import AUTO, CSSLength, getLengthOrAuto

if TYPE_CHECKING:
    from collections.abc import Mapping

log = logging.getLogger(__name__)

POSITIONS = ("static", "relative", "absolute", "fixed")
OFFSET_NAMES = ("top", "right", "bottom", "left")


def read_position(css_attr: Mapping[str, Any]) -> str:
    """The element's `position`, "static" for anything this does not know."""
    value = str(css_attr.get("position", "static")).strip().lower()
    if value == "sticky":
        # CSS Positioned Layout 3: in paged media a sticky box is laid out as
        # a relative one, with nothing to stick to.
        return "relative"
    return value if value in POSITIONS else "static"


def read_offsets(css_attr: Mapping[str, Any], font_size: float) -> dict[str, CSSLength]:
    """top, right, bottom and left, each a CSSLength; AUTO when not declared."""
    return {
        name: getLengthOrAuto(css_attr[name], font_size) if name in css_attr else AUTO
        for name in OFFSET_NAMES
    }


def read_z_index(css_attr: Mapping[str, Any]) -> int:
    """z-index as an int; `auto`, or anything unreadable, counts as 0."""
    try:
        return int(str(css_attr.get("z-index", "auto")).strip())
    except ValueError:
        return 0


# ~ relative ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def relative_shift(
    offsets: Mapping[str, CSSLength],
) -> tuple[CSSLength, CSSLength, int, int]:
    """
    The horizontal and vertical offsets of a relative box, CSS 2.1 9.4.3.

    Returned as (x length, y length, x sign, y sign): left wins over right and
    top over bottom, and a right or bottom offset moves the other way. The
    lengths stay unresolved because a percentage needs the containing block,
    which is only known when the box is drawn.
    """
    if offsets["left"].kind != "auto":
        dx, sx = offsets["left"], 1
    elif offsets["right"].kind != "auto":
        dx, sx = offsets["right"], -1
    else:
        dx, sx = AUTO, 0
    if offsets["top"].kind != "auto":
        dy, sy = offsets["top"], 1
    elif offsets["bottom"].kind != "auto":
        dy, sy = offsets["bottom"], -1
    else:
        dy, sy = AUTO, 0
    return dx, dy, sx, sy


class _Shifted:
    """
    The mixin a relatively positioned flowable gets as a subclass.

    A subclass of the flowable's own class rather than a wrapper around it, so
    that everything which asks what a flowable is -- the table of contents
    and the outline look for paragraphs, page numbering for tables -- still
    sees what it saw. The parts a split hands back are moved the same way.
    """

    _pisaShifts: tuple[tuple[CSSLength, CSSLength, int, int], ...] = ()

    def drawOn(self, canvas, x, y, _sW=0):
        frame = getattr(getattr(canvas, "_doctemplate", None), "frame", None)
        width = getattr(frame, "_aW", None)
        for dx, dy, sx, sy in self._pisaShifts:
            x += sx * (dx.resolve(width) or 0.0)
            # A percentage top is relative to the containing block's height,
            # which depends on its content here, so CSS 2.1 9.4.3 computes it
            # to auto: no vertical move. resolve(None) says just that.
            y -= sy * (dy.resolve(None) or 0.0)
        return super().drawOn(canvas, x, y, _sW)

    def split(self, availWidth, availHeight):
        return [
            shift_flowable(part, self._pisaShifts)
            for part in super().split(availWidth, availHeight)
        ]


_SHIFTED_CLASSES: dict[type, type] = {}


def _shifted_class(base: type) -> type:
    shifted = _SHIFTED_CLASSES.get(base)
    if shifted is None:
        shifted = _SHIFTED_CLASSES[base] = type(
            f"Shifted{base.__name__}", (_Shifted, base), {}
        )
    return shifted


def shift_flowable(flowable: Flowable, shifts) -> Flowable:
    """Move `flowable`, and whatever it splits into, by `shifts` when drawn."""
    if isinstance(flowable, _Shifted):
        # A relative box inside another: the offsets add up.
        flowable._pisaShifts = (*flowable._pisaShifts, *shifts)
        return flowable
    flowable.__class__ = _shifted_class(type(flowable))
    flowable._pisaShifts = tuple(shifts)
    return flowable


def shift_story(story: list, start: int, offsets: Mapping[str, CSSLength]) -> None:
    """Move every flowable of story[start:], a relative block's, in place."""
    dx, dy, sx, sy = relative_shift(offsets)
    if not (sx or sy):
        return
    shifts = ((dx, dy, sx, sy),)
    for flowable in story[start:]:
        shift_flowable(flowable, shifts)


# ~ absolute and fixed ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class PositionAnchor(Flowable):
    """
    Where an out-of-flow box would have been: nothing to see, a place to know.

    Zero-size, like PageNumberFlowable, and records at draw time the page it
    fell on and its point on that page -- through the canvas's matrix, since
    inside a paragraph the canvas has been moved to the paragraph's corner.
    That point is the box's static position, which CSS uses for an offset
    left auto.
    """

    width = 0.0
    height = 0.0
    last_baseline = None
    _ZEROSIZE = 1
    # The space after the flowable before it passes through to the one after
    # it, so that the margins either side still collapse into one.
    _SPACETRANSFER = True

    def __init__(self, indent: float = 0.0) -> None:
        super().__init__()
        #: The left margin a block's paragraphs would have been indented by;
        #: an anchor in the story is drawn at the frame's edge instead.
        self.indent = indent
        self.reset()

    def reset(self) -> None:
        self.page: int | None = None
        self.x = 0.0
        self.y = 0.0

    def wrap(self, availWidth, availHeight):  # noqa: PLR6301 - the Flowable API
        return 0.0, 0.0

    def drawOn(self, canvas, x, y, _sW=0):
        a, b, c, d, e, f = canvas._currentMatrix
        doc = getattr(canvas, "_doctemplate", None)
        self.page = getattr(doc, "page", None)
        self.x = a * x + c * y + e + self.indent
        self.y = b * x + d * y + f

    def draw(self) -> None:
        pass


class PageArea:
    """A containing block: left, top, width and height, in page coordinates."""

    def __init__(self, x: float, top: float, width: float, height: float) -> None:
        self.x = x
        self.top = top
        self.width = width
        self.height = height

    @property
    def bottom(self) -> float:
        return self.top - self.height

    @classmethod
    def of_template(cls, template) -> PageArea:
        """The page area: the template's first frame, less its padding."""
        frame = template.frames[0]
        left = frame._x1 + frame._leftPadding
        bottom = frame._y1 + frame._bottomPadding
        width = frame._width - frame._leftPadding - frame._rightPadding
        height = frame._height - frame._topPadding - frame._bottomPadding
        return cls(left, bottom + height, width, height)


class PositionedEntry:
    """An absolute or fixed box waiting for its page."""

    def __init__(self, box, mode, offsets, *, width, height, z, order, anchor) -> None:
        self.box = box
        self.mode = mode
        self.offsets = offsets
        self.width = width
        self.height = height
        self.z = z
        self.order = order
        self.anchor = anchor

    def _length(self, name: str, basis: float) -> float | None:
        length = self.offsets[name]
        return None if length.kind == "auto" else (length.resolve(basis) or 0.0)

    def place(self, page: int, page_area: PageArea, initial: PageArea | None):
        """The containing block and top offset for `page`, or None if not on it."""
        if self.mode == "fixed":
            return page_area, None
        block = initial or page_area
        top = self._length("top", block.height)
        bottom = self._length("bottom", block.height)
        if top is None and bottom is None:
            # The static position: wherever the anchor fell.
            return (block, None) if self.anchor.page == page else None
        if top is not None and block.height > 0:
            # The initial containing block is the first page's area, and what
            # lies past it goes on in the pages after, as the flow does.
            target, top = divmod(top, block.height)
            return (block, top) if page == 1 + int(target) else None
        return (block, None) if page == 1 else None

    def paint(self, canvas, block: PageArea, top_override: float | None) -> None:
        from xhtml2pdf.builders.flex import LARGE

        box = self.box
        style = box.style
        m_left, m_right, m_top, m_bottom = box.margins
        left = self._length("left", block.width)
        right = self._length("right", block.width)
        top = (
            top_override
            if top_override is not None
            else self._length("top", block.height)
        )
        bottom = self._length("bottom", block.height)

        # CSS 2.1 10.3.7 and 10.6.4: with both offsets and no size, the box
        # fills what is left between them.
        box.css_width = self.width
        box.css_height = self.height
        if self.width.kind == "auto" and left is not None and right is not None:
            content = block.width - left - right - m_left - m_right - style.horizontal
            box.css_width = CSSLength("length", max(content, 1.0))
        if self.height.kind == "auto" and top is not None and bottom is not None:
            content = block.height - top - bottom - m_top - m_bottom - style.vertical
            box.css_height = CSSLength("length", max(content, 1.0))
        box._cache_key = None

        if box.css_width.kind != "auto":
            avail = block.width
        elif left is None and right is None and self.anchor and self.anchor.page:
            avail = block.x + block.width - self.anchor.x
        else:
            avail = block.width - (left or 0.0) - (right or 0.0)
        width, height = box.wrapOn(canvas, max(avail, 1.0), LARGE)

        if left is not None:
            x = block.x + left
        elif right is not None:
            x = block.x + block.width - right - width
        else:
            x = self.anchor.x if self.anchor and self.anchor.page else block.x
        if top is not None:
            y_top = block.top - top
        elif bottom is not None:
            y_top = block.bottom + bottom + height
        else:
            y_top = self.anchor.y if self.anchor and self.anchor.page else block.top
        box.drawOn(canvas, x, y_top - height)


class PositionedBoxData:
    """
    What pisaLoop sets aside while it collects an absolute or fixed box.

    InlineBoxData's work -- the pending paragraph saved, the content collected
    into a story of its own, the box's own padding, borders and background
    taken off the frag -- with a different ending: the box goes to the
    document's list of positioned boxes, and only an anchor stays behind.
    """

    def __init__(
        self, c, frag, css_attr, mode, offsets, *, block_level, indent
    ) -> None:
        from xhtml2pdf.builders.flex import InlineBoxData

        self.mode = mode
        self.offsets = offsets
        self.z = read_z_index(css_attr)
        self.block_level = block_level
        self.indent = indent
        self._inner = InlineBoxData.__new__(InlineBoxData)
        InlineBoxData.__init__(self._inner, c, frag, css_attr)

    def close(self, c) -> None:
        from xhtml2pdf.builders.flex import InlineBox, inline_box_frag

        inner = self._inner
        c.addPara()
        content = c.swapStory(inner._outer_story)
        for name, value in inner._saved.items():
            setattr(c, name, value)
        anchor = None
        if self.mode == "absolute":
            anchor = PositionAnchor(self.indent if self.block_level else 0.0)
            if self.block_level:
                c.addStory(anchor)
            else:
                c.fragList.append(inline_box_frag(c.frag, anchor, "top"))
        if not content:
            return
        left, right, top, bottom = inner.margins
        box = InlineBox(
            content,
            inner.style,
            width=inner.width,
            height=inner.height,
            margin_left=left,
            margin_right=right,
            margin_top=top,
            margin_bottom=bottom,
        )
        c.positioned.append(
            PositionedEntry(
                box,
                self.mode,
                self.offsets,
                width=inner.width,
                height=inner.height,
                z=self.z,
                order=len(c.positioned),
                anchor=anchor,
            )
        )


def reset_positioned(doc) -> None:
    """Forget where the anchors fell: a multiBuild pass lays the story out anew."""
    for entry in getattr(doc, "pisaPositioned", ()):
        if entry.anchor is not None:
            entry.anchor.reset()
    doc.pisaInitialBlock = None


def paint_positioned(canvas, doc, template) -> None:
    """Paint the positioned boxes that belong on this page, in z-index order."""
    entries = getattr(doc, "pisaPositioned", None)
    if not entries:
        return
    page = doc.page
    area = PageArea.of_template(template)
    if page == 1 or getattr(doc, "pisaInitialBlock", None) is None:
        doc.pisaInitialBlock = area
    placed = []
    for entry in entries:
        placement = entry.place(page, area, doc.pisaInitialBlock)
        if placement is not None:
            placed.append((entry.z, entry.order, entry, placement))
    placed.sort(key=itemgetter(0, 1))
    for _z, _order, entry, (block, top) in placed:
        entry.paint(canvas, block, top)
