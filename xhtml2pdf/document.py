# -*- coding: utf-8 -*-

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

import six
from reportlab.platypus import NextPageTemplate
from reportlab.platypus.flowables import Spacer
from reportlab.platypus.frames import Frame

from xhtml2pdf.context import pisaContext
from xhtml2pdf.default import DEFAULT_CSS
from xhtml2pdf.parser import (pisaParser, set_grid_class, div_attr_list, grid_text, set_column_text,
                              grid_build_context, collect_paragraph_styles)
from xhtml2pdf.util import PyPDF2, getBox, pisaTempFile
from xhtml2pdf.xhtml2pdf_reportlab import PmlBaseDoc, PmlPageTemplate, PmlParagraph
from xhtml2pdf.grid import Grid


out_grid = []
if not six.PY2:
    from html import escape as html_escape
else:
    from cgi import escape as html_escape

log = logging.getLogger("xhtml2pdf")


def pisaErrorDocument(dest, c):
    out = pisaTempFile(capacity=c.capacity)
    out.write("<p style='background-color:red;'><strong>%d error(s) occured:</strong><p>" % c.err)
    for mode, line, msg, _ in c.log:
        if mode == "error":
            out.write("<pre>%s in line %d: %s</pre>" %
                      (mode, line, html_escape(msg)))

    out.write("<p><strong>%d warning(s) occured:</strong><p>" % c.warn)
    for mode, line, msg, _ in c.log:
        if mode == "warning":
            out.write("<p>%s in line %d: %s</p>" %
                      (mode, line, html_escape(msg)))

    return pisaDocument(out.getvalue(), dest, raise_exception=False)


def pisaStory(src, path=None, link_callback=None, debug=0, default_css=None,
              xhtml=False, encoding=None, context=None, xml_output=None,
              **kw):
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

    if context.indexing_story:
        context.story.append(context.indexing_story)

    # Remove anchors if they do not exist (because of a bug in Reportlab)
    for frag, anchor in context.anchorFrag:
        if anchor not in context.anchorName:
            frag.link = None
    return context


def getting_flow_position_in_grid(context):
    cont = 0
    list_cont = []
    for i in context.story:
        if isinstance(i, PmlParagraph):
            if i.frags[0].inCols:
                list_cont.append(cont)
        cont = cont + 1
    return list_cont


def getting_global_grid_next_template(list_nexts, list_cont):
    global_grid_next_template = []
    for index in list_nexts:
        for i in range(index):
            if i == index - 1:
                global_grid_next_template.append(list_cont[i]+1)
    return global_grid_next_template


def setting_next_page_template(global_grid_next_template, ids, context):
    for i in range(len(global_grid_next_template)):
        context.story.insert(global_grid_next_template[i], NextPageTemplate(ids[i+1]))


def checking_content_out_grid(context):
    for i in context.story:
        if isinstance(i, PmlParagraph):
            if i.frags[0].inCols == True:
                pass
            else:
                out_grid.append(i.frags[0])


def build_grid_templates(doc, context):
    joinList = list(context.templateList.values())
    global grid_text
    if grid_text != []:
        checking_content_out_grid(context)
        styles = collect_paragraph_styles(context)
        divs = set_grid_class(div_attr_list)
        g = Grid(set_column_text(grid_build_context(divs), grid_text), doc)
        ptl, ids, next_template_position_list = g.getting_templates_datas(static_frame=context.frameStatic, styles=styles)
        setting_next_page_template(getting_global_grid_next_template
                         (next_template_position_list, getting_flow_position_in_grid(context)), ids, context)
        if list(context.templateList.values()) != []:
            joinList = list(context.templateList.values()) + ptl
        else:
            joinList = ptl
        grid_text = []
    return joinList

