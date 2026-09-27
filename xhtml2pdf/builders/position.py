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
from operator import attrgetter
from typing import TYPE_CHECKING, Any

from reportlab.platypus.flowables import Flowable

from xhtml2pdf.util import AUTO, CSSLength, getLengthOrAuto

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xhtml2pdf.builders.flex import InlineBox

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
    left auto. A relative block's two anchors, at its start and end, are
    how its box is found again, to place what it contains.
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
        #: The frame's right edge and bottom, and the space after the
        #: flowable before the anchor -- what a margin collapsed into.
        self.frame_right = 0.0
        self.frame_bottom = 0.0
        self.space_before = 0.0

    def wrap(self, availWidth, availHeight):  # noqa: PLR6301 - the Flowable API
        return 0.0, 0.0

    def drawOn(self, canvas, x, y, _sW=0):
        a, b, c, d, e, f = canvas._currentMatrix
        doc = getattr(canvas, "_doctemplate", None)
        self.page = getattr(doc, "page", None)
        self.x = a * x + c * y + e + self.indent
        self.y = b * x + d * y + f
        frame = getattr(self, "_frame", None)
        if frame is not None:
            # The frame's right edge measured from the x the anchor was given,
            # so that a relative block's offset moves that edge too.
            room = frame._x1 + frame._width - frame._rightPadding - frame._x
            room -= frame._leftExtraIndent
            self.frame_right = self.x - self.indent + a * room
            self.frame_bottom = d * (frame._y1 + frame._bottomPadding) + f
            self.space_before = getattr(frame, "_prevASpace", 0.0) or 0.0

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


class RelativeContainer:
    """
    A relative block, as the containing block of the boxes inside it.

    Its box is not a flowable -- its paragraphs are -- so it is found again
    from two anchors placed around them: the start anchor gives its left,
    top and the frame's right edge, the end anchor its bottom when both fell
    on the same page. Its padding box is that, less its borders.
    """

    def __init__(self, *, margin_top, right_indent, borders, key) -> None:
        self.start = PositionAnchor()
        self.end = PositionAnchor()
        self.margin_top = margin_top
        self.right_indent = right_indent
        self.borders = borders
        #: Where in the painting order the boxes inside it belong.
        self.key = key

    def anchors(self) -> tuple[PositionAnchor, PositionAnchor]:
        return self.start, self.end

    def padding_box(self, page: int) -> PageArea | None:
        start, end = self.start, self.end
        if start.page != page:
            return None
        border_left, border_right, border_top, border_bottom = self.borders
        # The anchor sits above the block's own top margin, less whatever
        # of it collapsed into the space after the block before.
        top = start.y - max(self.margin_top - start.space_before, 0.0)
        bottom = end.y + end.space_before if end.page == page else start.frame_bottom
        left = start.x + border_left
        right = start.frame_right - self.right_indent - border_right
        top -= border_top
        bottom += border_bottom
        return PageArea(left, top, max(right - left, 0.0), max(top - bottom, 0.0))


