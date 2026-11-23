"""
CSS opacity: what a box draws is painted as one translucent group.

CSS 3 Color applies opacity to the element and its content together, after
they are drawn: where two parts of the box overlap, they do not show through
each other. PDF says the same with a transparency group, a form XObject
carrying ``/Group <</S /Transparency>>``, painted with a constant alpha. A
per-colour alpha would let a child's background show its parent's text
through it.

ReportLab draws forms but has no word for a group, and refuses a form that
holds an annotation. The group is added to the form's stream dictionary once
the form is made, and the links drawn inside it are handed to the page,
where annotations belong; their rectangles are worked out against the page,
not the form.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reportlab.pdfbase.pdfdoc import PDFDictionary, PDFName, PDFStream, xObjectName

if TYPE_CHECKING:
    from collections.abc import Callable


class _TransparencyGroupStream(PDFStream):
    """A form's content stream whose dictionary declares a transparency group."""

    def format(self, document):
        self.dictionary["Group"] = PDFDictionary(
            {"Type": PDFName("Group"), "S": PDFName("Transparency")}
        )
        return super().format(document)


def paint_with_opacity(canv, opacity: float, draw: Callable[[], None]) -> None:
    """
    Run `draw` on `canv`, as one group painted at `opacity`.

    Fully opaque, `draw` simply runs. Otherwise what it draws goes into a
    form whose bounding box is three pages each way around the origin, so
    nothing a box draws beside itself -- a list marker, a shadow -- is cut,
    and the form is drawn where the box is, under a constant fill and stroke
    alpha.
    """
    if opacity >= 1.0:
        draw()
        return
    width, height = canv._pagesize
    # Numbered per document, so the same document always comes out the same.
    doc = canv._doc
    doc._xhtml2pdfGroups = getattr(doc, "_xhtml2pdfGroups", 0) + 1
    name = f"xhtml2pdfOpacity{doc._xhtml2pdfGroups}"
    outer = canv._currentMatrix
    canv.beginForm(name, -3 * width, -3 * height, 3 * width, 3 * height)
    # Link rectangles are measured with this matrix: against the page.
    canv._currentMatrix = outer
    try:
        draw()
    finally:
        links = list(canv._annotationrefs)
        canv._annotationrefs[:] = []
        canv.endForm()
    canv._annotationrefs.extend(links)
    form = canv._doc.idToObject[xObjectName(name)]
    group = _TransparencyGroupStream()
    group.content = form.stream
    group.__Comment__ = "xobject form stream"
    form.Contents = group
    canv.saveState()
    canv.setFillAlpha(opacity)
    canv.setStrokeAlpha(opacity)
    canv.doForm(name)
    canv.restoreState()
