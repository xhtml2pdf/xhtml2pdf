"""
A block with a box of its own, drawn once around everything it holds (#627).

A block's padding, borders and background used to be drawn by each of its
paragraphs, around itself, and copied onto everything else it held: a
<div> with a border round a table gave the table, its rows and its cells
the div's border and padding, and the text before and after the table a
box each. Platypus stacks flowables and nothing else, so a box around
several of them has to be one flowable that stacks them inside itself:
BlockBox, the same shape as a flex container with one column.

Only a block whose box holds other blocks gets one. A block of text alone
is one paragraph, which has always drawn its own box and still does.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from reportlab.lib.abag import ABag
from reportlab.platypus.doctemplate import IndexingFlowable
from reportlab.platypus.flowables import Flowable, KeepTogether

from xhtml2pdf.builders.flex import (
    LARGE,
    BoxStyle,
    StackEntry,
    clear_box,
    content_widths,
    cut_style,
    draw_stack,
    split_stack,
)
from xhtml2pdf.builders.position import PositionAnchor
from xhtml2pdf.util import drawBoxBackground, drawBoxBorders, getSize, toList
from xhtml2pdf.xhtml2pdf_reportlab import (
    PmlKeepInFrame,
    PmlMaxHeightMixIn,
    layout_moment,
    opened_up,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_FUZZ = 1e-6
_SIDES = ("Left", "Right", "Top", "Bottom")


@dataclass(frozen=True)
class BlockWidth:
    """
    A block's CSS width, and the horizontal margins that place it.

    The width is the content box's, a length or a share of the containing
    block. What the box leaves of the line goes to an auto margin -- half
    to each when both are -- and otherwise to the right of the box.
    """

    length: float | None
    percent: float | None
    own_left: float
    own_right: float
    auto_left: bool
    auto_right: bool

    def indents(
        self, avail: float, left: float, right: float, horizontal: float
    ) -> tuple[float, float]:
        """The left and right indents that give the box its width in `avail`."""
        containing = avail - (left - self.own_left) - (right - self.own_right)
        if self.length is not None:
            content = self.length
        else:
            content = containing * (self.percent or 0.0) / 100.0
        room = avail - left - right
        extra = room - (content + horizontal)
        if extra <= 0:
            return left, right
        if self.auto_left and self.auto_right:
            return left + extra / 2, right + extra / 2
        if self.auto_left:
            return left + extra, right
        return left, right + extra


def _stack(
    content: Sequence[Flowable],
    width: float,
    canv,
    avail_height: float,
    *,
    top_margin: bool,
    bottom_margin: bool,
) -> tuple[list[StackEntry], float]:
    """
    Wrap each flowable at `width` and stack them: the entries and the height.

    builders.flex.stack_flowables, with two differences a block needs. A
    flowable with no height is kept, in its place, because an anchor or a
    bookmark is drawn to record where it fell. And the first margin and the
    last are kept inside the box when it has padding or a border on that
    side; without one they collapsed through it, into the box's own margin.
    """
    entries: list[StackEntry] = []
    height = 0.0
    previous_after = 0.0
    at_top = True
    for flowable in content:
        if hasattr(flowable, "frameAction"):
            continue
        w, h = flowable.wrapOn(canv, width, avail_height)
        if h <= _FUZZ:
            entries.append(StackEntry(flowable, w, 0.0, 0.0, 0.0))
            continue
        before = flowable.getSpaceBefore()
        if getattr(flowable, "_SPACETRANSFER", False):
            before = previous_after
        before = max(before - previous_after, 0.0)
        if at_top and not top_margin:
            before = 0.0
        at_top = False
        after = flowable.getSpaceAfter()
        if getattr(flowable, "_SPACETRANSFER", False):
            after = previous_after
        entries.append(StackEntry(flowable, w, h, before, after))
        height += before + h + after
        previous_after = after
    if not bottom_margin:
        height -= previous_after
    return entries, height


class BlockBox(Flowable, PmlMaxHeightMixIn):
    """
    A block's box: background, padding and borders around a column of
    flowables, laid out in the box's content area.

    Cut at a page edge, each part has its own edges but the cut one
    (box-decoration-break: slice), as a split paragraph's box has.
    """

    _SPACETRANSFER = False

    def __init__(
        self,
        content: Sequence[Flowable],
        style: BoxStyle,
        *,
        keep_together=False,
        min_height: float = 0.0,
        box_width: BlockWidth | None = None,
    ) -> None:
        super().__init__()
        self.content = list(content)
        self.style = style
        #: The CSS height: the content area is at least this tall.
        self.min_height = min_height
        #: The CSS width, if the block declares one.
        self.box_width = box_width
        #: The indents the box is drawn with, its width's once wrapped.
        self._left = style.leftIndent
        self._right = style.rightIndent
        #: page-break-inside: avoid on a block inside this one. Moved to the
        #: next page whole when it does not fit, if a page can hold it.
        self.keep_together = keep_together
        self.keepWithNext = False
        self._key: tuple[float, int, int] | None = None
        self._entries: list[StackEntry] = []
        self._inner = 0.0
        self._stacked = 0.0

    def identity(self, maxLen=None) -> str:
        return f"<BlockBox at {id(self):#x} with {len(self.content)} flowables>"

    def getSpaceBefore(self) -> float:
        return self.style.spaceBefore

    def getSpaceAfter(self) -> float:
        return self.style.spaceAfter

    def content_widths(self, canv) -> tuple[float, float]:
        """(min-content, max-content), its box and margins included."""
        low, high = content_widths(self.content, canv)
        style = self.style
        extra = style.horizontal + style.leftIndent + style.rightIndent
        return low + extra, high + extra

    def minWidth(self) -> float:
        return self.content_widths(getattr(self, "canv", None))[0]

    @property
    def _margins_inside(self) -> tuple[bool, bool]:
        style = self.style
        top = style.paddingTop + style.border("Top")
        bottom = style.paddingBottom + style.border("Bottom")
        return top > _FUZZ, bottom > _FUZZ

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        availHeight = self.setMaxHeight(availHeight)
        style = self.style
        key = (round(availWidth, 2), *layout_moment(getattr(self, "canv", None)))
        if self._key != key:
            # Laid out once per width and never at a trial one: a table
            # turns its percentage columns into points as it is wrapped.
            self._left, self._right = style.leftIndent, style.rightIndent
            if self.box_width is not None:
                self._left, self._right = self.box_width.indents(
                    availWidth, self._left, self._right, style.horizontal
                )
            inner = availWidth - self._left - self._right
            self._inner = max(inner - style.horizontal, 1.0)
            top, bottom = self._margins_inside
            self._entries, self._stacked = _stack(
                self.content,
                self._inner,
                getattr(self, "canv", None),
                (self.getMaxHeight() or LARGE) - style.vertical,
                top_margin=top,
                bottom_margin=bottom,
            )
            self._key = key
        self.width = availWidth
        self.height = max(self._stacked, self.min_height) + style.vertical
        return self.width, self.height

    def split(self, availWidth: float, availHeight: float) -> list:
        self.wrap(availWidth, availHeight)
        if self.height <= availHeight + _FUZZ:
            return [self]
        style = self.style
        room = self.getMaxHeight() or availHeight
        if self.keep_together and self.height <= room + _FUZZ:
            return []

        at = availHeight - style.content_top
        if at > _FUZZ:
            head, tail = split_stack(
                self._entries, at, self._inner, getattr(self, "canv", None)
            )
            if any(not getattr(f, "_ZEROSIZE", False) for f in head):
                # Nothing of the box's bottom is drawn at the cut, and
                # nothing of its top where it goes on.
                return [
                    BlockBox(
                        head, cut_style(style, "Bottom"), box_width=self.box_width
                    ),
                    self._part(tail, cut_style(style, "Top")),
                ]
        # A refused split may have dropped what a paragraph had broken; the
        # next wrap lays the content out afresh.
        self._key = None

        # Only a first flowable that no page can hold is shrunk to fit:
        # anything else waits for the next frame, where it gets a whole one.
        first = next((e for e in self._entries if e.height > _FUZZ), None)
        needed = (first.height if first is not None else 0.0) + style.vertical
        if needed > room + _FUZZ:
            return [
                PmlKeepInFrame(
                    maxWidth=availWidth,
                    maxHeight=availHeight,
                    mode="shrink",
                    content=[
                        _UnsplittableBlockBox(
                            self.content, self.style, box_width=self.box_width
                        )
                    ],
                )
            ]
        return []

    def _part(self, content: list, style: BoxStyle) -> BlockBox:
        part = BlockBox(content, style, box_width=self.box_width)
        part.keepWithNext = self.keepWithNext
        return part

    def draw(self) -> None:
        if self._key is None:
            self.wrap(self.width, LARGE)
        canv = self.canv
        style = self.style
        # drawOn has moved the origin to the box's bottom left.
        x = self._left
        width = self.width - self._left - self._right
        drawBoxBackground(canv, x, 0, width, self.height, style)
        left = x + style.content_left
        top = self.height - style.content_top
        anchors = self._frame_anchors(left)
        try:
            draw_stack(canv, self._entries, left, top, self._inner)
        finally:
            for anchor in anchors:
                del anchor._frame
        drawBoxBorders(canv, x, 0, width, self.height, style)

    def _frame_anchors(self, left: float) -> list[PositionAnchor]:
        """
        Give the anchors in the box the frame they measure against.

        A frame tells an anchor it places how far its right edge is and
        where its bottom is; inside the box the content area is that frame.
        """
        style = self.style
        bottom = style.paddingBottom + style.border("Bottom")
        anchors = []
        for entry in self._entries:
            if isinstance(entry.flowable, PositionAnchor):
                entry.flowable._frame = ABag(
                    _x1=left,
                    _x=left,
                    _width=self._inner,
                    _rightPadding=0.0,
                    _leftExtraIndent=0.0,
                    _y1=bottom,
                    _bottomPadding=0.0,
                    _prevASpace=entry.before,
                )
                anchors.append(entry.flowable)
        return anchors

    # An index inside the box. multiBuild looks for indexes only in the
    # document's own story, where it calls them before and after each pass
    # and passes them what the pages announce; a box holding one stands in
    # for it there, so the index stays where it was written.

    def _boxes(self) -> list[BlockBox]:
        """This box and the boxes inside it."""
        boxes = [self]
        for flowable in self.content:
            if isinstance(flowable, BlockBox):
                boxes.extend(flowable._boxes())
        return boxes

    def _indexes(self) -> list[IndexingFlowable]:
        return [
            flowable
            for box in self._boxes()
            for flowable in box.content
            if isinstance(flowable, IndexingFlowable)
        ]

    def isIndexing(self) -> bool:
        return bool(self._indexes())

    def isSatisfied(self) -> bool:
        return all(index.isSatisfied() for index in self._indexes())

    def notify(self, kind, stuff) -> None:
        canv = getattr(self, "_canv", None)
        for index in self._indexes():
            if canv is not None:
                index._canv = canv
            try:
                index.notify(kind, stuff)
            finally:
                if canv is not None:
                    del index._canv

    def beforeBuild(self) -> None:
        # The same boxes are laid out again on every pass, and an index is
        # as tall as the entries the last pass found.
        for box in self._boxes():
            box._key = None
        for index in self._indexes():
            index.beforeBuild()

    def afterBuild(self) -> None:
        for index in self._indexes():
            index.afterBuild()

    def drawn_flowables(self) -> list[Flowable]:
        """What this part of the box drew, boxes inside it opened up."""
        return opened_up(entry.flowable for entry in self._entries)


class BottomAligned(Flowable):
    """
    A block drawn at the bottom of the frame it lands in, which takes the
    room above it as well: what follows starts in the next frame
    (-pdf-frame-align: bottom).

    Where it does not fit it goes on to the next frame, and only a frame it
    has to itself splits it. Laid out anywhere but in a frame -- in a box,
    in a table cell -- it is just the block.
    """

    #: Room left below the block. A frame takes a flowable of no height --
    #: an anchor, the page count's marker -- only while it has room left at
    #: all, and one that comes after the block belongs on its page.
    LEFT_OVER = 0.01

    def __init__(self, content: Flowable) -> None:
        super().__init__()
        self.content = content

    def identity(self, maxLen=None) -> str:
        return f"<BottomAligned at {id(self):#x} of {self.content.identity(maxLen)}>"

    def _in_frame(self, availHeight: float) -> bool:
        return getattr(self, "_frame", None) is not None and availHeight < LARGE

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        width, height = self.content.wrapOn(self.canv, availWidth, availHeight)
        self.width = width
        if self._in_frame(availHeight):
            height = max(height, availHeight - self.LEFT_OVER)
        self.height = height
        return self.width, self.height

    def split(self, availWidth: float, availHeight: float) -> list:
        if getattr(getattr(self, "_frame", None), "_atTop", False):
            return self.content.split(availWidth, availHeight)
        return []

    def drawOn(self, canvas, x: float, y: float, _sW: float = 0) -> None:
        # y is the bottom of the room taken, at the bottom of the frame.
        self.content.drawOn(canvas, x, y, _sW)


def bottom_aligned(story: list[Flowable]) -> list[Flowable]:
    """What a block put into the flow, as one block at the bottom of a frame."""
    flowables = [f for f in story if not _breaks_the_flow(f)]
    if not flowables:
        return story
    breaks = [f for f in story if _breaks_the_flow(f)]
    box = BlockBox(flowables, BoxStyle(), keep_together=True)
    return [*breaks, BottomAligned(box)]


class _UnsplittableBlockBox(BlockBox):
    """Inside the shrink fallback: whatever the room, it is one piece."""

    def split(self, availWidth: float, availHeight: float) -> list:
        return [self]


def _breaks_the_flow(flowable: Flowable) -> bool:
    """
    A flowable that has to stay in the document's own story: a page or
    frame break, a template change. A frame acts on them only where they
    are its own flowables. An index stays in the box, which stands in for
    it (see BlockBox.isIndexing).
    """
    return getattr(flowable, "locChanger", False) or hasattr(flowable, "frameAction")


def _in_flow(flowables) -> list[Flowable]:
    """The flowables that take room in the flow, skipping markers and breaks."""
    return [
        f
        for f in flowables
        if not getattr(f, "_ZEROSIZE", False) and not _breaks_the_flow(f)
    ]


def _raise_space(flowable: Flowable, side: str, value: float) -> None:
    """Make `flowable`'s spaceBefore or spaceAfter at least `value`."""
    content = getattr(flowable, "_content", None)
    if isinstance(content, list):
        # A container (KeepTogether and the like) asks its content.
        inner = _in_flow(content)
        if inner:
            _raise_space(inner[0] if side == "spaceBefore" else inner[-1], side, value)
        return
    paragraph = getattr(flowable, "P", None)
    if isinstance(paragraph, Flowable):
        # A paragraph with a floated image asks the paragraph.
        _raise_space(paragraph, side, value)
        return
    current = (
        flowable.getSpaceBefore() if side == "spaceBefore" else flowable.getSpaceAfter()
    )
    if (current or 0.0) >= value:
        return
    style = getattr(flowable, "style", None)
    if not hasattr(flowable, side) and style is not None and hasattr(style, side):
        # A paragraph's style can be shared with another paragraph.
        flowable.style = style = copy.copy(style)
        setattr(style, side, value)
    else:
        setattr(flowable, side, value)