class PositionedEntry:
    """An absolute or fixed box waiting for its page."""

    def __init__(self, mode, offsets, *, z, order, container) -> None:
        self.box: InlineBox | None = None
        self.mode = mode
        self.offsets = offsets
        self.width = AUTO
        self.height = AUTO
        self.z = z
        self.order = order
        self.anchor: PositionAnchor | None = None
        #: The nearest positioned ancestor: a RelativeContainer, another
        #: PositionedEntry, or None for the initial containing block.
        self.container = container
        #: Painting order. A box inside another comes right after it,
        #: whatever its own z-index: the ancestor's is the one that counts
        #: against everything outside it.
        prefix = container.key if container is not None else ()
        self.key = (*prefix, z, order)
        #: Where the box was painted last: the page, and its padding box.
        self.painted_page: int | None = None
        self.painted_box: PageArea | None = None

    def padding_box(self, page: int) -> PageArea | None:
        return self.painted_box if self.painted_page == page else None

    def _length(self, name: str, basis: float) -> float | None:
        length = self.offsets[name]
        return None if length.kind == "auto" else (length.resolve(basis) or 0.0)

    def place(self, page: int, page_area: PageArea, initial: PageArea | None):
        """The containing block and top offset for `page`, or None if not on it."""
        if self.box is None:
            return None
        if self.mode == "fixed" and self.container is None:
            return page_area, None
        if self.container is not None:
            block = self.container.padding_box(page)
            if block is None:
                return None
            if (
                self.offsets["top"].kind == "auto"
                and self.offsets["bottom"].kind == "auto"
            ):
                return (
                    (block, None) if self.anchor and self.anchor.page == page else None
                )
            return block, None
        block = initial or page_area
        top = self._length("top", block.height)
        bottom = self._length("bottom", block.height)
        if top is None and bottom is None:
            # The static position: wherever the anchor fell.
            return (block, None) if self.anchor and self.anchor.page == page else None
        if top is not None and block.height > 0:
            # The initial containing block is the first page's area, and what
            # lies past it goes on in the pages after, as the flow does.
            target, top = divmod(top, block.height)
            return (block, top) if page == 1 + int(target) else None
        return (block, None) if page == 1 else None

    def paint(
        self, canvas, page: int, block: PageArea, top_override: float | None
    ) -> None:
        from xhtml2pdf.builders.flex import LARGE

        box = self.box
        assert box is not None  # place() hands out no entry without one
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
        anchor = (
            self.anchor
            if self.anchor is not None and self.anchor.page == page
            else None
        )

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
        elif left is None and right is None and anchor is not None:
            avail = block.x + block.width - anchor.x
        else:
            avail = block.width - (left or 0.0) - (right or 0.0)
        width, height = box.wrapOn(canvas, max(avail, 1.0), LARGE)

        if left is not None:
            x = block.x + left
        elif right is not None:
            x = block.x + block.width - right - width
        else:
            x = anchor.x if anchor is not None else block.x
        if top is not None:
            y_top = block.top - top
        elif bottom is not None:
            y_top = block.bottom + bottom + height
        else:
            y_top = anchor.y if anchor is not None else block.top
        y = y_top - height
        box.drawOn(canvas, x, y)
        # Its padding box, for the boxes positioned inside it.
        self.painted_page = page
        self.painted_box = PageArea(
            x + m_left + style.border("Left"),
            y + height - m_top - style.border("Top"),
            box._box_width - style.border("Left") - style.border("Right"),
            box._box_height - style.border("Top") - style.border("Bottom"),
        )


class PositionedBoxData:
    """
    What pisaLoop sets aside while it collects an absolute or fixed box.

    InlineBoxData's work -- the pending paragraph saved, the content collected
    into a story of its own, the box's own padding, borders and background
    taken off the frag -- with a different ending: the box goes to the
    document's list of positioned boxes, and only an anchor stays behind.
    The entry is made when the element opens, so that it comes before the
    boxes inside it in the list, and those can find it as their container.
    """

    def __init__(
        self, c, frag, css_attr, mode, offsets, *, block_level, indent
    ) -> None:
        from xhtml2pdf.builders.flex import InlineBoxData

        self.block_level = block_level
        self.indent = indent
        container = c.positionStack[-1] if c.positionStack else None
        self.entry = PositionedEntry(
            mode,
            offsets,
            z=read_z_index(css_attr),
            order=len(c.positioned),
            container=container,
        )
        c.positioned.append(self.entry)
        self._inner = InlineBoxData.__new__(InlineBoxData)
        InlineBoxData.__init__(self._inner, c, frag, css_attr)
        c.positionStack.append(self.entry)

    def close(self, c) -> None:
        from xhtml2pdf.builders.flex import InlineBox, inline_box_frag

        c.positionStack.pop()
        inner = self._inner
        entry = self.entry
        c.addPara()
        content = c.swapStory(inner._outer_story)
        for name, value in inner._saved.items():
            setattr(c, name, value)
        if entry.mode == "absolute":
            entry.anchor = PositionAnchor(self.indent if self.block_level else 0.0)
            if self.block_level:
                c.addStory(entry.anchor)
            else:
                c.fragList.append(inline_box_frag(c.frag, entry.anchor, "top"))
        offsets = entry.offsets
        sized = (
            inner.width.kind != "auto"
            or inner.height.kind != "auto"
            or (offsets["left"].kind != "auto" and offsets["right"].kind != "auto")
            or (offsets["top"].kind != "auto" and offsets["bottom"].kind != "auto")
        )
        if not content and not sized:
            # Nothing inside and nothing to give it a size: an empty box.
            return
        left, right, top, bottom = inner.margins
        entry.width = inner.width
        entry.height = inner.height
        entry.box = InlineBox(
            content,
            inner.style,
            width=inner.width,
            height=inner.height,
            margin_left=left,
            margin_right=right,
            margin_top=top,
            margin_bottom=bottom,
        )


