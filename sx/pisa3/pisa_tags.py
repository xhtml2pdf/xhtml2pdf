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

__reversion__ = "$Revision: 20 $"
__author__ = "$Author: holtwick $"
__date__ = "$Date: 2007-10-09 12:58:24 +0200 (Di, 09 Okt 2007) $"

from pisa_default import DEFAULT_CSS
from pisa_reportlab import *
from pisa_util import *

from reportlab.graphics.barcode.code39 import Standard39
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus.flowables import *
from reportlab.platypus.paraparser import tt2ps, ABag

from reportlab_paragraph import cleanBlockQuotedText

import reportlab.lib.utils

import os
import pprint
import re
import warnings

import logging
log = logging.getLogger("ho.pisa")

def deprecation(message):
    warnings.warn("<" + message + "> is deprecated!", DeprecationWarning, stacklevel=2)

class pisaTag:

    """
    The default class for a tag definition
    """
    
    def __init__(self, node, attr):
        self.node = node
        self.tag = node.tagName
        self.attr = attr
        
    def start(self, c):
        pass
    
    def end(self, c):
        pass    

class pisaTagBODY(pisaTag):
    
    """
    We can also asume that there is a BODY tag because html5lib 
    adds it for us. Here we take the base font size for later calculations
    in the FONT tag.
    """
    
    def start(self, c):
        c.baseFontSize = c.frag.fontSize
        # print "base font size", c.baseFontSize
        
class pisaTagTITLE(pisaTag):
    def end(self, c):
        c.meta["title"] = c.text
        c.clearFrag()

class pisaTagSTYLE(pisaTag):
    def start(self, c):
        c.addPara()
    def end(self, c):        
        c.clearFrag()

class pisaTagMETA(pisaTag):
    def start(self, c):
        name = self.attr.name.lower()
        if name in ("author" , "subject", "keywords"):
            c.meta[name] = self.attr.content
        
class pisaTagSUP(pisaTag):
    def start(self, c):
        c.frag.super = 1
        
class pisaTagSUB(pisaTag):
    def start(self, c):
        c.frag.sub = 1

class pisaTagA(pisaTag):

    rxLink = re.compile("^(#|[a-z]+\:).*")
    
    def start(self, c):
        attr = self.attr
        # XXX Also support attr.id ?
        if attr.name:
            # Important! Make sure that cbDefn is not inherited by other
            # fragments because of a bug in Reportlab! 
            afrag = c.frag.clone()
            # These 3 lines are needed to fix an error with non internal fonts
            afrag.fontName = "Helvetica"  
            afrag.bold = 0
            afrag.italic =  0 
            afrag.cbDefn = ABag(
                kind="anchor",
                name=attr.name,
                label="anchor")            
            c.fragAnchor.append(afrag)
            c.anchorName.append(attr.name)
        if attr.href and self.rxLink.match(attr.href):            
            c.frag.link = attr.href

    def end(self, c):
        pass   

class pisaTagFONT(pisaTag):

    # Source: http://www.w3.org/TR/CSS21/fonts.html#propdef-font-size
   
    def start(self, c):
        if self.attr["color"] is not None:
            c.frag.textColor = getColor(self.attr["color"])
        if self.attr["face"] is not None:
            c.frag.fontName = c.getFontName(self.attr["face"])
        if self.attr["size"] is not None:
            size = getSize(self.attr["size"], c.frag.fontSize, c.baseFontSize)
            c.frag.fontSize = max(size, 1.0)

    def end(self, c):
        pass
           
class pisaTagP(pisaTag):
    def start(self, c):
        # save the type of tag; it's used in PmlBaseDoc.afterFlowable()
        # to check if we need to add an outline-entry
        # c.frag.tag = self.tag
        if self.attr.align is not None:
            #print self.attr.align, getAlign(self.attr.align)
            c.frag.alignment = getAlign(self.attr.align)

class pisaTagDIV(pisaTagP): pass
class pisaTagH1(pisaTagP): pass
class pisaTagH2(pisaTagP): pass
class pisaTagH3(pisaTagP): pass
class pisaTagH4(pisaTagP): pass
class pisaTagH5(pisaTagP): pass
class pisaTagH6(pisaTagP): pass

