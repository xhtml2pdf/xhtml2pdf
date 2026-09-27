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
from typing import TYPE_CHECKING, Any

from xhtml2pdf.util import AUTO, CSSLength, getLengthOrAuto

if TYPE_CHECKING:
    from collections.abc import Mapping

    from reportlab.platypus.flowables import Flowable

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