def open_relative_container(c, frag, css_attr, right_indent) -> RelativeContainer:
    """Make a relative block the containing block of what is inside it."""
    from xhtml2pdf.builders.flex import BoxStyle

    style = BoxStyle(frag)
    margin_top = (
        getLengthOrAuto(css_attr["margin-top"], frag.fontSize).resolve(None)
        if "margin-top" in css_attr
        else 0.0
    )
    enclosing = next(
        (
            item
            for item in reversed(c.positionStack)
            if isinstance(item, PositionedEntry)
        ),
        None,
    )
    container = RelativeContainer(
        margin_top=margin_top or 0.0,
        right_indent=right_indent,
        borders=tuple(
            style.border(side) for side in ("Left", "Right", "Top", "Bottom")
        ),
        key=enclosing.key if enclosing is not None else (),
    )
    c.positionStack.append(container)
    return container


def close_relative_container(
    c, container: RelativeContainer, start: int, indent: float
) -> None:
    """Put the container's two anchors around its flowables, story[start:]."""
    c.positionStack.pop()
    container.start.indent = indent
    # The block's top border edge is below the top margin of what it starts
    # with: its own margin went there, and a child's collapses through it.
    if start < len(c.story):
        container.margin_top = c.story[start].getSpaceBefore() or 0.0
    c.story.insert(start, container.start)
    c.story.append(container.end)


def reset_positioned(doc) -> None:
    """Forget where the anchors fell: a multiBuild pass lays the story out anew."""
    for entry in getattr(doc, "pisaPositioned", ()):
        if entry.anchor is not None:
            entry.anchor.reset()
        entry.painted_page = None
        container = entry.container
        if isinstance(container, RelativeContainer):
            for anchor in container.anchors():
                anchor.reset()
    doc.pisaInitialBlock = None


def _under_flow_name(page: int) -> str:
    return f"pisaUnderFlow{page}"


def _is_under_flow(entry: PositionedEntry) -> bool:
    """A negative z-index, its own or its outermost positioned ancestor's."""
    return entry.key[0] < 0


def reserve_under_flow(canvas, doc) -> None:
    """
    Put a form under the page's flow for the boxes with a negative z-index.

    They belong under the flow (CSS 2.1 Appendix E), but which of them are
    on a page is only known once the flow has been drawn: a box at its
    static position is wherever its anchor fell. The page starts by drawing
    a form XObject that does not exist yet, and paint_positioned defines it
    at the end of the page -- reportlab resolves a form by name when the
    document is saved, the way "page N of M" recipes use it.
    """
    entries = getattr(doc, "pisaPositioned", None)
    if entries and any(_is_under_flow(entry) for entry in entries):
        canvas.doForm(_under_flow_name(doc.page))


def paint_positioned(canvas, doc, template) -> None:
    """Paint the positioned boxes that belong on this page, in painting order."""
    entries = getattr(doc, "pisaPositioned", None)
    if not entries:
        return
    page = doc.page
    area = PageArea.of_template(template)
    if page == 1 or getattr(doc, "pisaInitialBlock", None) is None:
        doc.pisaInitialBlock = area
    # In painting order, which puts every box after the one it is inside:
    # its containing block is known by the time it is placed.
    ordered = sorted(entries, key=attrgetter("key"))
    under = [entry for entry in ordered if _is_under_flow(entry)]
    over = [entry for entry in ordered if not _is_under_flow(entry)]
    if under:
        # Defined on every page reserve_under_flow referred to it on, empty
        # or not: a form that is drawn and never defined breaks the file.
        canvas.beginForm(_under_flow_name(page))
        _paint_entries(canvas, page, area, doc.pisaInitialBlock, under)
        canvas.endForm()
    _paint_entries(canvas, page, area, doc.pisaInitialBlock, over)


def _paint_entries(canvas, page, area, initial, entries) -> None:
    for entry in entries:
        placement = entry.place(page, area, initial)
        if placement is not None:
            block, top = placement
            entry.paint(canvas, page, block, top)
