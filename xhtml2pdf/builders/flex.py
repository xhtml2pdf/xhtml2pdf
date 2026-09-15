"""
A flex container as a ReportLab flowable.

Platypus stacks flowables top to bottom and knows nothing else, so a flex
container has to be one flowable that lays its items out inside itself: the
same shape as PmlTable. Each item is a list of flowables -- whatever the
parser collected between the item's tags -- measured as a column and drawn
at the offsets the algorithm in flex_layout gives it.

Two things here are easy to get wrong and are worth knowing about:

- Measuring is not free of side effects. PmlTable.wrap converts percentage
  column widths to points in place, so a table probed at a trial width is
  broken at every width after. The probing here (min-/max-content) therefore
  never wraps a table or a paragraph; it reads their words and their column
  widths. Only stack_flowables wraps, and it runs at a final width.

- Measuring and drawing must agree on the space between flowables. The
  height is the same merge of spaceBefore/spaceAfter that _listWrapOn does;
  the draw positions come from the very same entries, so the two cannot
  drift apart.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from operator import itemgetter
from typing import TYPE_CHECKING, Any

from reportlab.lib.abag import ABag
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus.flowables import Flowable, KeepInFrame
from reportlab.platypus.paragraph import Paragraph as ReportLabParagraph
from reportlab.platypus.tables import Table

from xhtml2pdf.builders.flex_layout import (
    ContainerSpec,
    FlexLayout,
    ItemSpec,
    resolve_flex_layout,
)
from xhtml2pdf.reportlab_paragraph import Paragraph, _getFragWords
from xhtml2pdf.util import (
    AUTO,
    NONE_LENGTH,
    CSSLength,
    drawBoxBackground,
    drawBoxBorders,
    getBorderWidth,
    getLengthOrAuto,
    getSize,
)
from xhtml2pdf.xhtml2pdf_reportlab import PmlKeepInFrame, PmlMaxHeightMixIn

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

#: The height _listWrapOn offers a flowable it is only measuring.
LARGE = 0xFFFFFFF
_FUZZ = 1e-6
ZERO = CSSLength("length", 0.0)
#: Added to a paragraph's max-content. Paragraph.breakLines breaks a line
#: that is exactly as wide as its words add up to, so an item sized to that
#: sum would wrap its last word; a hair more and it does not.
_MAX_CONTENT_SLACK = 1.0


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ The box around a container or an item
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

_SIDES = ("Left", "Right", "Top", "Bottom")


class BoxStyle:
    """
    Padding, borders and background, spelt the way ParagraphStyle spells
    them so drawBoxBackground and drawBoxBorders can read either.

    Built from a frag, which carries exactly these names once CSS2Frag has
    run over the element's block properties.
    """

    paddingLeft: float
    paddingRight: float
    paddingTop: float
    paddingBottom: float
    borderLeftWidth: float
    borderRightWidth: float
    borderTopWidth: float
    borderBottomWidth: float
    borderLeftStyle: str | None
    borderRightStyle: str | None
    borderTopStyle: str | None
    borderBottomStyle: str | None
    borderLeftColor: Any
    borderRightColor: Any
    borderTopColor: Any
    borderBottomColor: Any

    def __init__(self, frag=None, **overrides: Any) -> None:
        for side in _SIDES:
            setattr(self, f"padding{side}", 0.0)
            setattr(self, f"border{side}Width", 0.0)
            setattr(self, f"border{side}Style", None)
            setattr(self, f"border{side}Color", None)
        self.backColor = None
        self.backgroundImage = None
        self.backgroundRepeat = "repeat"
        self.backgroundPosition = "0% 0%"
        self.textColor = None
        self.fontSize = 10.0
        #: margin-top / margin-bottom, as Platypus asks for them.
        self.spaceBefore = 0.0
        self.spaceAfter = 0.0
        #: margin-left / margin-right, as the running indent.
        self.leftIndent = 0.0
        self.rightIndent = 0.0

        if frag is not None:
            for name in list(vars(self)):
                value = getattr(frag, name, None)
                if value is not None:
                    setattr(self, name, value)
        for name, value in overrides.items():
            setattr(self, name, value)

    def border(self, side: str) -> float:
        """The width a border takes up: nothing unless its style draws."""
        return getBorderWidth(
            getattr(self, f"border{side}Style"), getattr(self, f"border{side}Width")
        )

    @property
    def horizontal(self) -> float:
        """Padding and borders left and right; border box minus content box."""
        return (
            self.paddingLeft
            + self.paddingRight
            + self.border("Left")
            + self.border("Right")
        )

    @property
    def vertical(self) -> float:
        return (
            self.paddingTop
            + self.paddingBottom
            + self.border("Top")
            + self.border("Bottom")
        )

    @property
    def content_left(self) -> float:
        return self.paddingLeft + self.border("Left")

    @property
    def content_top(self) -> float:
        return self.paddingTop + self.border("Top")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ Measuring a list of flowables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


@dataclass
class StackEntry:
    flowable: Flowable
    width: float
    height: float
    #: The space merged in above this flowable, and the space it asks for
    #: below; the next entry's `before` is already net of this `after`.
    before: float
    after: float


def stack_flowables(
    content: Sequence[Flowable], width: float, canv, avail_height: float = LARGE
) -> tuple[list[StackEntry], float]:
    """
    Wrap each flowable at `width` and stack them; the entries and the height.

    The same rules as reportlab's _listWrapOn: a flowable with no height is
    skipped, spaceBefore is merged with the previous spaceAfter, and the
    last spaceAfter is not part of the height. Kept here rather than calling
    _listWrapOn because draw() walks these same entries to place things.
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
            continue
        before = 0.0
        if not at_top:
            before = flowable.getSpaceBefore()
            if getattr(flowable, "_SPACETRANSFER", False):
                before = previous_after
            before = max(before - previous_after, 0.0)
        at_top = False
        after = flowable.getSpaceAfter()
        if getattr(flowable, "_SPACETRANSFER", False):
            after = previous_after
        entries.append(StackEntry(flowable, w, h, before, after))
        height += before + h + after
        previous_after = after
    return entries, height - previous_after