def listDecimal(c):
    c.listCounter += 1
    return unicode("%d." % c.listCounter)

_bullet = u"\u2022"
_list_style_type = {
    "none": u"",
    "disc": _bullet,
    "circle": _bullet, # XXX PDF has no equivalent
    "square": _bullet, # XXX PDF has no equivalent
    "decimal": listDecimal,
    "decimal-leading-zero": listDecimal,
    "lower-roman": listDecimal,
    "upper-roman": listDecimal,
    "hebrew": listDecimal,
    "georgian": listDecimal,
    "armenian": listDecimal,
    "cjk-ideographic": listDecimal,
    "hiragana": listDecimal,
    "katakana": listDecimal,
    "hiragana-iroha": listDecimal,
    "katakana-iroha": listDecimal,
    "lower-latin": listDecimal,
    "lower-alpha": listDecimal,
    "upper-latin": listDecimal,
    "upper-alpha": listDecimal,
    "lower-greek": listDecimal,
}

class pisaTagUL(pisaTagP):
    
    def start(self, c):  
        self.counter, c.listCounter = c.listCounter, 0       

    def end(self, c):        
        c.addPara()        
        # XXX Simulate margin for the moment                
        c.addStory(Spacer(width=1, height=c.fragBlock.spaceAfter))
        c.listCounter = self.counter        

class pisaTagOL(pisaTagUL): 
    pass

class pisaTagLI(pisaTag):

    def start(self, c):
        lst = _list_style_type.get(c.frag.listStyleType or "disc", _bullet)
        
        #log.debug("frag %r", c.copyFrag(
        #        text=lst, 
        #        bulletFontName=c.getFontName("helvetica"),
        #        fontName=c.getFontName("helvetica")))
        # c.addFrag("")
        
        #frag = ParaFrag()
        #frag.fontName = frag.bulletFontName = c.getFontName("helvetica")
        #frag.fontSize = c.frag.fontSize
        #c.frag.fontName = c.getFontName("helvetica")
        
        frag = copy.copy(c.frag)
        #print "###", c.frag.fontName
        #frag.fontName = "au_00" # c.getFontName("helvetica")
        #frag.bulletFontName = "au_00" # c.getFontName("helvetica")

        self.offset = 0
        if frag.listStyleImage is not None:
            frag.text = u""
            f = frag.listStyleImage
            if f and (not f.notFound()):                        
                img = PmlImage(
                    f.getData(),
                    width=None,
                    height=None)
                img.drawHeight *= dpi96
                img.drawWidth *= dpi96
                img.pisaZoom = frag.zoom
                img.drawWidth *= img.pisaZoom
                img.drawHeight *= img.pisaZoom
                frag.image = img
                self.offset = max(0, img.drawHeight - c.frag.fontSize)
        else:
            if type(lst) == type(u""):         
                frag.text = lst   
            else:
                # XXX This should be the recent font, but it throws errors in Reportlab!
                frag.text = lst(c)

        # XXX This should usually be done in the context!!!
        frag.fontName = frag.bulletFontName = tt2ps(frag.fontName, frag.bold, frag.italic)        
        c.frag.bulletText = [frag]

    def end(self, c):
        c.fragBlock.spaceBefore += self.offset
        
        #c.fragBlock.bulletText = self.bulletText
        #print 999, self.bulletText
        # c.addPara()
    
class pisaTagBR(pisaTag): 
    
    def start(self, c):
        # print "BR", c.text[-40:]
        c.frag.lineBreak = 1 
        c.addFrag()
        c.fragStrip = True
        del c.frag.lineBreak 
        c.force = True

