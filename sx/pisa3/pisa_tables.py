# -*- coding: ISO-8859-1 -*-

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


__reversion__ = "$Revision: 20 $"
__author__ = "$Author: holtwick $"
__date__ = "$Date: 2007-10-09 12:58:24 +0200 (Di, 09 Okt 2007) $"

from pisa_tags import pisaTag
from pisa_util import *
from pisa_reportlab import PmlTable, TableStyle, PmlKeepInFrame

import copy
import sys

import logging
log = logging.getLogger("ho.pisa")
            
def _width(value=None):
    if value is None:
        return None
    value = str(value)
    if value.endswith("%"):
        return value
    return getSize(value)

class TableData:

    def __init__(self):
        self.data = []
        self.styles = []
        self.span = []
        self.mode = ""
        self.padding = 0
        self.col = 0
        # self.c = None

    def add_cell(self, data=None):
        self.col += 1
        self.data[len(self.data) - 1].append(data)

    def add_style(self, data):
        # print self.mode, data
        # Do we have color and 
        # width = data[3]
        #if data[0].startswith("LINE"):
        #    color = data[4]
        #    if color is None:
        #        return
        self.styles.append(copy.copy(data))

    def add_empty(self, x, y):
        self.span.append((x, y))

    def get_data(self):
        data = self.data
        for x, y in self.span:
            try:
                data[y].insert(x, '')
            except:
                pass
        return data
   
    def add_cell_styles(self, c, begin, end, mode="td"):
        def getColor(a, b): 
            return a
        self.mode = mode.upper()
        if c.frag.backColor and mode != "tr": # XXX Stimmt das so?
            self.add_style(('BACKGROUND', begin, end, c.frag.backColor))
            # print 'BACKGROUND', begin, end, c.frag.backColor
        if 0:
            log.debug("%r", (
                begin,
                end,
                c.frag.borderTopWidth,
                c.frag.borderTopStyle,
                c.frag.borderTopColor,
                c.frag.borderBottomWidth,
                c.frag.borderBottomStyle,
                c.frag.borderBottomColor,
                c.frag.borderLeftWidth,
                c.frag.borderLeftStyle,
                c.frag.borderLeftColor,
                c.frag.borderRightWidth,
                c.frag.borderRightStyle,
                c.frag.borderRightColor,
                ))
        if getBorderStyle(c.frag.borderTopStyle) and c.frag.borderTopWidth and c.frag.borderTopColor is not None:
            self.add_style(('LINEABOVE', begin, (end[0], begin[1]),
                c.frag.borderTopWidth,
                c.frag.borderTopColor,
                "squared"))
        if getBorderStyle(c.frag.borderLeftStyle) and c.frag.borderLeftWidth and c.frag.borderLeftColor is not None:
            self.add_style(('LINEBEFORE', begin, (begin[0], end[1]),
                c.frag.borderLeftWidth,
                c.frag.borderLeftColor,
                "squared"))
        if getBorderStyle(c.frag.borderRightStyle) and c.frag.borderRightWidth and c.frag.borderRightColor is not None:
            self.add_style(('LINEAFTER', (end[0], begin[1]), end,
                c.frag.borderRightWidth,
                c.frag.borderRightColor,
                "squared"))
        if getBorderStyle(c.frag.borderBottomStyle) and c.frag.borderBottomWidth and c.frag.borderBottomColor is not None:
            self.add_style(('LINEBELOW', (begin[0], end[1]), end,
                c.frag.borderBottomWidth,
                c.frag.borderBottomColor,
                "squared"))
        self.add_style(('LEFTPADDING', begin, end, c.frag.paddingLeft or self.padding))
        self.add_style(('RIGHTPADDING', begin, end, c.frag.paddingRight or self.padding))
        self.add_style(('TOPPADDING', begin, end, c.frag.paddingTop or self.padding))
        self.add_style(('BOTTOMPADDING', begin, end, c.frag.paddingBottom or self.padding))