def collapse_margins(story: list[Flowable], top: float, bottom: float) -> None:
    """
    Give a block without a box its vertical margins.

    With no padding or border to keep them apart, the block's top margin and
    its first child's are one, the larger of the two, and so are the bottom
    margins of the block and its last child (CSS 2.1, 8.3.1). `story` is
    what the block put into the flow.
    """
    flowables = _in_flow(story)
    if not flowables:
        return
    if top > 0:
        _raise_space(flowables[0], "spaceBefore", top)
    if bottom > 0:
        _raise_space(flowables[-1], "spaceAfter", bottom)


def block_box_style(c, kw: dict) -> BoxStyle | None:
    """
    The box an element declares for itself, or None when it declares none
    that shows: padding, a border or a background.

    Read off the frag CSS2Frag has filled, but only for what the element
    declares: its frag is a clone of its parent's, padding and borders
    included, and a box inside a box is not the outer box twice.
    """
    frag = c.frag
    css = c.cssAttr
    style = BoxStyle(frag, leftIndent=kw["margin-left"], rightIndent=kw["margin-right"])
    for side in _SIDES:
        low = side.lower()
        if f"padding-{low}" not in css:
            setattr(style, f"padding{side}", 0.0)
        if not any(f"border-{low}-{part}" in css for part in ("style", "width")):
            setattr(style, f"border{side}Style", None)
            setattr(style, f"border{side}Width", 0.0)
        elif getattr(style, f"border{side}Color", None) is None:
            # As a paragraph's box does: no colour is the text's.
            setattr(style, f"border{side}Color", frag.textColor)
    if "background-color" not in css:
        style.backColor = None
    if "background-image" not in css:
        style.backgroundImage = None
    if not (
        style.horizontal
        or style.vertical
        or style.backColor
        or style.backgroundImage
        or declared_height(c)
        or declared_width(c)
    ):
        return None
    return style


