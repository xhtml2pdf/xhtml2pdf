"""
Coverage for ``xhtml2pdf.reportlab_paragraph``.

That module is a 2000-line fork of reportlab's ``platypus/paragraph.py`` and is
the project's single largest coupling surface to reportlab internals, yet it had
no dedicated test file -- it was only exercised incidentally whenever some other
test happened to render text.
"""

from __future__ import annotations

import io
from unittest import TestCase

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import SimpleDocTemplate

from xhtml2pdf.reportlab_paragraph import (
    Paragraph,
    _handleBulletWidth,
    _split_blParaHard,
    _split_blParaSimple,
    cleanBlockQuotedText,
    split,
    strip,
)

LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat."
)


def style(**kwargs) -> ParagraphStyle:
    defaults = {"name": "test", "fontName": "Helvetica", "fontSize": 10, "leading": 12}
    defaults.update(kwargs)
    return ParagraphStyle(**defaults)


class HelpersTest(TestCase):
    def test_split_returns_utf8_words(self) -> None:
        self.assertEqual([b"a", b"b"], split("a b"))
        self.assertEqual([b"a", b"b"], split(b"a b"))

    def test_split_keeps_non_breaking_spaces_joined(self) -> None:
        """
        str.split(None) treats U+00A0 as whitespace; a non-breaking space must
        not become a line-break opportunity, hence the dedicated regex branch.
        """
        self.assertEqual([b"a\xc2\xa0b"], split("a\xa0b"))
        self.assertEqual([b"a", b"b"], split("a b"))

    def test_strip_accepts_str_and_bytes(self) -> None:
        self.assertEqual(b"a", strip("  a  "))
        self.assertEqual(b"a", strip(b"  a  "))

    def test_cleanBlockQuotedText(self) -> None:
        # split()/strip() in this module work in utf-8 bytes
        self.assertEqual(b"a b c", cleanBlockQuotedText("\n  a\n  b\n  c\n "))

    def test_handleBulletWidth_indents_the_first_line(self) -> None:
        widths = [100, 100]
        para_style = style(
            bulletFontName="Helvetica", bulletFontSize=10, bulletIndent=0
        )
        _handleBulletWidth("•", para_style, widths)
        self.assertLess(widths[0], 100, "first line was not indented for the bullet")
        self.assertEqual(100, widths[1], "later lines must keep the full width")

    def test_handleBulletWidth_ignores_empty_bullets(self) -> None:
        widths = [100, 100]
        _handleBulletWidth("", style(), widths)
        self.assertEqual([100, 100], widths)