def pisaDocument(src, dest=None, path=None, link_callback=None, debug=0,
                 default_css=None, xhtml=False, encoding=None, xml_output=None,
                 raise_exception=True, capacity=100 * 1024, context_meta=None,
                 **kw):
    log.debug("pisaDocument options:\n  src = %r\n  dest = %r\n  path = %r\n  link_callback = %r\n  xhtml = %r\n  context_meta = %r",
              src,
              dest,
              path,
              link_callback,
              xhtml,
              context_meta)

    # Prepare simple context
    context = pisaContext(path, debug=debug, capacity=capacity)

    if context_meta is not None:
        context.meta.update(context_meta)

    context.pathCallback = link_callback

    # Build story
    context = pisaStory(src, path, link_callback, debug, default_css, xhtml,
                        encoding, context=context, xml_output=xml_output)

    # Buffer PDF into memory
    out = io.BytesIO()
    doc = PmlBaseDoc(
        out,
        pagesize=context.pageSize,
        author=context.meta["author"].strip(),
        subject=context.meta["subject"].strip(),
        keywords=[x.strip() for x in
                  context.meta["keywords"].strip().split(",") if x],
        title=context.meta["title"].strip(),
        showBoundary=0,
        allowSplitting=1)
    # Prepare templates and their frames
    multi_template_list = False
    if "body" in context.templateList:
        body = context.templateList["body"]
        del context.templateList["body"]
    else:
        x, y, w, h = getBox("1cm 1cm -1cm -1cm", context.pageSize)
        body = PmlPageTemplate(
            id="body",
            frames=[
                Frame(x, y, w, h,
                      id="body",
                      leftPadding=0,
                      rightPadding=0,
                      bottomPadding=0,
                      topPadding=0)],
            pagesize=context.pageSize)

    ptl = build_grid_templates(doc, context)
    if ptl == []:
        doc.addPageTemplates([body] + list(context.templateList.values()))
    if ptl != []:
        if out_grid == []:
            doc.addPageTemplates(ptl)
        else:
            doc.addPageTemplates([body] + ptl)

    # Use multibuild e.g. if a TOC has to be created
    if context.multiBuild:
        doc.multiBuild(context.story)
    else:
        doc.build(context.story)

    # Add watermarks
    if PyPDF2:
        file_handler = None
        for bgouter in context.pisaBackgroundList:
            # If we have at least one background, then lets do it
            if bgouter:
                istream = out

                output = PyPDF2.PdfFileWriter()
                input1 = PyPDF2.PdfFileReader(istream)
                ctr = 0
                # TODO: Why do we loop over the same list again?
                # see bgouter at line 137
                for bg in context.pisaBackgroundList:
                    page = input1.getPage(ctr)
                    if (
                            bg and not bg.notFound() and
                            (bg.mimetype == "application/pdf")
                    ):
                        file_handler = open(bg.uri, 'rb')
                        bginput = PyPDF2.PdfFileReader(file_handler)
                        pagebg = bginput.getPage(0)
                        pagebg.mergePage(page)
                        page = pagebg

                    # Todo: the else-statement doesn't make a lot of sense to me; it's just throwing warnings
                    #  on unittesting \tests. Probably we have to rewrite the whole "background-image" stuff
                    #  to deal with cases like:
                    #  Page1 .jpg background
                    #  Page1 .pdf background
                    #  Page1 .jpg background, Page2 no background
                    #  Page1 .pdf background, Page2 no background
                    #  Page1 .jpg background, Page2 .pdf background
                    #  Page1 .pdf background, Page2 .jpg background
                    #  etc.
                    #  Right now it's kind of confusing. (fbernhart)
                    # else:
                    #     log.warning(context.warning(
                    #         "Background PDF %s doesn't exist.", bg))

                    output.addPage(page)

                    ctr += 1
                out = pisaTempFile(capacity=context.capacity)
                output.write(out)
                if file_handler:
                    file_handler.close()
                # data = sout.getvalue()
                # Found a background? So leave loop after first occurence
                break
    else:
        log.warning(context.warning("PyPDF2 not installed!"))

    # Get the resulting PDF and write it to the file object
    # passed from the caller

    if dest is None:
        # No output file was passed - Let's use a pisaTempFile
        dest = io.BytesIO()
    context.dest = dest

    data = out.getvalue()
    context.dest.write(data)  # TODO: context.dest is a tempfile as well...

    return context