def declared_height(c) -> float:
    """
    The element's own CSS height in points, or 0 for none, auto or a
    percentage: a block's containing block has no height to take one of.
    """
    value = c.cssAttr.get("height")
    if value is None:
        return 0.0
    text = "".join(str(part) for part in toList(value)).strip().lower()
    if not text or text == "auto" or text.endswith("%"):
        return 0.0
    try:
        return max(getSize(text, c.frag.fontSize), 0.0)
    except Exception:
        return 0.0


def declared_width(c) -> BlockWidth | None:
    """The element's own CSS width, or None for none or auto."""
    value = c.cssAttr.get("width")
    if value is None:
        return None
    text = "".join(str(part) for part in toList(value)).strip().lower()
    if not text or text == "auto":
        return None
    length = percent = None
    try:
        if text.endswith("%"):
            percent = max(float(text[:-1]), 0.0)
        else:
            length = max(getSize(text, c.frag.fontSize), 0.0)
    except Exception:
        return None
    margins = []
    for side in ("left", "right"):
        margin = "".join(
            str(part) for part in toList(c.cssAttr.get(f"margin-{side}", ""))
        )
        margin = margin.strip().lower()
        auto = margin == "auto"
        try:
            own = 0.0 if auto or not margin else getSize(margin, c.frag.fontSize)
        except Exception:
            own = 0.0
        margins.append((own, auto))
    return BlockWidth(
        length=length,
        percent=percent,
        own_left=margins[0][0],
        own_right=margins[1][0],
        auto_left=margins[0][1],
        auto_right=margins[1][1],
    )


