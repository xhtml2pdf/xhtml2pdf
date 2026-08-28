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

import io
import logging
import warnings
from html import escape as html_escape

from reportlab.lib import pdfencrypt
from reportlab.platypus.flowables import Spacer
from reportlab.platypus.frames import Frame

from xhtml2pdf.builders.signs import PDFSignature
from xhtml2pdf.builders.watermarks import WaterMarks
from xhtml2pdf.context import pisaContext
from xhtml2pdf.default import DEFAULT_CSS, DEFAULT_PAGE_NAME
from xhtml2pdf.files import cleanFiles, pisaTempFile
from xhtml2pdf.parser import pisaParser
from xhtml2pdf.util import getBox, reset_caches
from xhtml2pdf.xhtml2pdf_reportlab import PmlBaseDoc, PmlPageTemplate

log = logging.getLogger(__name__)


def pisaErrorDocument(dest, c):
    out = pisaTempFile(capacity=c.capacity)
    out.write(
        "<p style='background-color:red;'><strong>%d error(s) occurred:</strong><p>"
        % c.err
    )
    for mode, line, msg, _ in c.log:
        if mode == "error":
            out.write("<pre>%s in line %d: %s</pre>" % (mode, line, html_escape(msg)))

    out.write("<p><strong>%d warning(s) occurred:</strong><p>" % c.warn)
    for mode, line, msg, _ in c.log:
        if mode == "warning":
            out.write("<p>%s in line %d: %s</p>" % (mode, line, html_escape(msg)))

    return pisaDocument(out.getvalue(), dest, raise_exception=False)


def pisaStory(
    src,
    path="",
    link_callback=None,
    debug=0,
    default_css=None,
    xhtml=False,  # noqa: FBT002
    encoding=None,
    context=None,
    xml_output=None,
    **_kwargs,
):
    # Prepare Context
    if not context:
        context = pisaContext(path, debug=debug)
        context.pathCallback = link_callback

    # Use a default set of CSS definitions to get an expected output
    if default_css is None:
        default_css = DEFAULT_CSS

    # Parse and fill the story
    pisaParser(src, context, default_css, xhtml, encoding, xml_output)

    # Avoid empty documents
    if not context.story:
        context.story = [Spacer(1, 1)]
    else:
        # Let the first block keep its top margin.
        #
        # ReportLab's Frame._add reads a flowable's spaceBefore only when the
        # frame is not empty, so the first block of a document sat flush
        # against the top of the frame where a browser pushes it down by its
        # own margin. The margin is moved onto a spacer ahead of it, which
        # gets the same result without keeping a copy of _add in step with
        # ReportLab.
        #
        # Only the start of the story. Further pages begin with content
        # carried over, and neither engine reintroduces a margin at a page
        # break.
        first = context.story[0]
        style = getattr(first, "style", None)
        space_before = getattr(style, "spaceBefore", 0) or 0
        if space_before > 0:
            style.spaceBefore = 0
            context.story.insert(0, Spacer(1, space_before))

    if context.indexing_story:
        context.story.append(context.indexing_story)

    # Remove anchors if they do not exist (because of a bug in Reportlab)
    for frag, anchor in context.anchorFrag:
        if anchor not in context.anchorName:
            frag.link = None
    return context


def get_encrypt_instance(data):
    if data is None:
        return None

    if isinstance(data, str):
        return pdfencrypt.StandardEncryption(data)

    return data


def start_on_mirrored_pair(doc, templates, *, declared_body: bool) -> None:
    """
    Begin the document on the ``:left`` / ``:right`` pair, if that is all there is.

    A stylesheet whose only page rules are ``@page :left`` and ``@page :right``
    describes a mirrored document from its very first page. Nothing selected
    those templates before: the cycle between them is built by
    ``handle_nextPageTemplate``, which only runs for a <pdf:nextpage>, so the
    document started on the synthetic body template and the mirrored rules were
    never used -- silently.

    Handing reportlab a list as the first template index is its own way of
    saying "start on a cycle": ``handle_documentBegin`` turns it into the
    PTCycle, which is also the one case ``PmlBaseDoc.beforeDocument`` leaves
    alone between the passes of a multiBuild.
    """
    if declared_body:
        # An explicit @page wins: it says where the document starts.
        return

    mirrored = [f"{DEFAULT_PAGE_NAME}_left", f"{DEFAULT_PAGE_NAME}_right"]
    declared = {template.id for template in templates}
    if declared.issuperset(mirrored):
        # Names, not indexes: PmlBaseDoc.handle_nextPageTemplate resolves a
        # list of template ids into the cycle.
        doc._firstPageTemplateIndex = mirrored