class pisaTagIMG(pisaTag):
           
    def start(self, c):        
        attr = self.attr        
        if attr.src and (not attr.src.notFound()):
                        
            try:             
                align = attr.align or c.frag.vAlign or "baseline"    
                # print "align", align, attr.align, c.frag.vAlign  
                                
                width = c.frag.width 
                height = c.frag.height

                if attr.width:
                    width = attr.width * dpi96
                if attr.height:
                    height = attr.height * dpi96                    
                
                img = PmlImage(
                    attr.src.getData(),
                    width=None,
                    height=None)   
                               
                img.pisaZoom = c.frag.zoom

                img.drawHeight *= dpi96
                img.drawWidth *= dpi96
                            
                if (width is None) and (height is not None):
                    factor = float(height) / img.drawHeight
                    img.drawWidth *= factor
                    img.drawHeight = height
                elif (height is None) and (width is not None):
                    factor = float(width) / img.drawWidth
                    img.drawHeight *= factor
                    img.drawWidth = width
                elif (width is not None) and (height is not None):
                    img.drawWidth = width
                    img.drawHeight = height
                    
                img.drawWidth *= img.pisaZoom
                img.drawHeight *= img.pisaZoom
                
                img.spaceBefore = c.frag.spaceBefore
                img.spaceAfter = c.frag.spaceAfter

                # print "image", id(img), img.drawWidth, img.drawHeight
                                  
                '''
                TODO:

                - Apply styles
                - vspace etc.
                - Borders
                - Test inside tables
                '''

                c.force = True
                if align in ["left", "right"]:

                    c.image = img
                    c.imageData = dict(
                        align=align
                        )
                                        
                else:

                    # Important! Make sure that cbDefn is not inherited by other
                    # fragments because of a bug in Reportlab!
                    # afrag = c.frag.clone()

                    valign = align
                    if valign in ["texttop"]:
                        valign = "top"
                    elif valign in ["absmiddle"]:
                        valign = "middle"
                    elif valign in ["absbottom", "baseline"]:
                        valign = "bottom"

                    afrag = c.frag.clone()
                    afrag.text = ""
                    afrag.fontName="Helvetica" # Fix for a nasty bug!!!
                    afrag.cbDefn = ABag(
                        kind="img",
                        image=img, #.getImage(), # XXX Inline?
                        valign=valign,
                        fontName="Helvetica", 
                        fontSize=img.drawHeight,
                        width=img.drawWidth,
                        height=img.drawHeight)
                    # print "add frag", id(afrag), img.drawWidth, img.drawHeight
                    c.fragList.append(afrag)
                    c.fontSize = img.drawHeight                                    
                    
            except Exception:
                log.warn(c.warning("Error in handling image"), exc_info=1)
        else:
            log.warn(c.warning("Need a valid file name!"))
            
class pisaTagHR(pisaTag):

    def start(self, c):
        c.addPara()
        c.addStory(HRFlowable(
            color=self.attr.color,
            thickness=self.attr.size,
            width="100%",
            spaceBefore=c.frag.spaceBefore,
            spaceAfter=c.frag.spaceAfter
            ))

# --- Forms

import pisa_reportlab

if 0:
    
    class pisaTagINPUT(pisaTag):
    
        def _render(self, c, attr):
            width = 10
            height = 10
            if attr.type == "text":
                width = 100
                height = 12            
            c.addStory(pisa_reportlab.PmlInput(attr.name,
                type=attr.type,
                default=attr.value,
                width=width,
                height=height,
                ))
            
        def end(self, c):        
            c.addPara()
            attr = self.attr
            if attr.name:
                self._render(c, attr)                            
            c.addPara()
    
    class pisaTagTEXTAREA(pisaTagINPUT):
               
        def _render(self, c, attr):
            c.addStory(pisa_reportlab.PmlInput(attr.name,
                default="",
                width=100,
                height=100))
    
    class pisaTagSELECT(pisaTagINPUT):
        
        def start(self, c):
            c.select_options = ["One", "Two", "Three"]
            
        def _render(self, c, attr):
            c.addStory(pisa_reportlab.PmlInput(attr.name,
                type="select",
                default=c.select_options[0],
                options=c.select_options,
                width=100,
                height=40))
            c.select_options = None
    
    class pisaTagOPTION(pisaTag):
               
        pass

# ============================================

class pisaTagPDFNEXTPAGE(pisaTag):    
    """
    <pdf:nextpage name="" />
    """
    def start(self, c):
        # deprecation("pdf:nextpage")
        c.addPara()
        if self.attr.name:
            c.addStory(NextPageTemplate(self.attr.name))
        c.addStory(PageBreak())
        
class pisaTagPDFNEXTTEMPLATE(pisaTag):    
    """
    <pdf:nexttemplate name="" />
    """
    def start(self, c):       
        # deprecation("pdf:frame")
        c.addStory(NextPageTemplate(self.attr["name"]))
    