class pisaTagTABLE(pisaTag):
    
    def start(self, c):
        c.addPara()
    
        attrs = self.attr
        
        # Swap table data
        c.tableData, self.tableData = TableData(), c.tableData
        tdata = c.tableData

        # border
        #tdata.border = attrs.border
        #tdata.bordercolor = attrs.bordercolor

        begin = (0, 0)
        end = (-1, - 1)
            
        if attrs.border and attrs.bordercolor:
            frag = c.frag
            frag.borderLeftWidth = attrs.border
            frag.borderLeftColor = attrs.bordercolor
            frag.borderLeftStyle = "solid"
            frag.borderRightWidth = attrs.border
            frag.borderRightColor = attrs.bordercolor
            frag.borderRightStyle = "solid"
            frag.borderTopWidth = attrs.border
            frag.borderTopColor = attrs.bordercolor
            frag.borderTopStyle = "solid"
            frag.borderBottomWidth = attrs.border
            frag.borderBottomColor = attrs.bordercolor
            frag.borderBottomStyle = "solid"

            # tdata.add_style(("GRID", begin, end, attrs.border, attrs.bordercolor))
        
        tdata.padding = attrs.cellpadding
        
        #if 0: #attrs.cellpadding:
        #    tdata.add_style(('LEFTPADDING', begin, end, attrs.cellpadding))
        #    tdata.add_style(('RIGHTPADDING', begin, end, attrs.cellpadding))
        #    tdata.add_style(('TOPPADDING', begin, end, attrs.cellpadding))
        #    tdata.add_style(('BOTTOMPADDING', begin, end, attrs.cellpadding))
            
        # alignment
        #~ tdata.add_style(('VALIGN', (0,0), (-1,-1), attrs.valign.upper()))

        # Set Border and padding styles
        
        tdata.add_cell_styles(c, (0, 0), (-1, - 1), "table")

        # bgcolor
        #if attrs.bgcolor is not None:
        #    tdata.add_style(('BACKGROUND', (0, 0), (-1, -1), attrs.bgcolor))

        tdata.align = attrs.align.upper()
        tdata.col = 0
        tdata.row = 0        
        tdata.colw = []
        tdata.rowh = []
        tdata.repeat = attrs.repeat
        tdata.width = _width(attrs.width)

        # self.tabdata.append(tdata)

    def end(self, c):
        tdata = c.tableData
        data = tdata.get_data()        
        
        # Add missing columns so that each row has the same count of columns
        # This prevents errors in Reportlab table
        
        try:
            maxcols = max([len(row) for row in data] or [0])
        except ValueError:
            log.warn(c.warning("<table> rows seem to be inconsistent"))
            maxcols = [0]

        for i, row in enumerate(data):
            data[i] += [''] * (maxcols - len(row))

        try:
            if tdata.data:
                # log.debug("Table sryles %r", tdata.styles)
                t = PmlTable(
                    data,
                    colWidths=tdata.colw,
                    rowHeights=tdata.rowh,
                    # totalWidth = tdata.width,
                    splitByRow=1,
                    # repeatCols = 1,
                    repeatRows=tdata.repeat,
                    hAlign=tdata.align,
                    vAlign='TOP',
                    style=TableStyle(tdata.styles))
                t.totalWidth = _width(tdata.width)
                t.spaceBefore = c.frag.spaceBefore
                t.spaceAfter = c.frag.spaceAfter
                
                # XXX Maybe we need to copy some more properties?
                t.keepWithNext = c.frag.keepWithNext
                # t.hAlign = tdata.align
                c.addStory(t)
            else:
                log.warn(c.warning("<table> is empty"))
        except:            
            log.warn(c.warning("<table>"), exc_info=1)

        # Cleanup and re-swap table data
        c.clearFrag()
        c.tableData, self.tableData = self.tableData, None
    
class pisaTagTR(pisaTag):
    
    def start(self, c):            
        tdata = c.tableData
        row = tdata.row
        begin = (0, row)
        end = (-1, row)
        
        tdata.add_cell_styles(c, begin, end, "tr")       
        c.frag.vAlign = self.attr.valign or c.frag.vAlign
          
        tdata.col = 0
        tdata.data.append([])

    def end(self, c):
        c.tableData.row += 1        