def draw_stack(
    canv, entries: Sequence[StackEntry], x: float, top: float, width: float
) -> None:
    """Draw stacked entries down from `top`, the way stack_flowables measured them."""
    cursor = top
    for entry in entries:
        cursor -= entry.before + entry.height
        surplus = max(width - entry.width, 0.0)
        entry.flowable.drawOn(canv, x, cursor, surplus)
        cursor -= entry.after


def _paragraph_widths(paragraph, style) -> tuple[float, float]:
    """
    (min-content, max-content) of a paragraph, from its words.

    max-content is the longest run between line breaks laid out without
    wrapping; ReportLab does not offer it, because Paragraph.wrap assigns
    itself the available width whatever its text needs.
    """
    frags = paragraph.frags
    if not frags:
        return 0.0, 0.0
    longest_word = 0.0
    longest_line = 0.0
    line = 0.0
    previous_space = 0.0
    for word in _getFragWords(frags):
        width = word[0]
        frag = word[1][0]
        if hasattr(frag, "lineBreak"):
            longest_line = max(longest_line, line)
            line, previous_space = 0.0, 0.0
            continue
        longest_word = max(longest_word, width)
        line += previous_space + width
        previous_space = stringWidth(" ", frag.fontName, frag.fontSize)
    longest_line = max(longest_line, line) + _MAX_CONTENT_SLACK
    extra = style.leftIndent + style.rightIndent
    extra += getattr(style, "paddingLeft", 0) + getattr(style, "paddingRight", 0)
    for side in ("Left", "Right"):
        extra += getBorderWidth(
            getattr(style, f"border{side}Style", None),
            getattr(style, f"border{side}Width", 0),
        )
    return longest_word + extra, longest_line + extra


def _cell_widths(value, style, canv) -> tuple[float, float]:
    """(min-content, max-content) of one table cell's value."""
    if isinstance(value, KeepInFrame):
        value = value._content
    if isinstance(value, list | tuple):
        return content_widths(value, canv)
    if isinstance(value, Flowable):
        return content_widths([value], canv)
    if value is None:
        return 0.0, 0.0
    text = str(value)
    if not text:
        return 0.0, 0.0
    font, size = style.fontname, style.fontsize
    lines = [stringWidth(line, font, size) for line in text.split("\n")]
    words = [stringWidth(word, font, size) for word in text.split()] or [0.0]
    return max(words), max(lines)


def _table_widths(table: Table, canv) -> tuple[float, float]:
    """
    (min-content, max-content) of a table, column by column from its cells.

    Not Table.minWidth(): that asks each cell flowable for its minWidth, and
    the cells this library builds are KeepInFrames, which answer with a
    width they have not measured. A column with a width in points is that
    wide; one given as a percentage or left open is as wide as its cells.
    """
    widths = list(table._argW or [])
    if not widths:
        return 0.0, 0.0
    lows = [0.0] * len(widths)
    highs = [0.0] * len(widths)
    for row, styles in zip(table._cellvalues, table._cellStyles, strict=False):
        for column, (value, style) in enumerate(zip(row, styles, strict=False)):
            if column >= len(widths):
                break
            padding = style.leftPadding + style.rightPadding
            low, high = _cell_widths(value, style, canv)
            lows[column] = max(lows[column], low + padding)
            highs[column] = max(highs[column], high + padding)
    for column, width in enumerate(widths):
        if isinstance(width, int | float):
            lows[column] = highs[column] = float(width)
    return sum(lows), sum(highs)