def pisaDocument(
    src,
    dest=None,
    dest_bytes=False,  # noqa: FBT002
    path="",
    link_callback=None,
    debug=0,
    default_css=None,
    xhtml=False,  # noqa: FBT002
    encoding=None,
    xml_output=None,
    raise_exception=True,  # noqa: FBT002
    capacity=100 * 1024,
    context_meta=None,
    encrypt=None,
    signature=None,
    show_error_as_pdf=False,  # noqa: FBT002
    **kwargs,
):
    if kwargs:
        # These used to disappear into **_kwargs. Two of the callers passing
        # them were this library's own CLI and its WSGI middleware.
        warnings.warn(
            f"pisaDocument does not take {', '.join(sorted(kwargs))}",
            DeprecationWarning,
            stacklevel=2,
        )
    if debug:
        warnings.warn(
            "debug does nothing; set the level of the xhtml2pdf logger instead",
            DeprecationWarning,
            stacklevel=2,
        )

    if encrypt and signature:
        # The document is encrypted as it is built and signed after that, so
        # the signer is handed a PDF it has no password for and fails with
        # PdfKeyNotAvailableError several steps later. Said here, where the
        # caller can see which two arguments are the problem.
        msg = (
            "encrypt and signature cannot be combined: the document is"
            " encrypted before it is signed, and the signer cannot open it"
        )
        raise ValueError(msg)

    log.debug(
        "pisaDocument options:\n  src = %r\n  dest = %r\n  path = %r\n  link_callback ="
        " %r\n  xhtml = %r\n  context_meta = %r",
        src,
        dest,
        path,
        link_callback,
        xhtml,
        context_meta,
    )

    # Prepare simple context
    context = pisaContext(path, capacity=capacity)

    if context_meta is not None:
        context.meta.update(context_meta)

    context.pathCallback = link_callback

    try:
        return _build(
            src,
            context,
            dest=dest,
            dest_bytes=dest_bytes,
            path=path,
            link_callback=link_callback,
            default_css=default_css,
            xhtml=xhtml,
            encoding=encoding,
            xml_output=xml_output,
            encrypt=encrypt,
            signature=signature,
        )
    except Exception:
        # raise_exception=False has always been the documented way to ask for
        # a status object rather than an exception, and it was never read:
        # the argument was marked unused and every failure propagated.
        if raise_exception and not show_error_as_pdf:
            raise
        log.exception("Error while converting the document")
        context.err += 1
        if show_error_as_pdf:
            # What pisaErrorDocument was written for. Nothing called it.
            return pisaErrorDocument(
                dest if dest is not None else io.BytesIO(), context
            )
        return context


def _build(
    src,
    context,
    *,
    dest,
    dest_bytes,
    path,
    link_callback,
    default_css,
    xhtml,
    encoding,
    xml_output,
    encrypt,
    signature,
):
    """Convert the document; the caller decides what a failure means."""
    # Build story
    context = pisaStory(
        src,
        path,
        link_callback,
        0,
        default_css,
        xhtml,
        encoding,
        context=context,
        xml_output=xml_output,
    )

    # Buffer PDF into memory
    out = io.BytesIO()

    doc = PmlBaseDoc(
        out,
        pagesize=context.pageSize,
        author=context.meta["author"].strip(),
        subject=context.meta["subject"].strip(),
        keywords=[x.strip() for x in context.meta["keywords"].strip().split(",") if x],
        title=context.meta["title"].strip(),
        showBoundary=0,
        encrypt=get_encrypt_instance(encrypt),
        allowSplitting=1,
    )

    # Prepare templates and their frames
    declared_body = DEFAULT_PAGE_NAME in context.templateList
    if declared_body:
        body = context.templateList[DEFAULT_PAGE_NAME]
        del context.templateList[DEFAULT_PAGE_NAME]
    else:
        x, y, w, h = getBox("1cm 1cm -1cm -1cm", context.pageSize)
        body = PmlPageTemplate(
            id="body",
            frames=[
                Frame(
                    x,
                    y,
                    w,
                    h,
                    id="body",
                    leftPadding=0,
                    rightPadding=0,
                    bottomPadding=0,
                    topPadding=0,
                )
            ],
            pagesize=context.pageSize,
        )

    templates = [body, *list(context.templateList.values())]
    if context.pageCanvasBackground is not None:
        # CSS 2.1 14.2: body's background covers the canvas on every page
        for template in templates:
            template.canvasBackground = context.pageCanvasBackground
    doc.addPageTemplates(templates)
    start_on_mirrored_pair(doc, templates, declared_body=declared_body)

    # Use multibuild e.g. if a TOC has to be created
    if context.multiBuild:
        doc.multiBuild(context.story)
    else:
        doc.build(context.story)

    # Add watermarks
    output = io.BytesIO()
    output, has_bg = WaterMarks.process_doc(doc, out, output)

    if not has_bg:
        output = out
    if signature:
        signoutput = io.BytesIO()
        do_ok = PDFSignature.sign(output, signoutput, signature)
        if do_ok:
            output = signoutput

    # Get the resulting PDF and write it to the file object
    # passed from the caller

    # Get the resulting PDF and write it to the file object
    # passed from the caller

    if dest is None:
        # No output file was passed - Let's use a pisaTempFile
        dest = io.BytesIO()
    context.dest = dest

    data = output.getvalue()
    context.dest.write(data)  # TODO: context.dest is a tempfile as well...
    cleanFiles()
    reset_caches()

    if dest_bytes:
        return data

    return context
