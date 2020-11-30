from reportlab.lib import colors
from reportlab.platypus import Frame, PageTemplate, Paragraph, FrameBreak
from reportlab.lib.styles import ParagraphStyle
import six
from xhtml2pdf.xhtml2pdf_reportlab import PmlImage
import re
from xhtml2pdf.utility_calc_values import UtilityCalcValues
from xhtml2pdf.utility_search_strip_values import UtilitySearchStrip
from xhtml2pdf.default_grid_system import DefaultGridSystem


class Grid(UtilityCalcValues, UtilitySearchStrip, DefaultGridSystem):

    context_paint = []
    flowElements = []
    wraps = []
    frames = []
    cols_width = []
    page_frames = []
    grids = []
    children = []
    static_frames = None
    style = None
    doc = None
    doc_width = 0
    p = None
    unique_index = '#class-colS'
    next_frame = 'next_frame'
    context = None
    styles = []

    def __init__(self, context, doc):

        self.doc = doc

        self.style = ParagraphStyle('style', textColor=colors.black, firstLineIndent=5, fontSize=7.5, leading=11.5,
                              borderPadding=(5,), borderColor=colors.blue, allowWidows=1, allowOrphans=0)

        self.doc_width = self.doc.width

        self.context = context

    def get_temporal_paragraph(self, text, style, grid_class):
        p = Paragraph(text, self.style)
        cw = self.get_col_width(grid_class)
        w, h = p.wrap(cw, self.doc.height)
        return h

    def setting_context(self):
        cont = 0
        grid = []
        for i in self.context:
            if i.get('class') == 'columns' or self.cols.get(i.get('class')):
                if i.get('class') == 'columns':
                    cont = cont + 1
                if cont > 1:
                    self.grids.append(grid)
                    grid = []
                    cont = 0
                grid.append(i)
        self.grids.append('grid')
        self.grids.append(grid)
        self.context_paint.append(self.grids)
        return self.context_paint

    def setting_index_to_flowable(self, flowable, numStyle):
        if isinstance(flowable.get('text'), six.text_type):
            if flowable.get('child'):
                self.p = Paragraph(self.index.get('child') + flowable.get('child') + self.index.get('default')
                                   + flowable.get('class') + self.index.get('default') + ' ' + flowable.get('text'),
                                   self.style)
            if flowable.get('parent'):
                self.p = Paragraph(self.index.get('parent') + flowable.get('parent') + self.index.get('default')
                                   + flowable.get('class')+ self.index.get('default') + ' ' + flowable.get('text'),
                                   self.style)
            if not flowable.get('child') and not flowable.get('parent'):
                self.p = Paragraph(self.index.get('default') + flowable.get('class') + self.index.get('default') + ' ' +
                                   flowable.get('text'),
                                   self.style)
        obj = None
        if isinstance(flowable.get('text'), list):
            if dict in flowable.get('text'):
                obj = flowable.get('text')[1].get('scr')
                width = flowable.get('text')[1].get('width')
                height = flowable.get('text')[1].get('height')
            if isinstance(flowable.get('text')[0], six.text_type):
                flow_para = {
                    "class": flowable.get('class'),
                    "text": flowable.get('text')[0],
                }
                self.setting_index_to_flowable(flow_para, numStyle)
            else:
                flow_img = {
                'scr': flowable.get('text')[0].get('scr'),
                'width': flowable.get('text')[0].get('width'),
                'height': flowable.get('text')[0].get('height'),
                    }
                self.setting_index_to_flowable(flow_img, numStyle)

        if isinstance(flowable.get('text'), dict):
            obj = flowable.get('text').get('scr')
            width = flowable.get('text').get('width')
            height = flowable.get('text').get('height')
        if isinstance(obj, PmlImage):
            if flowable.get('child'):
                obj = {
                    'text': self.index.get('child') + flowable.get('child') + self.index.get('default')
                                + flowable.get('class') + self.index.get('default') + ' ',
                    'width': width,
                    'height': height,
                }
                self.p = obj
            if flowable.get('parent'):
                obj = {
                    'text': self.index.get('parent') + flowable.get('parent') + self.index.get('default')
                                + flowable.get('class') + self.index.get('default') + ' ',
                    'width': width,
                    'height': height,
                 }
                self.p = obj
            if not flowable.get('child') and not flowable.get('parent'):
                space_over = 0
                if isinstance(flowable.get('text'), list):
                    space_over = self.get_temporal_paragraph(flowable.get('text')[0], numStyle, flowable.get('class'))
                height = space_over + height
                obj = {
                    'text': self.index.get('default') + flowable.get('class') + self.index.get('default') + ' ',
                    'width': width,
                    'height': height + space_over,
                }
                self.p = obj

    def set_flowables(self):
        cont = 0
        num_style = 0
        objects = self.setting_context()
        for object in objects:
            if 'grid' in object:
                for f in object:
                    if isinstance(f, list):
                        for i in f:
                            if i.get('text'):
                                num_style = num_style + 1
                                self.setting_index_to_flowable(i, num_style)
                                if isinstance(i.get('text'), six.text_type):
                                    self.p.style = self.styles[cont]
                                self.flowElements.append(self.p)
                                self.flowElements.append(FrameBreak())
                                if i.get('text') != ' ':
                                    cont = cont + 1
        return self.flowElements

    def get_cols_values(self, flowable):
        if isinstance(flowable, Paragraph):
            result = re.search(r'is-\w+', flowable.text)
            if not result:
                result = re.search(r'col-sm-\w+', flowable.text)
        else:
            result = re.search(r'is-\w+', flowable.get('text'))
            if not result:
                result = re.search(r'col-sm-\w+', flowable.text)
        colName = result.group()
        colNumName = len(colName)
        if colName.startswith('col'):
            colSize = colName[7:colNumName]
        else:
            colSize = colName[3:colNumName]
        values = {
            'colName': colName,
            'colSize': colSize
        }
        return values

    def set_wh_values(self, wh, w, h, parent_column, parent):
        if parent_column:
            wh.append((w, h))
        if parent:
            wh.append((w, h, parent))
        if not parent_column and not parent:
            wh.append((w, h))
        return wh

    def get_wrap_flowables(self):
        flows = self.set_flowables()
        wh = []
        parent_column = None
        parent = None
        cols = 0
        cols_child = 0
        colSize = 0
        cw = 0
        for flow in flows:
            parent_column = None
            parent = None
            if isinstance(flow, Paragraph):
                if flow.text.startswith(self.index.get('parent')):
                    parent = self.searching_index(flow)
                if flow.text.startswith(self.index.get('child')):
                    parent_column = self.searching_index(flow)
                    self.children.append(parent_column)
                cols_values = self.get_cols_values(flow)
                if cols_values.get('colName').startswith('is-') or cols_values.get('colName').startswith('col'):
                    cw = self.get_col_width(cols_values.get('colName'), parent_column)
                    nf = self.clean_text_flowable(flow)
                if cols >= 12:
                    if not parent_column:
                        self.wraps.append(self.next_frame)
                        cols = 0
                if cols_child >= 12:
                    if parent:
                        cols_child = 0
                cols_result = self.cols_increment(parent, parent_column, cols_values, cols_child, cols)
                cols_child = cols_result.get('cols_child')
                cols = cols_result.get('cols')
                if cols <= 12:
                    w, h = nf.wrap(cw, self.doc.height)
                    wh = self.set_wh_values(wh, w, h + 20, parent_column, parent)
                if cols >= 12:
                    self.wraps.append(wh)
                    wh = []
            if isinstance(flow, dict):
                if flow.get('text').startswith(self.index.get('parent')):
                    parent = self.searching_index(flow)
                if flow.get('text').startswith(self.index.get('child')):
                    parent_column = self.searching_index(flow)
                    self.children.append(parent_column)
                cols_values = self.get_cols_values(flow)
                if cols_values.get('colName').startswith('is-') or cols_values.get('colName').startswith('col'):
                    cw = self.get_col_width(cols_values.get('colName'), parent_column)
                    nf = self.clean_text_flowable(flow)
                if cols >= 12:
                    if not parent_column:
                        self.wraps.append(self.next_frame)
                        cols = 0
                if cols_child >= 12:
                    if parent:
                        cols_child = 0
                cols_result = self.cols_increment(parent, parent_column, cols_values, cols_child, cols)
                cols_child = cols_result.get('cols_child')
                cols = cols_result.get('cols')
                if cols <= 12:
                    w, h = cw, flow.get('height')
                    wh = self.set_wh_values(wh, w, h, parent_column, parent)
                if cols >= 12:
                    self.wraps.append(wh)
                    wh = []
        self.get_max(self.wraps)
        return self.wraps

    def create_frames(self, margin_left, margin_top, padingTop, padingBottom):
        self.get_wrap_flowables()
        wid = 0
        mxh = 0
        av = self.doc.height
        space = 0
        temp_width = 0
        children = False
        totalpading = padingTop + padingBottom + 16
        startposition = self.doc._topMargin - totalpading
        next_template_position_list = []
        next_template_index = 1

        for list_values in self.wraps:
            if isinstance(list_values, list):
                mxh = list_values[-1] + totalpading
                if space > 0:
                    space = space + mxh + margin_top
                else:
                    space = space + mxh
                if space >= av:
                    next_template_position_list.append(next_template_index)
                    startposition = self.doc._topMargin - totalpading
                    space = mxh
                    self.page_frames.append(self.frames)
                    self.frames = []
                for values in list_values:
                    if isinstance(values, tuple):
                        if children:
                            wid = wid - temp_width
                            f = Frame(self.doc.leftMargin + wid, startposition - values[1], values[0], values[1]
                                + totalpading,
                                topPadding=padingTop, bottomPadding=padingBottom, showBoundary=0)
                            children = False
                        else:
                            f = Frame(self.doc.leftMargin + wid, startposition - values[1], values[0], values[1]
                                  + totalpading,
                                  topPadding=padingTop, bottomPadding=padingBottom, showBoundary=0)
                        temp_width = values[0]
                        wid = values[0] + wid + margin_left
                        self.frames.append(f)
                        if len(values) == 3:
                            children = True
            next_template_index = next_template_index + 1
            if isinstance(list_values, six.text_type):
                if list_values == self.next_frame:
                    startposition = (startposition) - (mxh + padingTop)
                    wid = 0
        return next_template_position_list

    def getting_templates_datas(self, margin_left=0, margin_top=0, padingTop=0, padingBottom=0, styles=None, static_frame=None):
        self.static_frame = static_frame
        self.styles = styles
        next_template_position_list = self.create_frames(margin_left, margin_top, padingTop, padingBottom)
        self.page_frames.append(self.frames)
        #self.pf.append(self.sf.get('header_content'))
        if self.page_frames:
            contador = 0
            ptl = []
            ids = []
            for f in self.page_frames:
                id = 'id' + str(contador)
                ids.append(id)
                t = PageTemplate(id=id, frames=f)
                contador = contador + 1
                ptl.append(t)
            return ptl, ids, next_template_position_list