def content_widths(content: Sequence[Flowable], canv) -> tuple[float, float]:
    """
    (min-content, max-content) along the width, for a list of flowables.

    The flowables stack, so the list's sizes are the largest of its members'.
    Paragraphs and tables are read, not wrapped -- see the module docstring
    for why a trial wrap is not harmless. Anything else is wrapped once at
    an unbounded width and asked for its minWidth.
    """
    min_content = 0.0
    max_content = 0.0
    for flowable in content:
        if isinstance(flowable, FlexContainer):
            low, high = flowable.content_widths(canv)
        elif isinstance(flowable, Paragraph | ReportLabParagraph):
            low, high = _paragraph_widths(flowable, flowable.style)
        elif isinstance(flowable, Table):
            low, high = _table_widths(flowable, canv)
        elif isinstance(flowable, KeepInFrame):
            low, high = content_widths(flowable._content, canv)
        elif hasattr(flowable, "drawWidth"):
            low = high = flowable.drawWidth
        else:
            high = flowable.wrapOn(canv, LARGE, LARGE)[0]
            low = min(flowable.minWidth(), high)
        min_content = max(min_content, low)
        max_content = max(max_content, high)
    return min(min_content, max_content), max_content


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ The items
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


@dataclass
class FlexItem:
    """One flex item: its content, its box, and the item properties."""

    content: list[Flowable]
    style: BoxStyle = field(default_factory=BoxStyle)
    flex_grow: float = 0.0
    flex_shrink: float = 1.0
    flex_basis: CSSLength = AUTO
    align_self: str = "auto"
    order: int = 0
    width: CSSLength = AUTO
    height: CSSLength = AUTO
    min_width: CSSLength = AUTO
    max_width: CSSLength = NONE_LENGTH
    min_height: CSSLength = AUTO
    max_height: CSSLength = NONE_LENGTH
    #: CSSLength, AUTO for an auto margin.
    margin_left: CSSLength = ZERO
    margin_right: CSSLength = ZERO
    margin_top: CSSLength = ZERO
    margin_bottom: CSSLength = ZERO

    @classmethod
    def from_frag(
        cls, content: list[Flowable], frag, margins=None, style: BoxStyle | None = None
    ) -> FlexItem:
        """
        An item from the frag of the element that is the item.

        `margins` is the four margin-* values as CSSLength, left, right, top,
        bottom; the frag only carries them as an accumulated indent, which
        cannot say "auto". `style` is the box as it was before clear_box
        took it off the frag, when the caller has done that.
        """
        left, right, top, bottom = margins or (
            ZERO,
            ZERO,
            CSSLength("length", getattr(frag, "spaceBefore", 0.0) or 0.0),
            CSSLength("length", getattr(frag, "spaceAfter", 0.0) or 0.0),
        )
        return cls(
            content=content,
            style=style or BoxStyle(frag, spaceBefore=0.0, spaceAfter=0.0),
            flex_grow=getattr(frag, "flexGrow", 0.0),
            flex_shrink=getattr(frag, "flexShrink", 1.0),
            flex_basis=getattr(frag, "flexBasis", AUTO),
            align_self=getattr(frag, "alignSelf", "auto"),
            order=getattr(frag, "flexOrder", 0),
            width=_length_from_frag(getattr(frag, "width", None)),
            height=_length_from_frag(getattr(frag, "height", None)),
            min_width=getattr(frag, "minWidth", AUTO),
            max_width=getattr(frag, "maxWidth", NONE_LENGTH),
            min_height=getattr(frag, "minHeight", AUTO),
            max_height=getattr(frag, "maxHeight", NONE_LENGTH),
            margin_left=left,
            margin_right=right,
            margin_top=top,
            margin_bottom=bottom,
        )


def _length_from_frag(value) -> CSSLength:
    """frag.width / frag.height are kept as the declared string, or None."""
    if not value:
        return AUTO
    return getLengthOrAuto(value)