class pisaTagTD(pisaTag):
    
    def start(self, c):

        if self.attr.align is not None:
            #print self.attr.align, getAlign(self.attr.align)
            c.frag.alignment = getAlign(self.attr.align)
            
        c.clearFrag()
        self.story = c.swapStory()
        # print "#", len(c.story)
        
        attrs = self.attr
        
        tdata = c.tableData

        cspan = attrs.colspan
        rspan = attrs.rowspan

        row = tdata.row
        col = tdata.col
        while 1:
            for x, y in tdata.span:
                if x == col and y == row:
                    col += 1
                    tdata.col += 1
            break
        #cs = 0
        #rs = 0

        begin = (col, row)
        end = (col, row)
        if cspan:
            end = (end[0] + cspan - 1, end[1])
        if rspan:
            end = (end[0], end[1] + rspan - 1)
        if begin != end:
            #~ print begin, end
            tdata.add_style(('SPAN', begin, end))
            for x in range(begin[0], end[0] + 1):
                for y in range(begin[1], end[1] + 1):
                    if x != begin[0] or y != begin[1]:
                        tdata.add_empty(x, y)

        # Set Border and padding styles
        tdata.add_cell_styles(c, begin, end, "td")

        # Calculate widths
        # Add empty placeholders for new columns
        if (col + 1) > len(tdata.colw):
            tdata.colw = tdata.colw + ((col + 1 - len(tdata.colw)) * [_width()])
        # Get value of with, if no spanning
        if not cspan:
            # print c.frag.width
            width = c.frag.width or self.attr.width #self._getStyle(None, attrs, "width", "width", mode)
            # If is value, the set it in the right place in the arry
            # print width, _width(width)
            if width is not None:
                tdata.colw[col] = _width(width)

        # Calculate heights
        if row + 1 > len(tdata.rowh):
            tdata.rowh = tdata.rowh + ((row + 1 - len(tdata.rowh)) * [_width()])
        if not rspan:
            height = None #self._getStyle(None, attrs, "height", "height", mode)
            if height is not None:
                tdata.rowh[row] = _width(height)
                tdata.add_style(('FONTSIZE', begin, end, 1.0))
                tdata.add_style(('LEADING', begin, end, 1.0))

        # Vertical align      
        valign = self.attr.valign or c.frag.vAlign
        if valign is not None:
            tdata.add_style(('VALIGN', begin, end, valign.upper()))

        # Reset border, otherwise the paragraph block will have borders too
        frag = c.frag
        frag.borderLeftWidth = 0
        frag.borderLeftColor = None
        frag.borderLeftStyle = None
        frag.borderRightWidth = 0
        frag.borderRightColor = None
        frag.borderRightStyle = None
        frag.borderTopWidth = 0
        frag.borderTopColor = None
        frag.borderTopStyle = None
        frag.borderBottomWidth = 0
        frag.borderBottomColor = None
        frag.borderBottomStyle = None

    def end(self, c):
        tdata = c.tableData
        
        c.addPara()
        cell = c.story
        
        # Handle empty cells, they otherwise collapse
        #if not cell:
        #    cell = ' '        
            
        # Keep in frame if needed since Reportlab does no split inside of cells
        if (not c.frag.insideStaticFrame) and (c.frag.keepInFrameMode is not None):
            
            # tdata.keepinframe["content"] = cell
            cell = PmlKeepInFrame(
                maxWidth=0,
                maxHeight=0,
                mode=c.frag.keepInFrameMode,
                content=cell)

        c.swapStory(self.story)
              
        tdata.add_cell(cell)
        
class pisaTagTH(pisaTagTD):
    pass

'''
    end_th = end_td

    def start_keeptogether(self, attrs):
        self.story.append([])
        self.next_para()

    def end_keeptogether(self):
        if not self.story[-1]:
            self.add_noop()
        self.next_para()
        s = self.story.pop()
        self.add_story(KeepTogether(s))

    def start_keepinframe(self, attrs):
        self.story.append([])
        self.keepinframe = {
            "maxWidth": attrs["maxwidth"],
            "maxHeight": attrs["maxheight"],
            "mode": attrs["mode"],
            "name": attrs["name"],
            "mergeSpace": attrs["mergespace"]
            }
        # print self.keepinframe
        self.next_para()

    def end_keepinframe(self):
        if not self.story[-1]:
            self.add_noop()
        self.next_para()
        self.keepinframe["content"] = self.story.pop()
        self.add_story(KeepInFrame(**self.keepinframe))
'''