class pisaTagPDFNEXTFRAME(pisaTag):    
    """
    <pdf:nextframe name="" />
    """
    def start(self, c):
        c.addPara()
        c.addStory(FrameBreak())

class pisaTagPDFSPACER(pisaTag):    
    """
    <pdf:spacer height="" />
    """
    def start(self, c):
        c.addPara()
        c.addStory(Spacer(1, self.attr.height))

class pisaTagPDFPAGENUMBER(pisaTag):    
    """
    <pdf:pagenumber offset="" example="" />
    """   
    def start(self, c):
        c.frag.pageNumber = True 
        c.frag.offset = self.attr.offset
        c.addFrag(self.attr.example)
        c.frag.pageNumber = False
        
class pisaTagPDFTOC(pisaTag):    
    """
    <pdf:toc />
    """   
    def end(self, c):
        c.multiBuild = True
        c.addTOC()        
        
class pisaTagPDFFRAME(pisaTag):    
    """
    <pdf:frame name="" static box="" />
    """
    def start(self, c):
        deprecation("pdf:frame")
        attrs = self.attr       

        name = attrs["name"]        
        if name is None:
            name = "frame%d" % c.UID()
        
        x, y, w, h = attrs.box
        self.frame = Frame(
                x, y, w, h,
                id=name,
                leftPadding=0,
                rightPadding=0,
                bottomPadding=0,
                topPadding=0,
                showBoundary=attrs.border)
        
        self.static = False
        if self.attr.static:
            self.static = True
            c.addPara()
            self.story = c.swapStory()
        else:
            c.frameList.append(self.frame)

    def end(self, c):
        if self.static:
            c.addPara()
            self.frame.pisaStaticStory = c.story
            c.frameStaticList.append(self.frame)
            c.swapStory(self.story)

class pisaTagPDFTEMPLATE(pisaTag):    
    """
    <pdf:template name="" static box="" >
        <pdf:frame...>
    </pdf:template>
    """
    def start(self, c):
        deprecation("pdf:template")
        attrs = self.attr    
        #print attrs
        name = attrs["name"]
        c.frameList = []
        c.frameStaticList = []
        if c.templateList.has_key(name):
            log.warn(c.warning("template '%s' has already been defined", name))
       
        '''
        self.oldpagesize = A4 # self._pagesize

        self._pagesize = PML_PAGESIZES[attrs.format]
        if attrs.orientation is not None:
            if attrs.orientation == "landscape":
                self._pagesize = landscape(self._pagesize)
            elif attrs.orientation == "portrait":
                self._pagesize = portrait(self._pagesize)
        '''
        
        # self._drawing = PmlPageDrawing(self._pagesize)

    def end(self, c):
        attrs = self.attr 
        name = attrs["name"]
        if len(c.frameList) <= 0:
            log.warn(c.warning("missing frame definitions for template"))
            
        pt = PmlPageTemplate(
            id=name,
            frames=c.frameList,
            pagesize=A4,
            ) 
        pt.pisaStaticList = c.frameStaticList
        pt.pisaBackgroundList = c.pisaBackgroundList
        pt.pisaBackground = self.attr.background
        
        # self._pagesize)
        # pt.pml_statics = self._statics
        # pt.pml_draw = self._draw
        # pt.pml_drawing = self._drawing
        # pt.pml_background = attrs.background
        # pt.pml_bgstory = self._bgstory

        c.templateList[name] = pt
        c.template = None
        c.frameList = []
        c.frameStaticList = []

class pisaTagPDFFONT(pisaTag):    
    """
    <pdf:fontembed name="" src="" />
    """
    def start(self, c):        
        deprecation("pdf:font")
        c.loadFont(self.attr.name, self.attr.src, self.attr.encoding)

class pisaTagPDFBARCODE(pisaTag):
    """
    <pdf:barcode value="" align="">
    """
    def start(self, c):
        c.addPara()
        attr = self.attr       
        bc = Standard39()
        bc.value = attr.value
        bc.barHeight = 0.5 * inch
        bc.lquiet = 0 # left padding
        bc.rquiet = 0 # left padding
        bc.hAlign = attr.align.upper()
        c.addStory(bc)
        c.addPara() 