def _margin(length: CSSLength, basis: float | None) -> float | None:
    """A margin for the layout: None for auto, else points."""
    if length.kind == "auto":
        return None
    return length.resolve(basis) or 0.0


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ The container
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class FlexContainer(Flowable, PmlMaxHeightMixIn):
    """
    display: flex, as one flowable the width of its frame.

    wrap() lays the items out for the width it is given and remembers the
    result; split() and draw() work from that. The layout is redone only
    when Platypus offers a different size, which it does when the container
    moves to another frame.
    """

    _SPACETRANSFER = False

    def __init__(
        self,
        items: Sequence[FlexItem],
        style: BoxStyle | None = None,
        *,
        direction: str = "row",
        wrap: str = "nowrap",
        justify_content: str = "flex-start",
        align_items: str = "stretch",
        align_content: str = "stretch",
        row_gap: CSSLength = AUTO,
        column_gap: CSSLength = AUTO,
        width: CSSLength = AUTO,
        height: CSSLength = AUTO,
    ) -> None:
        self.items = list(items)
        self.style = style or BoxStyle()
        self.direction = direction
        self.flex_wrap = wrap
        self.justify_content = justify_content
        self.align_items = align_items
        self.align_content = align_content
        self.row_gap = row_gap
        self.column_gap = column_gap
        self.css_width = width
        self.css_height = height
        self.width = 0.0
        self.height = 0.0
        #: Empty until wrap has run; _box says whether it has.
        self.layout = FlexLayout()
        #: Per item, the stacked content at the width it was last measured.
        self._stacks: dict[int, tuple[float, list[StackEntry], float]] = {}
        self._cache_key: tuple[float, float] | None = None
        self._box: ABag | None = None

    # ~ Platypus protocol ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def identity(self, maxLen=None) -> str:
        return f"<FlexContainer {self.direction} with {len(self.items)} items>"

    def getSpaceBefore(self) -> float:
        return self.style.spaceBefore

    def getSpaceAfter(self) -> float:
        return self.style.spaceAfter

    def minWidth(self) -> float:
        return self.content_widths(getattr(self, "canv", None))[0]

    @property
    def is_row(self) -> bool:
        return self.direction in {"row", "row-reverse"}

    def content_widths(self, canv) -> tuple[float, float]:
        """(min-content, max-content) of the container itself, for nesting."""
        lows, highs = [], []
        for item in self.items:
            low, high = content_widths(item.content, canv)
            extra = item.style.horizontal
            lows.append(low + extra)
            highs.append(high + extra)
        if not lows:
            return self.style.horizontal, self.style.horizontal
        gap = self.column_gap.resolve(None) or 0.0
        if self.is_row:
            gaps = gap * (len(lows) - 1)
            low = max(lows) if self.flex_wrap != "nowrap" else sum(lows) + gaps
            high = sum(highs) + gaps
        else:
            low, high = max(lows), max(highs)
        return low + self.style.horizontal, high + self.style.horizontal

    # ~ Measuring ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _stack(self, index: int, content_width: float, canv) -> tuple[list, float]:
        """The item's content stacked at `content_width`, measured once."""
        cached = self._stacks.get(index)
        if cached is not None and abs(cached[0] - content_width) < _FUZZ:
            return cached[1], cached[2]
        content_width = max(content_width, 1.0)
        entries, height = stack_flowables(
            self.items[index].content, content_width, canv, self.getMaxHeight() or LARGE
        )
        self._stacks[index] = (content_width, entries, height)
        return entries, height

    def _spec(
        self, index: int, inner_width: float, inner_height: float | None, canv
    ) -> ItemSpec:
        """
        The item as the algorithm sees it: border-box sizes on the axes.

        CSS sizes the content box and adds padding and borders outside it;
        the algorithm here works in border-box sizes, so every size from
        the item's CSS gets the box's extras added, and every size measured
        from content does too. Margins stay margins.
        """
        item = self.items[index]
        style = item.style
        horizontal, vertical = style.horizontal, style.vertical
        min_content, max_content = content_widths(item.content, canv)

        def resolved(length: CSSLength, basis: float | None, extra: float):
            value = length.resolve(basis)
            return None if value is None else value + extra

        main_basis: float | None
        cross_basis: float | None
        if self.is_row:
            main_extra, cross_extra = horizontal, vertical
            main_basis, cross_basis = inner_width, inner_height
            main_min_content = min_content + horizontal
            main_max_content = max_content + horizontal
            size, cross = item.width, item.height
            min_main, max_main = item.min_width, item.max_width
            min_cross, max_cross = item.min_height, item.max_height
        else:
            main_extra, cross_extra = vertical, horizontal
            main_basis, cross_basis = inner_height, inner_width
            # Along a column the content size is a height: the content
            # stacked at the width it will have, which is the inner width
            # (stretch) unless the item says otherwise.
            declared = item.width.resolve(inner_width)
            cross_width = (
                declared
                if declared is not None
                else min(max_content, inner_width - horizontal)
            )
            _entries, stacked = self._stack(index, cross_width, canv)
            main_min_content = main_max_content = stacked + vertical
            size, cross = item.height, item.width
            min_main, max_main = item.min_height, item.max_height
            min_cross, max_cross = item.min_width, item.max_width

        flex_basis: float | None
        if item.flex_basis.kind == "content":
            flex_basis = main_max_content
        else:
            flex_basis = resolved(item.flex_basis, main_basis, main_extra)

        return ItemSpec(
            flex_basis=flex_basis,
            specified=resolved(size, main_basis, main_extra),
            min_content=main_min_content,
            max_content=main_max_content,
            grow=item.flex_grow,
            shrink=item.flex_shrink,
            min_main=resolved(min_main, main_basis, main_extra),
            max_main=resolved(max_main, main_basis, main_extra),
            margin_main_start=_margin(
                item.margin_left if self.is_row else item.margin_top, inner_width
            ),
            margin_main_end=_margin(
                item.margin_right if self.is_row else item.margin_bottom, inner_width
            ),
            margin_cross_start=_margin(
                item.margin_top if self.is_row else item.margin_left, inner_width
            ),
            margin_cross_end=_margin(
                item.margin_bottom if self.is_row else item.margin_right, inner_width
            ),
            align_self=item.align_self,
            cross_specified=resolved(cross, cross_basis, cross_extra),
            min_cross=resolved(min_cross, cross_basis, cross_extra),
            max_cross=resolved(max_cross, cross_basis, cross_extra),
            order=item.order,
        )

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        availHeight = self.setMaxHeight(availHeight)
        key = (round(availWidth, 2), round(availHeight, 2))
        if self._cache_key == key and self._box is not None:
            return self.width, self.height
        canv = getattr(self, "canv", None)
        style = self.style

        # The container's own box: margins outside, then padding and borders.
        outer_width = availWidth - style.leftIndent - style.rightIndent
        declared_width = self.css_width.resolve(outer_width)
        if declared_width is not None:
            outer_width = min(outer_width, declared_width + style.horizontal)
        inner_width = max(outer_width - style.horizontal, 1.0)
        # A percentage height has nothing definite to resolve against in a
        # flow of flowables, so only a length makes the height definite.
        inner_height = self.css_height.resolve(None)

        if self.is_row:
            main_size: float | None = inner_width
            cross_size = inner_height
        else:
            main_size = inner_height
            cross_size = inner_width

        specs = [
            self._spec(index, inner_width, inner_height, canv)
            for index in range(len(self.items))
        ]
        gap_basis = inner_width
        row_gap = self.row_gap.resolve(gap_basis) or 0.0
        column_gap = self.column_gap.resolve(gap_basis) or 0.0
        container = ContainerSpec(
            main_size=main_size,
            cross_size=cross_size,
            direction=self.direction,
            wrap=self.flex_wrap,
            justify_content=self.justify_content,
            align_items=self.align_items,
            align_content=self.align_content,
            main_gap=column_gap if self.is_row else row_gap,
            cross_gap=row_gap if self.is_row else column_gap,
        )

        def measure_cross(index: int, main: float) -> float:
            item = self.items[index]
            if self.is_row:
                _entries, height = self._stack(
                    index, main - item.style.horizontal, canv
                )
                return height + item.style.vertical
            # In a column the cross size is the width the content wants,
            # capped by the container: fit-content.
            _low, high = content_widths(item.content, canv)
            return min(high + item.style.horizontal, inner_width)

        layout = resolve_flex_layout(specs, container, measure_cross)

        # The final pass wins: every item is stacked at the width it will be
        # drawn at, whatever width it was probed at along the way.
        for placed in layout.placed:
            item = self.items[placed.index]
            box_width = placed.main_size if self.is_row else placed.cross_size
            self._stack(placed.index, box_width - item.style.horizontal, canv)

        self.layout = layout
        self._cache_key = key
        self._box = ABag(
            outer_width=outer_width,
            inner_width=inner_width,
            inner_height=layout.cross_size if self.is_row else layout.main_size,
        )
        self.width = availWidth
        self.height = self._box.inner_height + style.vertical
        return self.width, self.height

    def split(self, availWidth: float, availHeight: float) -> list:
        """
        Cut between flex lines, never inside one.

        A row container breaks between its lines (flex-wrap: wrap); a column
        container between its items, which stack the same way. Whatever
        does not fit the room left here moves whole to the next frame, and
        a piece taller than any frame is shrunk rather than lost.
        """
        self.wrap(availWidth, availHeight)
        if self.height <= availHeight + _FUZZ:
            return [self]

        bands = self._bands()
        room = availHeight - self.style.content_top
        fitting = [band for band in bands if band[0] <= room + _FUZZ]
        if fitting and len(fitting) < len(bands):
            head = {i for band in fitting for i in band[1]}
            return self._split_items(head)

        # Nothing fits the room left here, or all of it does but the box
        # around it does not. Whether to wait for the next frame depends on
        # the first band alone: if a whole frame holds it, the rest is cut
        # there in turn. Only a band no frame can hold is shrunk -- an empty
        # list for that would have Platypus try the next frame forever, and
        # shrinking is what a table cell does with the same problem.
        max_height = self.getMaxHeight() or availHeight
        first = (bands[0][0] + self.style.vertical) if bands else self.height
        if first > max_height + _FUZZ:
            return [
                PmlKeepInFrame(
                    maxWidth=availWidth,
                    maxHeight=availHeight,
                    mode="shrink",
                    content=[self._unsplittable()],
                )
            ]
        return []

    def _bands(self) -> list[tuple[float, list[int]]]:
        """
        (bottom edge, item indices) of each horizontal band, top to bottom.

        In a row the bands are the flex lines; in a column, the items. The
        edge is measured from the top of the content box.
        """
        bands: dict[int, tuple[float, list[int]]] = {}
        for placed in self.layout.placed:
            if self.is_row:
                key = placed.line
                bottom = placed.cross_pos + placed.cross_size
            else:
                key = placed.index
                bottom = placed.main_pos + placed.main_size
            edge, indices = bands.get(key, (0.0, []))
            bands[key] = (max(edge, bottom), [*indices, placed.index])
        return sorted(bands.values(), key=itemgetter(0))

    def _split_items(self, head: set[int]) -> list[FlexContainer]:
        """Two containers holding the head items and the rest, in order."""
        first = [item for i, item in enumerate(self.items) if i in head]
        rest = [item for i, item in enumerate(self.items) if i not in head]
        top = BoxStyle(self.style, paddingBottom=0.0, spaceAfter=0.0)
        top.borderBottomStyle = None
        bottom = BoxStyle(self.style, paddingTop=0.0, spaceBefore=0.0)
        bottom.borderTopStyle = None
        return [self._like(first, top), self._like(rest, bottom)]

    def _like(
        self, items: Sequence[FlexItem], style: BoxStyle, cls: type | None = None
    ) -> FlexContainer:
        """A container with these items and the same properties as this one."""
        return (cls or type(self))(
            items,
            style,
            direction=self.direction,
            wrap=self.flex_wrap,
            justify_content=self.justify_content,
            align_items=self.align_items,
            align_content=self.align_content,
            row_gap=self.row_gap,
            column_gap=self.column_gap,
            width=self.css_width,
            height=self.css_height,
        )

    def _unsplittable(self) -> FlexContainer:
        """A copy whose split never recurses into this fallback."""
        return self._like(self.items, self.style, cls=_UnsplittableFlexContainer)

    # ~ Drawing ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def draw(self) -> None:
        if self._box is None:
            self.wrap(self.width, LARGE)
        layout, box = self.layout, self._box
        assert box is not None
        canv = self.canv
        style = self.style

        # drawOn has moved the origin to the container's bottom left.
        outer_x = style.leftIndent
        outer_h = self.height
        drawBoxBackground(canv, outer_x, 0, box.outer_width, outer_h, style)

        content_x = outer_x + style.content_left
        content_top = outer_h - style.content_top
        for placed in layout.placed:
            item = self.items[placed.index]
            if self.is_row:
                x = content_x + placed.main_pos
                top = content_top - placed.cross_pos
                w, h = placed.main_size, placed.cross_size
            else:
                x = content_x + placed.cross_pos
                top = content_top - placed.main_pos
                w, h = placed.cross_size, placed.main_size
            y = top - h
            drawBoxBackground(canv, x, y, w, h, item.style)
            draw_stack(
                canv,
                self._stacks[placed.index][1],
                x + item.style.content_left,
                top - item.style.content_top,
                w - item.style.horizontal,
            )
            drawBoxBorders(canv, x, y, w, h, item.style)

        drawBoxBorders(canv, outer_x, 0, box.outer_width, outer_h, style)


