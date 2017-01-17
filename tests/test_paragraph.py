# -*- coding: utf-8
from __future__ import unicode_literals, absolute_import

import copy
import re
import unittest

from reportlab.lib.colors import Color
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate

from xhtml2pdf.paragraph import Style, Word, Space, Text, BoxBegin, BoxEnd, LineBreak, Paragraph


class LegacyParagraphTests(unittest.TestCase):

    def test_legacy(self):
        """Test function coming from paragraph.__main__"""
        ALIGNMENTS = (TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY)

        TEXT = """
        Lörem ipsum dolor sit amet, consectetur adipisicing elit,
        sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
        Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi
        ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit
        in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
        Excepteur sint occaecat cupidatat non proident, sunt in culpa qui
        officia deserunt mollit anim id est laborum. Lorem ipsum dolor sit amet,
        consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore
        et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation
        ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure
        dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat
        nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt
        in culpa qui officia deserunt mollit anim id est laborum. Lorem ipsum
        dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor
        incididunt ut labore et dolore magna aliqua.
        """.strip()

        def textGenerator(data, fn, fs):
            i = 1
            for word in re.split('\s+', data):
                if word:
                    yield Word(
                        text="[%d|%s]" % (i, word),
                        fontName=fn,
                        fontSize=fs
                    )
                    yield Space(
                        fontName=fn,
                        fontSize=fs
                    )

        def createText(data, fn, fs):
            text = Text(list(textGenerator(data, fn, fs)))
            return text

        def makeBorder(width, style="solid", color=Color(1, 0, 0)):
            return dict(
                borderLeftColor=color,
                borderLeftWidth=width,
                borderLeftStyle=style,
                borderRightColor=color,
                borderRightWidth=width,
                borderRightStyle=style,
                borderTopColor=color,
                borderTopWidth=width,
                borderTopStyle=style,
                borderBottomColor=color,
                borderBottomWidth=width,
                borderBottomStyle=style
            )

        def test():
            doc = SimpleDocTemplate("test.pdf")
            story = []

            style = Style(fontName="Helvetica", textIndent=24.0)
            fn = style["fontName"]
            fs = style["fontSize"]
            sampleText1 = createText(TEXT[:100], fn, fs)
            sampleText2 = createText(TEXT[100:], fn, fs)

            text = Text(sampleText1 + [
                Space(
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="TrennbarTrennbar",
                    pairs=[("Trenn-", "barTrennbar")],
                    fontName=fn,
                    fontSize=fs),
                Space(
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Normal",
                    color=Color(1, 0, 0),
                    fontName=fn,
                    fontSize=fs),
                Space(
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="gGrößer",
                    fontName=fn,
                    fontSize=fs * 1.5),
                Space(
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Bold",
                    fontName="Times-Bold",
                    fontSize=fs),
                Space(
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="jItalic",
                    fontName="Times-Italic",
                    fontSize=fs),
                Space(
                    fontName=fn,
                    fontSize=fs),

                # <span style="border: 1px solid red;">ipsum <span style="border: 1px solid green; padding: 4px;
                # padding-left: 20px; background: yellow; margin-bottom: 8px; margin-left: 10px;">
                # Lo<font size="12pt">re</font>m</span> <span style="background:blue; height: 30px;">ipsum</span>
                # Lorem</span>

                BoxBegin(
                    fontName=fn,
                    fontSize=fs,
                    **makeBorder(0.5, "solid", Color(0, 1, 0))),
                Word(
                    text="Lorem",
                    fontName="Times-Bold",
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName="Times-Bold",
                    fontSize=fs),
                Space(
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Space(
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Space(
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Space(
                    fontName=fn,
                    fontSize=fs),
                BoxBegin(
                    fontName=fn,
                    fontSize=fs,
                    backgroundColor=Color(1, 1, 0),
                    **makeBorder(1, "solid", Color(1, 0, 0))),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                BoxEnd(),
                Space(
                    fontName=fn,
                    fontSize=fs),
                Word(
                    text="Lorem",
                    fontName=fn,
                    fontSize=fs),
                Space(
                    fontName=fn,
                    fontSize=fs),
                BoxEnd(),

                LineBreak(
                    fontName=fn,
                    fontSize=fs),
                LineBreak(
                    fontName=fn,
                    fontSize=fs),
            ] + sampleText2)

            story.append(Paragraph(
                copy.copy(text),
                style,
                debug=0))

            for i in range(10):
                style = copy.deepcopy(style)
                style["textAlign"] = ALIGNMENTS[i % 4]
                text = createText(("(%d) " % i) + TEXT, fn, fs)
                story.append(Paragraph(
                    copy.copy(text),
                    style,
                    debug=0))
            doc.build(story)

        test()