class BlockBoxData:
    """
    What pisaLoop keeps while it collects a block with a box: the box, and
    the story the block interrupted.

    Opened after CSS2Frag has read the block's properties and before its
    children are visited, which then start from a frag without the box --
    nothing inside draws it again or is indented by it again -- and lay
    themselves out in the box's content area.
    """

    def __init__(self, c, kw: dict, style: BoxStyle) -> None:
        c.addPara()
        frag = c.frag
        self.style = style
        self.min_height = declared_height(c)
        self.box_width = declared_width(c)
        self.keep_with_next = bool(getattr(frag, "keepWithNext", False))

        self._outer = c.swapStory()
        offset_left = style.leftIndent + style.content_left
        offset_right = style.rightIndent + style.paddingRight + style.border("Right")
        bullet_indent = (frag.bulletIndent or 0) - offset_left
        bullet_right = (getattr(frag, "bulletRightIndent", 0) or 0) - offset_right
        clear_box(frag)
        # A list marker hangs outside the box, where it was.
        frag.bulletIndent = bullet_indent
        frag.bulletRightIndent = bullet_right
        kw["margin-left"] = kw["margin-right"] = 0

        # A marker an enclosing <li> left for the first paragraph: that
        # paragraph is now in the box, so its place is measured from there.
        self._pending = c.pendingBullet
        if c.pendingBullet is not None:
            bullet, item_frag = c.pendingBullet
            item_frag = copy.copy(item_frag)
            item_frag.bulletIndent = (item_frag.bulletIndent or 0) - offset_left
            item_frag.bulletRightIndent = (
                getattr(item_frag, "bulletRightIndent", 0) or 0
            ) - offset_right
            c.pendingBullet = (bullet, item_frag)

    def close(self, c) -> list[Flowable]:
        """The box, in as many parts as page breaks inside it make."""
        c.addPara()
        content = c.swapStory(self._outer)
        if self._pending is not None and c.pendingBullet is not None:
            # Nothing in the box claimed it: it is the enclosing item's again.
            c.pendingBullet = self._pending

        segments: list[list[Flowable]] = [[]]
        between: list[list[Flowable]] = [[]]
        for flowable in content:
            if _breaks_the_flow(flowable):
                between[-1].append(flowable)
                continue
            if between[-1]:
                segments.append([])
                between.append([])
            if isinstance(flowable, KeepTogether):
                # Its wrap answers "too tall" to have the frame split it,
                # which a stack cannot take; a box without edges keeps the
                # rule instead.
                flowable = BlockBox(flowable._content, BoxStyle(), keep_together=True)
                self._collapse(flowable, flowable)
            segments[-1].append(flowable)

        out: list[Flowable] = []
        boxes: list[BlockBox] = []
        last = len(segments) - 1
        for n, (segment, breaks) in enumerate(zip(segments, between, strict=True)):
            style = self.style
            if n > 0:
                style = cut_style(style, "Top")
            if n < last:
                style = cut_style(style, "Bottom")
            if segment or len(segments) == 1:
                # The height is the whole block's; a block cut by a page
                # break inside it is not one box to give it to.
                box = BlockBox(
                    segment,
                    style,
                    min_height=self.min_height if len(segments) == 1 else 0.0,
                    box_width=self.box_width,
                )
                boxes.append(box)
                out.append(box)
            out.extend(breaks)
        if boxes:
            self._collapse(boxes[0], boxes[-1])
            boxes[-1].keepWithNext = self.keep_with_next
        return out

    @staticmethod
    def _collapse(first: BlockBox, last: BlockBox) -> None:
        """
        A margin with no padding or border to stop it goes through the box:
        the first child's top margin and the box's are one, and so are the
        last child's bottom margin and the box's (CSS 2.1, 8.3.1).
        """
        top, _ = first._margins_inside
        if not top and first.content:
            child = next(
                (f for f in first.content if not getattr(f, "_ZEROSIZE", False)), None
            )
            if child is not None:
                first.style.spaceBefore = max(
                    first.style.spaceBefore, child.getSpaceBefore() or 0.0
                )
        _, bottom = last._margins_inside
        if not bottom and last.content:
            child = next(
                (
                    f
                    for f in reversed(last.content)
                    if not getattr(f, "_ZEROSIZE", False)
                ),
                None,
            )
            if child is not None:
                last.style.spaceAfter = max(
                    last.style.spaceAfter, child.getSpaceAfter() or 0.0
                )