class _UnsplittableFlexContainer(FlexContainer):
    """Inside the shrink fallback: whatever the room, it is one piece."""

    def split(self, availWidth: float, availHeight: float) -> list:
        return [self]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ Collecting a container while the parser walks it
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#: The frag attributes that describe an element's own box. A child's frag is
#: a clone of its parent's, so without clearing these a paragraph inside a
#: flex item would paint the item's padding and background a second time.
_BOX_ATTRIBUTES: dict[str, Any] = {
    "paddingLeft": 0,
    "paddingRight": 0,
    "paddingTop": 0,
    "paddingBottom": 0,
    "backColor": None,
    "backgroundImage": None,
    "leftIndent": 0,
    "rightIndent": 0,
    "spaceBefore": 0,
    "spaceAfter": 0,
    "bulletIndent": 0,
}


def clear_box(frag) -> None:
    """Take an element's box off its frag, so its children do not repeat it."""
    for name, value in _BOX_ATTRIBUTES.items():
        setattr(frag, name, value)
    for side in _SIDES:
        setattr(frag, f"border{side}Width", 0)
        setattr(frag, f"border{side}Style", None)
        setattr(frag, f"border{side}Color", None)


class FlexData:
    """
    The flex container the parser is inside, the way TableData is the table.

    pisaLoop swaps one in when it meets display: flex and swaps the previous
    one back when the element closes, so containers nest. Each child of the
    container is one item: its story is collected apart, between begin_item
    and end_item, and the child's own frag says what kind of item it is.
    """

    def __init__(self, frag=None, css_attr=None, *, rtl: bool = False) -> None:
        #: False on the instance a context starts with, which is no container.
        self.active = frag is not None
        self.items: list[FlexItem] = []
        #: True from begin_item until the child element publishes its
        #: properties; only the outermost element of an item does.
        self.collecting_item = False
        self._item_frag = None
        self._item_style: BoxStyle | None = None
        self._item_margins: tuple | None = None
        self._outer_story: list | None = None
        if frag is None:
            return

        self.style = BoxStyle(frag)
        direction = frag.flexDirection
        if rtl and direction in {"row", "row-reverse"}:
            # main-start is the right in a right-to-left document.
            direction = "row-reverse" if direction == "row" else "row"
        self.direction = direction
        self.wrap = frag.flexWrap
        self.justify_content = frag.justifyContent
        self.align_items = frag.alignItems
        self.align_content = frag.alignContent
        self.row_gap = frag.rowGap
        self.column_gap = frag.columnGap
        self.width = _length_from_frag(frag.width)
        self.height = _length_from_frag(frag.height)

    def begin_item(self, c) -> None:
        c.addPara()
        c.clearFrag()
        self._outer_story = c.swapStory()
        self.collecting_item = True
        self._item_frag = None
        self._item_style = None
        self._item_margins = None

    def set_item_style(self, frag, css_attr) -> None:
        """
        The child element's frag and margins, taken as it opens.

        Margins come from the declarations rather than the frag: the frag
        only has them as an accumulated indent, which cannot say "auto".
        The element's box then comes off the frag, so the paragraphs inside
        the item do not paint it again and are not indented by it again.
        """
        self.collecting_item = False
        self._item_frag = frag
        # The box is read before it comes off the frag; the vertical margins
        # are the item's, read below, not spacing for the paragraphs inside.
        self._item_style = BoxStyle(frag, spaceBefore=0.0, spaceAfter=0.0)
        size = frag.fontSize
        margins = []
        for name in ("margin-left", "margin-right", "margin-top", "margin-bottom"):
            if name in css_attr:
                margins.append(getLengthOrAuto(css_attr[name], size))
            else:
                margins.append(ZERO)
        self._item_margins = tuple(margins)
        clear_box(frag)

    def end_item(self, c) -> None:
        c.addPara()
        assert self._outer_story is not None, "end_item without begin_item"
        content = c.swapStory(self._outer_story)
        self._outer_story = None
        self.collecting_item = False
        if not content:
            # Whitespace between tags, a comment, display: none: no item.
            return
        if self._item_frag is None:
            # Text straight inside the container: an anonymous item.
            self.items.append(FlexItem(content=content))
        else:
            self.items.append(
                FlexItem.from_frag(
                    content, self._item_frag, self._item_margins, self._item_style
                )
            )

    def build(self) -> FlexContainer | None:
        if not self.items:
            return None
        return FlexContainer(
            self.items,
            self.style,
            direction=self.direction,
            wrap=self.wrap,
            justify_content=self.justify_content,
            align_items=self.align_items,
            align_content=self.align_content,
            row_gap=self.row_gap,
            column_gap=self.column_gap,
            width=self.width,
            height=self.height,
        )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ display: inline-block
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class InlineBox(Flowable):
    """
    display: inline-block -- a box that is one word of the line it sits in.

    The paragraph carries it as a cbDefn of kind "box", the way it carries an
    inline image: the box's width is the word's width, its height and
    vertical-align set the line's height, and _putFragLine draws it where
    the word falls. Sized shrink-to-fit: as wide as its content wants, up to
    the room the line has, unless width says otherwise.
    """

    _SPACETRANSFER = False

    def __init__(
        self,
        content: Sequence[Flowable],
        style: BoxStyle | None = None,
        *,
        width: CSSLength = AUTO,
        height: CSSLength = AUTO,
        margin_left: float = 0.0,
        margin_right: float = 0.0,
        margin_top: float = 0.0,
        margin_bottom: float = 0.0,
    ) -> None:
        self.content = list(content)
        self.style = style or BoxStyle()
        self.css_width = width
        self.css_height = height
        self.margins = (margin_left, margin_right, margin_top, margin_bottom)
        self.width = 0.0
        self.height = 0.0
        self._entries: list[StackEntry] = []
        self._box_width = 0.0
        self._box_height = 0.0
        self._cache_key: float | None = None

    def identity(self, maxLen=None) -> str:
        return f"<InlineBox with {len(self.content)} flowables>"

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        key = round(availWidth, 2)
        if self._cache_key == key:
            return self.width, self.height
        canv = getattr(self, "canv", None)
        style = self.style
        left, right, top, bottom = self.margins
        room = max(availWidth - left - right - style.horizontal, 1.0)

        declared = self.css_width.resolve(availWidth)
        if declared is not None:
            content_width = min(declared, room)
        else:
            # CSS fit-content: min(max-content, max(min-content, available)).
            low, high = content_widths(self.content, canv)
            content_width = min(high, max(low, room))
            content_width = min(content_width, room) if room > low else low
        content_width = max(content_width, 1.0)

        self._entries, content_height = stack_flowables(
            self.content, content_width, canv, LARGE
        )
        declared_height = self.css_height.resolve(None)
        if declared_height is not None:
            content_height = declared_height

        self._box_width = content_width + style.horizontal
        self._box_height = content_height + style.vertical
        self.width = self._box_width + left + right
        self.height = self._box_height + top + bottom
        self._cache_key = key
        return self.width, self.height

    def draw(self) -> None:
        if self._cache_key is None:
            self.wrap(LARGE, LARGE)
        canv = self.canv
        style = self.style
        left, _right, _top, bottom = self.margins
        x, y = left, bottom
        drawBoxBackground(canv, x, y, self._box_width, self._box_height, style)
        draw_stack(
            canv,
            self._entries,
            x + style.content_left,
            y + self._box_height - style.content_top,
            self._box_width - style.horizontal,
        )
        drawBoxBorders(canv, x, y, self._box_width, self._box_height, style)


