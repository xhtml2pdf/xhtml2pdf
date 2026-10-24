"""
Bleed and printer's marks for `@page { bleed; marks }` (CSS Paged Media 3).

The page box of a template is the trim size: the size of the sheet once it is
cut, and the space the layout fills. With bleed or marks the PDF page grows
around it. ``bleed`` is how far the page's own background reaches past the
trim, so that a cut a little off still leaves no white edge; the marks sit in
a further margin outside that, the slug, where the cut removes them.

reportlab's crop-mark support moves the page's content and grows its
MediaBox, page by page; it is given a mark length of zero so that it draws
nothing itself, and the marks are drawn here, at negative coordinates, which
the move puts in the slug. reportlab's own bleed would scale the content to
cover the bleed, which a print shop does not want, so it stays at zero.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from reportlab.lib.colors import CMYKColor
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from xhtml2pdf.util import getSize

log = logging.getLogger(__name__)

#: The marks a template may ask for.
MARK_NAMES: frozenset[str] = frozenset({"crop", "cross"})

#: The bleed of `bleed: auto` when the page has marks (CSS Paged Media 3).
AUTO_BLEED: float = 6.0

#: The margin outside the bleed that holds the marks.
SLUG: float = 12 * mm

#: The space between the end of a crop mark and the edge of the bleed.
MARK_GAP: float = 3.0

MARK_WIDTH: float = 0.25

#: Registration colour: every separation prints it, so the marks show on
#: each plate.
REGISTRATION = CMYKColor(1, 1, 1, 1)


@dataclass
class PageMarks:
    """
    The crop-mark settings reportlab's canvas reads when it shows a page.

    Only ``borderWidth`` does anything: it is how far the content moves and
    how much the MediaBox grows on every side.
    """

    borderWidth: float
    markLength: float = 0
    markColor: None = None
    bleedWidth: float = 0
    markLast: int = 0


class MarkedCanvas(Canvas):
    """
    A canvas whose link destinations move with the content on a marked page.

    reportlab moves link rectangles by the crop-mark offset but leaves the
    coordinates of a destination where they were drawn, so a link to an
    anchor would scroll to a point the offset away from it.
    """

    def bookmarkPage(
        self, key, fit="Fit", left=None, top=None, bottom=None, right=None, zoom=None
    ):
        shift = self._getCmShift()
        if shift:
            left, top, bottom, right = (
                None if value is None else value + shift
                for value in (left, top, bottom, right)
            )
        return super().bookmarkPage(key, fit, left, top, bottom, right, zoom)


def parse_marks(value) -> frozenset[str]:
    """The `marks` of an @page: none, crop, cross or both."""
    words = value if isinstance(value, list) else [value]
    marks = {str(word).strip().lower() for word in words}
    if marks == {"none"}:
        return frozenset()
    unknown = marks - MARK_NAMES
    if unknown:
        log.warning("Unknown value for @page marks: %s", ", ".join(sorted(unknown)))
    return frozenset(marks & MARK_NAMES)


def parse_bleed(value, marks: frozenset[str]) -> float:
    """The `bleed` of an @page, in points; `auto` is 6pt with marks, else 0."""
    if value is None or str(value).strip().lower() == "auto":
        return AUTO_BLEED if marks else 0.0
    try:
        bleed = getSize(value)
    except Exception:
        bleed = None
    if bleed is None or bleed < 0:
        log.warning("Cannot read the @page bleed %r, using none", value)
        return 0.0
    return bleed


def media_offset(bleed: float, marks: frozenset[str]) -> float:
    """How far the trim box sits from the edge of the MediaBox."""
    return bleed + (SLUG if marks else 0.0)


def begin_page(canvas: Canvas, pagesize, bleed: float, marks: frozenset[str]) -> None:
    """
    Set up the page reportlab is about to draw for its bleed and marks.

    Called at the start of every page, before anything is drawn, so that the
    link rectangles reportlab writes during the page move with the content.
    The boxes are written for every page, and cleared on a page with neither
    bleed nor marks.
    """
    offset = media_offset(bleed, marks)
    if not offset:
        canvas._cropMarks = None
        canvas._trimBox = None
        canvas._bleedBox = None
        return
    width, height = pagesize
    canvas._cropMarks = PageMarks(offset)
    canvas._trimBox = (offset, offset, offset + width, offset + height)
    canvas._bleedBox = (
        offset - bleed,
        offset - bleed,
        offset + width + bleed,
        offset + height + bleed,
    )


def draw_marks(canvas: Canvas, pagesize, bleed: float, marks: frozenset[str]) -> None:
    """Draw the crop and registration marks in the slug of the current page."""
    if not marks:
        return
    width, height = pagesize
    near = bleed + MARK_GAP
    far = bleed + SLUG
    canvas.saveState()
    canvas.setStrokeColor(REGISTRATION)
    canvas.setLineWidth(MARK_WIDTH)
    if "crop" in marks:
        lines: list[tuple[float, float, float, float]] = []
        for x, sx in ((0, -1), (width, 1)):
            for y, sy in ((0, -1), (height, 1)):
                lines.extend(
                    (
                        (x + sx * near, y, x + sx * far, y),
                        (x, y + sy * near, x, y + sy * far),
                    )
                )
        canvas.lines(lines)
    if "cross" in marks:
        middle = bleed + SLUG / 2
        radius = SLUG / 6
        arm = SLUG / 3
        for cx, cy in (
            (width / 2, -middle),
            (width / 2, height + middle),
            (-middle, height / 2),
            (width + middle, height / 2),
        ):
            canvas.circle(cx, cy, radius, stroke=1, fill=0)
            canvas.lines([(cx - arm, cy, cx + arm, cy), (cx, cy - arm, cx, cy + arm)])
    canvas.restoreState()
