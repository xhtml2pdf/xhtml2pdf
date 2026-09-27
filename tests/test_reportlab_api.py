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

import ast
import importlib
import inspect
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
PACKAGE = Path(__file__).parent.parent / "xhtml2pdf"

#: module -> symbols xhtml2pdf imports from it.
REQUIRED_SYMBOLS: dict[str, tuple[str, ...]] = {
    # private / undocumented
    "reportlab.pdfbase._cidfontdata": ("defaultUnicodeEncodings",),
    "reportlab.pdfbase._glyphlist": ("_glyphname2unicode",),
    "reportlab.rl_settings": ("_FUZZ", "warnOnMissingFontGlyphs"),
    "reportlab.rl_config": ("register_reset",),
    "reportlab.lib.abag": ("ABag",),
    "reportlab.lib.utils": (
        "ImageReader",
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
    "reportlab": ("rl_settings",),
    "reportlab.graphics": ("renderPDF",),
    "reportlab.lib": ("pdfencrypt",),
    "reportlab.pdfbase": ("pdfform", "pdfmetrics"),
    "reportlab.pdfgen.canvas": ("Canvas", "FILL_EVEN_ODD"),
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
        "KeepTogether",
        "PageBreak",
        "ParagraphAndImage",
        "Spacer",
    ),
    "reportlab.platypus.frames": ("Frame",),
    "reportlab.platypus.paragraph": ("Paragraph",),
    # _SPECIALROWS is private: the names reportlab gives the rows a split adds
    "reportlab.platypus.tables": ("_SPECIALROWS", "Table", "TableStyle"),
    "reportlab.platypus.tableofcontents": ("TableOfContents", "drawPageNumbers"),
    "reportlab.pdfbase.pdfform": (
        "buttonFieldRelative",
        "selectFieldRelative",
        "textFieldRelative",
    ),
    "reportlab.pdfbase.cidfonts": ("UnicodeCIDFont",),
    "reportlab.pdfbase.ttfonts": ("TTFont",),
    "reportlab.lib.fonts": ("addMapping", "tt2ps"),
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
        *(f"{series}{n}" for series in "ABC" for n in range(11)),
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


def _optional(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Whether an import sits in a ``try`` that catches ImportError."""
    while node in parents:
        node = parents[node]
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                names = (
                    handler.type.elts
                    if isinstance(handler.type, ast.Tuple)
                    else [handler.type]
                )
                if any(
                    isinstance(name, ast.Name)
                    and name.id in {"ImportError", "ModuleNotFoundError"}
                    for name in names
                ):
                    return True
    return False


def _package_reportlab_imports() -> list[tuple[str, str, str]]:
    """(module, name, file) for each non-optional reportlab import."""
    found: list[tuple[str, str, str]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.split(".")[0] == "reportlab"
                and not _optional(node, parents)
            ):
                found.extend(
                    (node.module, alias.name, path.name) for alias in node.names
                )
    return found


def _resolves(module, symbol: str) -> bool:
    """``from module import symbol`` works: an attribute, or a submodule."""
    if hasattr(module, symbol):
        return True
    try:
        importlib.import_module(f"{module.__name__}.{symbol}")
    except ImportError:
        return False
    return True


class ImportContractTest(TestCase):
    def test_every_imported_symbol_exists(self) -> None:
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
                if not _resolves(module, symbol)
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

    def test_every_reportlab_import_in_the_package_is_registered(self) -> None:
        """
        REQUIRED_SYMBOLS is only a contract if it is complete.

        Every ``from reportlab... import name`` in the package must be listed
        above, so that adding an import without registering it fails here. An
        import inside ``try: ... except ImportError`` is optional by
        construction and is left out.
        """
        registered = {
            (module, symbol)
            for module, symbols in REQUIRED_SYMBOLS.items()
            for symbol in symbols
        }
        unregistered = sorted(
            f"{module}.{symbol} ({path})"
            for module, symbol, path in _package_reportlab_imports()
            if (module, symbol) not in registered
        )
        self.assertEqual([], unregistered, "add these to REQUIRED_SYMBOLS")


class RecentPublicApiTest(TestCase):
    """
    Public API newer than 4.0, which sets the lowest reportlab that works.

    Importing a name is not the whole contract: a keyword argument or a method
    can be missing from an older release while every import still succeeds.
    The table of contents used both from 0.2.19 on while the declared floor
    stayed at 4.0.4, and every document with a <pdf:toc> failed on 4.0.4 to
    4.4.7 without a test saying so.
    """

    def test_a_table_of_contents_takes_a_notify_kind(self) -> None:
        """Reportlab 4.2.2; ``PmlTableOfContents`` names its index with it."""
        from reportlab.platypus.tableofcontents import TableOfContents

        toc = TableOfContents(notifyKind="TOCEntry:appendix")
        self.assertEqual("TOCEntry:appendix", toc._notifyKind)

    def test_a_canvas_takes_a_named_callback(self) -> None:
        """Reportlab 4.4.9; ``PmlTableOfContents`` draws its leaders with it."""
        import io

        from reportlab.pdfgen.canvas import Canvas

        self.assertTrue(callable(Canvas(io.BytesIO()).setNamedCB))


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
            "_code",
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


class _Probe:
    """
    A flowable that records what reportlab lets it see while it is drawn.

    Built on first use, so that importing this module does not import
    reportlab's platypus before the import tests above run.
    """

    @staticmethod
    def make(record: list[dict]):
        from reportlab.platypus.flowables import Flowable

        class Probe(Flowable):
            def wrap(self, availWidth, availHeight):  # noqa: PLR6301
                return 10, 10

            def draw(self) -> None:
                canv = self.canv
                # Set by build() for the duration of the build only.
                doc = canv._doctemplate
                frame = self._frame
                record.append(
                    {
                        "doc": doc,
                        "template": doc.pageTemplate.id,
                        "matrix": canv._currentMatrix,
                        "frame": frame,
                        "flowable_frame_is_doc_frame": frame is doc.frame,
                        "frame_state": {
                            name: getattr(frame, name)
                            for name in (
                                "_aW",
                                "_aH",
                                "_x",
                                "_x1",
                                "_y1",
                                "_width",
                                "_height",
                                "_leftPadding",
                                "_rightPadding",
                                "_topPadding",
                                "_bottomPadding",
                                "_leftExtraIndent",
                                "_prevASpace",
                            )
                        },
                    }
                )

        return Probe()


def _build(story: list, template_ids=("A", "B"), doc_class=None):
    """Build ``story`` into a throwaway document with one frame per template."""
    import io

    from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
    from reportlab.platypus.frames import Frame

    doc = (doc_class or BaseDocTemplate)(io.BytesIO())
    doc.addPageTemplates(
        [
            PageTemplate(id=name, frames=[Frame(50, 60, 300, 400, id=f"frame-{name}")])
            for name in template_ids
        ]
    )
    doc.build(story)
    return doc


class CanvasAndFrameStateTest(TestCase):
    """
    The private state a flowable reads while it is drawn.

    - ``canvas._doctemplate``: the document from inside ``draw``; used for the
      page number (``paragraph.py``, ``PmlPageTemplate``) and by positioned
      boxes. No public way from a canvas to its document.
    - ``canvas._currentMatrix``: where a flowable really is on the page
      (``builders/position.py``). No public getter.
    - ``flowable._frame`` and the frame's ``_aW``, ``_aH``, ``_x``, ``_x1``,
      ``_y1``, ``_width``, ``_height``, the four ``_*Padding``,
      ``_leftExtraIndent`` and ``_prevASpace``: the frame's geometry and
      cursor (``builders/position.py``, static frames in
      ``xhtml2pdf_reportlab.py``). Frame has no public accessors for any of it.
    """

    def test_a_drawn_flowable_sees_its_document_frame_and_matrix(self) -> None:
        record: list[dict] = []
        doc = _build([_Probe.make(record)])

        (seen,) = record
        self.assertIs(doc, seen["doc"])
        self.assertEqual("frame-A", seen["frame"].id)
        self.assertTrue(seen["flowable_frame_is_doc_frame"])
        self.assertEqual(6, len(seen["matrix"]))
        state = seen["frame_state"]
        self.assertEqual(
            (50, 60, 300, 400),
            (state["_x1"], state["_y1"], state["_width"], state["_height"]),
        )
        for name in ("_leftPadding", "_rightPadding", "_topPadding", "_bottomPadding"):
            self.assertEqual(6, state[name], name)
        self.assertEqual(300 - 12, state["_aW"])
        self.assertEqual(56, state["_x"])
        for name in ("_aH", "_leftExtraIndent", "_prevASpace"):
            self.assertIsInstance(state[name], int | float, name)

    def test_frame_add_still_reads_SPACETRANSFER(self) -> None:
        """
        flex.py and position.py set ``_SPACETRANSFER = False`` on their own
        flowables, and read it from children when stacking them; the frame is
        what gives it its meaning. No public equivalent.
        """
        from reportlab.platypus.frames import Frame

        self.assertIn("_SPACETRANSFER", inspect.getsource(Frame._add))


class DocTemplateStateTest(TestCase):
    """
    The page-template bookkeeping ``PmlBaseDoc`` writes and reportlab reads.

    ``handle_nextPageTemplate`` is a copy of reportlab's, extended for
    ``:left``/``:right`` pairs; it sets ``_nextPageTemplateIndex``,
    ``_nextPageTemplateCycle`` and ``PTCycle._restart``, and ``document.py``
    sets ``_firstPageTemplateIndex`` for mirrored templates. reportlab offers
    ``NextPageTemplate`` flowables, but nothing that sets the first page's
    template or a cycle from outside the story.
    """

    def test_the_first_page_template_index_is_honoured(self) -> None:
        from reportlab.platypus.doctemplate import BaseDocTemplate

        record: list[dict] = []

        class Doc(BaseDocTemplate):
            def handle_documentBegin(self) -> None:
                self._firstPageTemplateIndex = 1
                super().handle_documentBegin()

        _build([_Probe.make(record)], doc_class=Doc)

        self.assertEqual("B", record[0]["template"])

    def test_the_next_page_template_index_is_honoured(self) -> None:
        from reportlab.platypus.flowables import Flowable, PageBreak

        record: list[dict] = []

        class Switch(Flowable):
            """Asks for template B the way PmlBaseDoc does."""

            def draw(self) -> None:
                self.canv._doctemplate._nextPageTemplateIndex = 1

        _build([Switch(), PageBreak(), _Probe.make(record)])

        self.assertEqual("B", record[0]["template"])

    def test_PmlBaseDoc_cycles_left_and_right_templates(self) -> None:
        """
        The whole contract at once: PmlBaseDoc's copy of
        handle_nextPageTemplate builds the cycle reportlab then walks.
        """
        from reportlab.platypus.doctemplate import NextPageTemplate
        from reportlab.platypus.flowables import PageBreak

        from xhtml2pdf.xhtml2pdf_reportlab import PmlBaseDoc

        record: list[dict] = []
        story = [NextPageTemplate(["A", "B"]), PageBreak()]
        for _ in range(3):
            story += [_Probe.make(record), PageBreak()]
        _build(story[:-1], doc_class=PmlBaseDoc)

        self.assertEqual(["A", "B", "A"], [seen["template"] for seen in record])

    def test_a_PTCycle_starts_with_a_restart_position(self) -> None:
        from reportlab.platypus.doctemplate import PTCycle

        self.assertEqual(0, PTCycle()._restart)


class TableStateTest(TestCase):
    """
    ``PmlTable`` overrides three private methods of Table and reads its
    layout, and ``builders/flex.py`` reads a table's content to measure it.
    None of it has a public equivalent.
    """

    @staticmethod
    def drawn_table():
        import io

        from reportlab.pdfgen.canvas import Canvas
        from reportlab.platypus.tables import Table, TableStyle

        table = Table(
            [["a", "b"], ["c", "d"]],
            colWidths=[50, None],
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 1, "black"),
                    ("BACKGROUND", (0, 0), (-1, 0), "yellow"),
                ]
            ),
        )
        canvas = Canvas(io.BytesIO())
        table.wrapOn(canvas, 300, 300)
        table.drawOn(canvas, 0, 0)
        return table

    def test_the_layout_attributes_exist_after_drawing(self) -> None:
        table = self.drawn_table()
        for attribute in (
            "_argW",
            "_cellvalues",
            "_cellStyles",
            "_colWidths",
            "_ncols",
            "_nrows",
            "_colpositions",
            "_rowpositions",
            "_bkgrndcmds",
        ):
            with self.subTest(attribute=attribute):
                self.assertTrue(hasattr(table, attribute))
        self.assertEqual((2, 2), (table._ncols, table._nrows))
        self.assertEqual(3, len(table._colpositions))
        self.assertEqual(2, len(table._cellStyles))

    def test_line_drawing_reads_the_blocks_PmlTable_sets(self) -> None:
        """
        Reportlab only sets ``_hBlocks``/``_vBlocks`` for spanned cells, and
        reads them with a default; PmlTable sets them to keep its lines off a
        rounded edge.
        """
        from reportlab.platypus.tables import Table

        source = inspect.getsource(Table)
        self.assertIn("getattr(self,'_hBlocks'", source.replace(" ", ""))
        self.assertIn("getattr(self,'_vBlocks'", source.replace(" ", ""))

    def test_a_background_command_unpacks_as_PmlTable_expects(self) -> None:
        """``for _cmd, (sc, sr), (ec, er), arg in self._bkgrndcmds``."""
        ((_cmd, (sc, sr), (ec, er), arg),) = self.drawn_table()._bkgrndcmds

        self.assertEqual((0, 0, -1, 0, "yellow"), (sc, sr, ec, er, arg))

    def test_the_overridden_methods_keep_their_signatures(self) -> None:
        from reportlab.platypus.tables import _SPECIALROWS, Table

        def parameters(method) -> list[str]:
            return list(inspect.signature(method).parameters)

        self.assertEqual(["self"], parameters(Table._drawBkgrnd))
        self.assertEqual(["self"], parameters(Table._drawLines))
        self.assertEqual(
            ["self", "V", "w", "s", "W", "H", "aH"], parameters(Table._listCellGeom)
        )
        self.assertTrue(all(isinstance(name, str) for name in _SPECIALROWS))


class OtherPrivateStateTest(TestCase):
    def test_KeepInFrame_keeps_its_content_in_content(self) -> None:
        """flex.py measures a KeepInFrame by what it holds. No public getter."""
        from reportlab.platypus.flowables import KeepInFrame, Spacer

        spacer = Spacer(1, 1)

        self.assertEqual([spacer], KeepInFrame(10, 10, content=[spacer])._content)

    def test_TableOfContents_state_and_drawPageNumbers(self) -> None:
        """
        PmlTableOfContents overrides wrap and reads ``_lastEntries``, then
        builds ``_table``, which reportlab's split and drawOn delegate to; it
        calls ``drawPageNumbers`` with the dot leader.
        """
        from reportlab.platypus.tableofcontents import TableOfContents, drawPageNumbers

        toc = TableOfContents()
        self.assertEqual([], toc._lastEntries)
        self.assertIn("self._table", inspect.getsource(TableOfContents.drawOn))
        self.assertEqual(
            ["canvas", "style", "pages", "availWidth", "availHeight", "dot"],
            list(inspect.signature(drawPageNumbers).parameters)[:6],
        )

    def test_the_font_and_glyph_tables(self) -> None:
        """
        ``_glyphname2unicode`` and ``_cidfontdata.defaultUnicodeEncodings``
        feed ``util.py``'s font maps and have no public equivalent.
        """
        import reportlab.pdfbase._cidfontdata as cidfontdata
        from reportlab.pdfbase._glyphlist import _glyphname2unicode

        self.assertEqual(ord("A"), _glyphname2unicode["A"])
        self.assertIsInstance(cidfontdata.defaultUnicodeEncodings, dict)

    def test_the_canvas_keeps_its_code(self) -> None:
        """The paragraph fork appends to ``canvas._code`` directly."""
        import io

        from reportlab.pdfgen.canvas import Canvas

        canvas = Canvas(io.BytesIO())
        self.assertIsInstance(canvas._code, list)


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