def inline_box_frag(frag, box: InlineBox, valign="baseline"):
    """
    The frag that carries an InlineBox through a paragraph.

    Appended to the frag list directly, not through addFrag, which clones
    with keyword arguments -- and the patched clone drops cbDefn when it is
    given any, on purpose, so that a box is not inherited by the text after
    it. Same shape as the frag pisaTagIMG builds for an inline image.
    """
    carrier = frag.clone()
    carrier.text = ""
    carrier.cbDefn = ABag(
        kind="box",
        flowable=box,
        valign=valign,
        fontName=carrier.fontName,
        fontSize=box.height,
        width=box.width,
        height=box.height,
    )
    return carrier


#: The vertical-align keywords imgVRange understands; anything else is a
#: length, which it takes as a raise in points.
_VALIGN_KEYWORDS = frozenset(
    {"baseline", "top", "text-top", "middle", "bottom", "text-bottom", "super", "sub"}
)


def box_valign(value, font_size: float = 0.0):
    if value is None:
        return "baseline"
    text = "".join(
        str(part) for part in (value if isinstance(value, list | tuple) else [value])
    )
    text = text.strip().lower()
    if text in _VALIGN_KEYWORDS:
        return text
    if not text:
        return "baseline"
    return getSize(text, font_size)


class InlineBoxData:
    """
    What pisaLoop sets aside while it collects an inline-block.

    The box sits inside a paragraph that is still being built, so unlike a
    flex container it cannot flush that paragraph: the pending frags, text
    and anchors are saved, the box's content is collected into a story of
    its own, and when the element closes the paragraph gets them back with
    one frag more -- the carrier of the box.
    """

    _PENDING = (
        "fragList",
        "text",
        "fragStrip",
        "fragAnchor",
        "force",
        "image",
        "imageData",
    )

    def __init__(self, c, frag, css_attr) -> None:
        self.style = BoxStyle(frag, spaceBefore=0.0, spaceAfter=0.0)
        self.width = _length_from_frag(frag.width)
        self.height = _length_from_frag(frag.height)
        self.valign = box_valign(getattr(frag, "vAlign", None), frag.fontSize)
        size = frag.fontSize
        self.margins = tuple(
            (
                (getLengthOrAuto(css_attr[name], size).resolve(None) or 0.0)
                if name in css_attr
                else 0.0
            )
            for name in ("margin-left", "margin-right", "margin-top", "margin-bottom")
        )
        self._saved = {name: getattr(c, name) for name in self._PENDING}
        c.clearFrag()
        c.fragAnchor = []
        c.force = False
        c.image = None
        c.imageData = {}
        self._outer_story = c.swapStory()
        # The box paints its own padding, borders and background; the
        # paragraphs inside it must not.
        clear_box(frag)

    def close(self, c) -> InlineBox | None:
        c.addPara()
        content = c.swapStory(self._outer_story)
        for name, value in self._saved.items():
            setattr(c, name, value)
        if not content:
            return None
        left, right, top, bottom = self.margins
        box = InlineBox(
            content,
            self.style,
            width=self.width,
            height=self.height,
            margin_left=left,
            margin_right=right,
            margin_top=top,
            margin_bottom=bottom,
        )
        # Sized to its content for now; the paragraph lays it out again for
        # the width it really has, in PmlParagraph._calcImageMaxSizes.
        box.wrapOn(None, LARGE, LARGE)
        c.fragList.append(inline_box_frag(c.frag, box, self.valign))
        # Like an image: a paragraph holding nothing but the box still exists.
        c.force = True
        return box