class BreakLinesTest(TestCase):
    @staticmethod
    def _para(text: str = LOREM, **style_kwargs) -> Paragraph:
        return Paragraph(text, style(**style_kwargs))

    def test_wrap_reports_a_positive_height(self) -> None:
        para = self._para()
        width, height = para.wrap(200, 1000)
        self.assertEqual(200, width)
        self.assertGreater(height, 0)

    def test_narrower_width_produces_more_lines(self) -> None:
        wide = self._para()
        wide.wrap(400, 1000)
        narrow = self._para()
        narrow.wrap(120, 1000)
        self.assertGreater(len(narrow.blPara.lines), len(wide.blPara.lines))

    def test_height_matches_lines_times_leading(self) -> None:
        para = self._para(leading=14)
        _, height = para.wrap(200, 1000)
        self.assertAlmostEqual(len(para.blPara.lines) * 14, height, places=5)

    def test_every_line_fits_the_available_width(self) -> None:
        para = self._para()
        para.wrap(200, 1000)
        for extra_space, _words in para.blPara.lines:
            self.assertGreaterEqual(
                extra_space, -1e-6, "a line overflowed the available width"
            )

    def test_unbreakable_word_overflows_on_a_single_line(self) -> None:
        """
        This fork predates reportlab's ``splitLongWords``: a word wider than the
        frame is laid out on one overflowing line rather than being broken.
        """
        para = Paragraph("A" * 200, style())
        para.wrap(60, 1000)
        self.assertEqual(1, len(para.blPara.lines))
        self.assertLess(para.blPara.lines[0][0], 0, "expected a negative extraSpace")

    def test_alignments_all_lay_out(self) -> None:
        for alignment in (TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY):
            with self.subTest(alignment=alignment):
                para = self._para(alignment=alignment)
                _, height = para.wrap(200, 1000)
                self.assertGreater(height, 0)

    def test_getPlainText_roundtrips(self) -> None:
        """
        The bracket in ``"".join([frag.text] for ...)`` made this join a
        sequence of one-element lists, so it raised TypeError on every call.
        """
        para = self._para("hello <b>bold</b> world")
        para.wrap(200, 1000)
        self.assertEqual("hello bold world", para.getPlainText())

    def test_getPlainText_without_frags(self) -> None:
        para = self._para("x")
        del para.frags
        self.assertEqual("", para.getPlainText())

    def test_minWidth_is_the_widest_word(self) -> None:
        para = Paragraph("a bbbbbbbbbb c", style())
        self.assertAlmostEqual(
            stringWidth("bbbbbbbbbb", "Helvetica", 10), para.minWidth(), places=5
        )

    def test_actual_line_widths_do_not_exceed_the_frame(self) -> None:
        para = self._para()
        para.wrap(200, 1000)
        for line_width in para.getActualLineWidths0():
            self.assertLessEqual(line_width, 200 + 1e-6)


class SplitTest(TestCase):
    def test_split_returns_two_paragraphs(self) -> None:
        para = Paragraph(LOREM, style())
        para.wrap(200, 1000)
        total_lines = len(para.blPara.lines)

        head, tail = para.split(200, 24)  # room for two lines only
        head.wrap(200, 24)
        tail.wrap(200, 1000)
        self.assertEqual(2, len(head.blPara.lines))
        self.assertEqual(total_lines, len(head.blPara.lines) + len(tail.blPara.lines))

    def test_split_with_no_room_returns_nothing(self) -> None:
        para = Paragraph(LOREM, style())
        para.wrap(200, 1000)
        self.assertEqual([], para.split(200, 1))

    def test_split_blParaSimple_collects_the_words_of_the_slice(self) -> None:
        para = Paragraph(LOREM, style())
        para.wrap(200, 1000)
        self.assertEqual(0, para.blPara.kind, "expected the simple layout")

        expected = sum(len(line[1]) for line in para.blPara.lines[:2])
        frags = _split_blParaSimple(para.blPara, 0, 2)
        self.assertEqual(1, len(frags))
        self.assertEqual(expected, len(frags[0].words))

    def test_split_blParaHard_collects_the_words_of_the_slice(self) -> None:
        para = Paragraph(f"<b>{LOREM}</b> and <i>more</i>", style())
        para.wrap(200, 1000)
        self.assertEqual(1, para.blPara.kind, "expected the multi-frag layout")

        expected = sum(len(line.words) for line in para.blPara.lines[:2])
        self.assertEqual(expected, len(_split_blParaHard(para.blPara, 0, 2)))


class RenderTest(TestCase):
    def test_paragraph_renders_into_a_pdf(self) -> None:
        target = io.BytesIO()
        doc = SimpleDocTemplate(target)
        doc.build([Paragraph(LOREM, style()) for _ in range(20)])
        self.assertTrue(target.getvalue().startswith(b"%PDF"))

    def test_bulleted_paragraph_renders(self) -> None:
        target = io.BytesIO()
        doc = SimpleDocTemplate(target)
        doc.build(
            [
                Paragraph(
                    LOREM,
                    style(bulletFontName="Helvetica", bulletFontSize=10),
                    bulletText="•",
                )
            ]
        )
        self.assertTrue(target.getvalue().startswith(b"%PDF"))
