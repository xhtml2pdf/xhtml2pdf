"""
Contract tests for the reportlab API surface xhtml2pdf depends on.

xhtml2pdf reaches deep into reportlab: ``xhtml2pdf/reportlab_paragraph.py`` is a
fork of ``reportlab/platypus/paragraph.py`` and roughly thirty private or
semi-private symbols are imported across the package. None of that is covered by
reportlab's own compatibility promises, so a version bump can break it silently.

These tests pin the coupling down, so that an incompatible reportlab release
fails here -- naming the exact symbol -- rather than somewhere deep inside a
render.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase, skipUnless

import reportlab

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    # tomli only ships in the "test" extra; a missing optional dependency must
    # not take the rest of this module's tests down with it
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"

#: module -> symbols xhtml2pdf imports from it.
REQUIRED_SYMBOLS: dict[str, tuple[str, ...]] = {
    # private / undocumented
    "reportlab.pdfbase._cidfontdata": ("defaultUnicodeEncodings",),
    "reportlab.rl_settings": ("_FUZZ", "warnOnMissingFontGlyphs"),
    "reportlab.rl_config": ("register_reset",),
    "reportlab.lib.abag": ("ABag",),
    "reportlab.lib.utils": (
        "LazyImageReader",
        "flatten",
        "haveImages",
        "open_for_read",
    ),
    "reportlab.lib.textsplit": ("ALL_CANNOT_START", "wordSplit"),
    "reportlab.pdfbase.pdfutils": ("readJPEGInfo",),
    "reportlab.pdfbase.pdfmetrics": (
        "EmbeddedType1Face",
        "Font",
        "getAscentDescent",
        "registerTypeFace",
        "stringWidth",
    ),
    "reportlab.platypus.paraparser": (
        "ABag",
        "ParaFrag",
        "ParaParser",
        "ps2tt",
        "tt2ps",
    ),
    # public, but load-bearing
    "reportlab.pdfgen.canvas": ("Canvas",),
    "reportlab.platypus.doctemplate": (
        "BaseDocTemplate",
        "FrameBreak",
        "IndexingFlowable",
        "NextPageTemplate",
        "PTCycle",
        "PageTemplate",
    ),
    "reportlab.platypus.flowables": (
        "CondPageBreak",
        "Flowable",
        "HRFlowable",
        "KeepInFrame",
        "PageBreak",
        "ParagraphAndImage",
        "Spacer",
    ),
    "reportlab.platypus.frames": ("Frame",),
    "reportlab.platypus.tables": ("Table", "TableStyle"),
    "reportlab.platypus.tableofcontents": ("TableOfContents",),
    "reportlab.pdfbase.pdfform": (
        "buttonFieldRelative",
        "selectFieldRelative",
        "textFieldRelative",
    ),
    "reportlab.pdfbase.cidfonts": ("UnicodeCIDFont",),
    "reportlab.pdfbase.ttfonts": ("TTFont",),
    "reportlab.lib.fonts": ("addMapping",),
    "reportlab.lib.styles": ("ParagraphStyle", "getSampleStyleSheet"),
    "reportlab.lib.colors": ("Color", "toColor"),
    "reportlab.lib.units": ("cm", "inch", "mm"),
    "reportlab.lib.enums": ("TA_CENTER", "TA_JUSTIFY", "TA_LEFT", "TA_RIGHT"),
    "reportlab.lib.pdfencrypt": ("StandardEncryption",),
    "reportlab.graphics.barcode": ("createBarcodeDrawing",),
    "reportlab.graphics.shapes": ("Drawing", "Rect"),
    "reportlab.graphics.charts.barcharts": ("HorizontalBarChart", "VerticalBarChart"),
    "reportlab.graphics.charts.doughnut": ("Doughnut",),
    "reportlab.graphics.charts.linecharts": ("HorizontalLineChart",),
    "reportlab.graphics.charts.piecharts": ("LegendedPie", "Pie"),
    "reportlab.graphics.charts.legends": ("Legend",),
    "reportlab.graphics.charts.textlabels": ("Label",),
    "reportlab.graphics.widgets.markers": ("makeMarker",),
    "reportlab.lib.pagesizes": (
        "A4",
        "ELEVENSEVENTEEN",
        "GOV_LEGAL",
        "GOV_LETTER",
        "HALF_LETTER",
        "JUNIOR_LEGAL",
        "LEDGER",
        "LEGAL",
        "LETTER",
        "TABLOID",
        "landscape",
    ),
}


class ImportContractTest(TestCase):
    def test_every_imported_symbol_exists(self) -> None:
        import importlib

        missing: list[str] = []
        for module_name, symbols in REQUIRED_SYMBOLS.items():
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                missing.append(f"{module_name} (module)")
                continue
            missing.extend(
                f"{module_name}.{symbol}"
                for symbol in symbols
                if not hasattr(module, symbol)
            )
        self.assertEqual([], missing, f"reportlab {reportlab.Version} is missing these")

    def test_ShowBoundaryValue_is_importable_from_either_module(self) -> None:
        """
        It moved to reportlab.pdfgen.canvas in 4.0.9.1 and was dropped from
        reportlab.platypus.frames in 5.0, so xhtml2pdf/context.py tries both.
        """
        try:
            from reportlab.pdfgen.canvas import ShowBoundaryValue
        except ImportError:
            from reportlab.platypus.frames import ShowBoundaryValue
        self.assertTrue(callable(ShowBoundaryValue))

    def test_renderPDF_is_importable(self) -> None:
        from reportlab.graphics import renderPDF

        self.assertTrue(hasattr(renderPDF, "draw"))


class PrivateBehaviourTest(TestCase):
    def test_PTCycle_exposes_next_value(self) -> None:
        """
        ``BaseDocTemplate._setPageTemplate`` reads ``next_value``; xhtml2pdf's
        alternating left/right page templates depend on it.
        """
        from reportlab.platypus.doctemplate import PTCycle

        cycle = PTCycle()
        cycle.extend(["a", "b"])
        self.assertEqual(["a", "b", "a"], [cycle.next_value for _ in range(3)])

    def test_text_object_private_state(self) -> None:
        """``reportlab_paragraph`` drives PDFTextObject internals directly."""
        import io

        from reportlab.pdfgen.canvas import Canvas

        text_object = Canvas(io.BytesIO()).beginText(0, 0)
        for attribute in (
            "_canvas",
            "_fontname",
            "_fontsize",
            "_leading",
            "_setFont",
            "_textOut",
            "_x0",
        ):
            with self.subTest(attribute=attribute):
                self.assertTrue(hasattr(text_object, attribute))

    def test_ParaFrag_accepts_the_clone_monkeypatch(self) -> None:
        """``xhtml2pdf.context`` replaces ``ParaFrag.clone`` globally."""
        from reportlab.platypus.paraparser import ParaFrag

        import xhtml2pdf.context  # noqa: F401  (applies the patch on import)

        frag = ParaFrag(fontName="Helvetica", fontSize=10)
        clone = frag.clone(fontSize=12)
        self.assertEqual("Helvetica", clone.fontName)
        self.assertEqual(12, clone.fontSize)
        self.assertEqual(10, frag.fontSize, "clone must not mutate the original")

    def test_table_exposes_the_private_attributes_the_subclass_uses(self) -> None:
        from reportlab.platypus.tables import Table

        table = Table([["a", "b"], ["c", "d"]])
        for attribute in ("_argW", "_cellvalues", "_listCellGeom"):
            with self.subTest(attribute=attribute):
                self.assertTrue(hasattr(table, attribute))


@skipUnless(tomllib is not None, "needs tomllib (py>=3.11) or the tomli extra")
class DeclaredVersionRangeTest(TestCase):
    """The tox config only *printed* the reportlab version; assert it instead."""

    @staticmethod
    def _declared_specifier() -> str:
        with PYPROJECT.open("rb") as handle:
            data = tomllib.load(handle)
        for requirement in data["project"]["dependencies"]:
            if requirement.replace(" ", "").startswith("reportlab"):
                return requirement
        msg = "reportlab is not declared in [project] dependencies"
        raise AssertionError(msg)

    def test_installed_reportlab_is_within_the_declared_range(self) -> None:
        specifier = self._declared_specifier()

        def as_tuple(text: str) -> tuple[int, ...]:
            return tuple(int(part) for part in text.split(".") if part.isdigit())

        installed = as_tuple(reportlab.Version)
        for clause in specifier.split(",")[0:]:
            clause = clause.replace("reportlab", "").strip()
            if clause.startswith(">="):
                self.assertGreaterEqual(installed, as_tuple(clause[2:]), specifier)
            elif clause.startswith("<"):
                self.assertLess(installed, as_tuple(clause[1:]), specifier)
