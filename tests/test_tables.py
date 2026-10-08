from __future__ import annotations

from typing import Any, NamedTuple
from unittest import TestCase
from xml.dom import minidom

from xhtml2pdf import tables
from xhtml2pdf.context import pisaContext
from xhtml2pdf.document import pisaStory
from xhtml2pdf.parser import AttrContainer
from xhtml2pdf.xhtml2pdf_reportlab import PmlTable


class TablesWidthTestCase(TestCase):
    def test_width_returns_none_if_value_passed_is_none(self) -> None:
        result = tables._width(None)
        self.assertEqual(result, None)

    def test_width_returns_values_passed_if_string_and_ends_with_percent(self) -> None:
        result = tables._width("100%")
        self.assertEqual(result, "100%")

    def test_width_will_convert_string_to_float_if_string_passed_in_doesnt_end_with_percent(
        self,
    ) -> None:
        result = tables._width("100")
        self.assertEqual(type(result), float)

    def test_width_returns_float_if_string_contains_string_of_number(self) -> None:
        result = tables._width("130")
        self.assertEqual(result, 130.0)


class TablesHeightTestCase(TestCase):
    def test_width_returns_none_if_value_passed_is_none(self) -> None:
        result = tables._height(None)
        self.assertEqual(result, None)

    def test_width_returns_values_passed_if_string_and_ends_with_percent(self) -> None:
        result = tables._height("100%")
        self.assertEqual(result, "100%")

    def test_width_will_convert_string_to_float_if_string_passed_in_doesnt_end_with_percent(
        self,
    ) -> None:
        result = tables._height("100")
        self.assertEqual(type(result), float)

    def test_width_returns_X_if_string(self) -> None:
        result = tables._height("100")
        self.assertEqual(result, 100.0)


class TableDataTestCase(TestCase):
    def setUp(self) -> None:
        self.sut = tables.TableData

    def test_init_defines_variables(self) -> None:
        instance = self.sut()
        self.assertEqual(instance.data, [])
        self.assertEqual(instance.styles, [])
        self.assertEqual(instance.span, [])
        self.assertEqual(instance.mode, "")
        self.assertEqual(instance.padding, 0)
        self.assertEqual(instance.col, 0)
        self.assertEqual(instance.col_with_content, set())
        self.assertEqual(instance.col_empty_width, {})

    def test_add_cell_will_increment_col_and_append_data_to_instance_data(self) -> None:
        instance = self.sut()
        instance.data.append([])
        instance.add_cell("Foo")
        self.assertEqual(instance.data, [["Foo"]])
        self.assertEqual(instance.col, 1)

    def test_add_style_will_append_shallow_copy_of_passed_in_data(self) -> None:
        instance = self.sut()
        style_one = "bold"
        style_two = "italic"
        style_three = "foo"
        instance.add_style(style_one)
        self.assertEqual(instance.styles, ["bold"])
        instance.add_style(style_two)
        instance.add_style(style_three)
        self.assertEqual(instance.styles, ["bold", "italic", "foo"])

    def test_add_empty_will_add_tuple_of_args_to_span_instance_variable(self) -> None:
        instance = self.sut()
        instance.add_empty(1, 3)
        self.assertEqual(instance.span, [(1, 3)])

    def test_get_data_will_return_data_instance_variable_if_no_styles(self) -> None:
        instance = self.sut()
        instance.data.append([])
        instance.add_cell("Foo")
        data = instance.get_data()
        self.assertEqual(data, [["Foo"]])

    def test_get_data_will_add_empty_strings_where_they_have_been_defined_by_add_empty(
        self,
    ) -> None:
        instance = self.sut()
        instance.data.append([])
        instance.add_cell("Foo")
        instance.add_cell("Bar")
        instance.add_empty(0, 0)
        data = instance.get_data()
        self.assertEqual(data, [["", "Foo", "Bar"]])

    def test_get_data_will_fail_silently_if_invalid_empty_cell_found(self) -> None:
        instance = self.sut()
        instance.data.append([])
        instance.add_cell("Foo")
        instance.add_cell("Bar")
        instance.add_empty(0, 2)
        data = instance.get_data()
        self.assertEqual(data, [["Foo", "Bar"]])

    def test_add_cell_styles_will_add_padding_styles_based_on_frag_padding_attrs(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.paddingRight = 5
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="td")
        self.assertEqual(instance.styles[0], ("LEFTPADDING", (0, 1), (3, 5), 0))
        self.assertEqual(instance.styles[1], ("RIGHTPADDING", (0, 1), (3, 5), 5))
        self.assertEqual(instance.styles[2], ("TOPPADDING", (0, 1), (3, 5), 0))
        self.assertEqual(instance.styles[3], ("BOTTOMPADDING", (0, 1), (3, 5), 0))

    def test_add_cell_styles_will_add_background_style_if_context_frag_has_backcolor_set_and_mode_is_not_tr(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.backColor = "green"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="td")
        self.assertEqual(instance.styles[0], ("BACKGROUND", (0, 1), (3, 5), "green"))

    def test_add_cell_styles_will_not_add_background_style_if_context_frag_has_backcolor_set_and_mode_is_tr(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.backColor = "green"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0], ("BACKGROUND", (0, 1), (3, 5), "green"))

    def test_add_cell_styles_will_add_lineabove_style_if_bordertop_attrs_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderTopStyle = "solid"
        context.frag.borderTopWidth = "3px"
        context.frag.borderTopColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertEqual(
            instance.styles[0], ("LINEABOVE", (0, 1), (3, 1), "3px", "black", "squared")
        )

    def test_add_cell_styles_will_not_add_lineabove_style_if_bordertop_style_not_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderTopWidth = "3px"
        context.frag.borderTopColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEABOVE")

    def test_add_cell_styles_will_not_add_lineabove_style_if_bordertop_width_not_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderTopStyle = "solid"
        context.frag.borderTopWidth = 0
        context.frag.borderTopColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEABOVE")

    def test_add_cell_styles_will_not_add_lineabove_style_if_bordertop_color_not_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderTopStyle = "solid"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEABOVE")

    def test_add_cell_styles_will_add_linebefore_style_if_borderleft_attrs_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderLeftStyle = "solid"
        context.frag.borderLeftWidth = "3px"
        context.frag.borderLeftColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertEqual(
            instance.styles[0],
            ("LINEBEFORE", (0, 1), (0, 5), "3px", "black", "squared"),
        )

    def test_add_cell_styles_will_not_add_linebefore_style_if_borderleft_style_not_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderLeftWidth = "3px"
        context.frag.borderLeftColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEBEFORE")

    def test_add_cell_styles_will_not_add_linebefore_style_if_borderleft_width_set_to_zero_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderLeftStyle = "solid"
        context.frag.borderLeftWidth = 0
        context.frag.borderLeftColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEBEFORE")

    def test_add_cell_styles_will_not_add_linebefore_style_if_borderleft_width_not_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderLeftStyle = "solid"
        context.frag.borderLeftWidth = "3px"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEBEFORE")

    def test_add_cell_styles_will_add_lineafter_style_if_borderright_attrs_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderRightStyle = "solid"
        context.frag.borderRightWidth = "3px"
        context.frag.borderRightColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertEqual(
            instance.styles[0], ("LINEAFTER", (3, 1), (3, 5), "3px", "black", "squared")
        )

    def test_add_cell_styles_will_not_add_lineafter_style_if_borderright_style_not_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderRightWidth = "3px"
        context.frag.borderRightColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEAFTER")

    def test_add_cell_styles_will_not_add_lineafter_style_if_borderright_width_set_to_zero_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderRightStyle = "solid"
        context.frag.borderRightWidth = 0
        context.frag.borderRightColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEAFTER")

    def test_add_cell_styles_will_not_add_lineafter_style_if_borderright_color_not_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderRightStyle = "solid"
        context.frag.borderRightWidth = "3px"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEAFTER")

    def test_add_cell_styles_will_add_linebelow_style_if_borderbottom_attrs_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderBottomStyle = "solid"
        context.frag.borderBottomWidth = "3px"
        context.frag.borderBottomColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertEqual(
            instance.styles[0], ("LINEBELOW", (0, 5), (3, 5), "3px", "black", "squared")
        )

    def test_add_cell_styles_will_not_add_linebelow_style_if_borderbottom_style_not_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderBottomWidth = "3px"
        context.frag.borderBottomColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEBELOW")

    def test_add_cell_styles_will_not_add_linebelow_style_if_borderbottom_width_set_to_zero_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderBottomStyle = "solid"
        context.frag.borderBottomWidth = 0
        context.frag.borderBottomColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEBELOW")

    def test_add_cell_styles_will_not_add_linebelow_style_if_borderbottom_color_not_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderBottomStyle = "solid"
        context.frag.borderBottomWidth = "3px"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertNotEqual(instance.styles[0][0], "LINEBELOW")

    def test_add_cell_styles_will_add_all_line_styles_if_all_border_attrs_set_on_context_frag(
        self,
    ) -> None:
        context = pisaContext()
        context.frag.borderTopStyle = "solid"
        context.frag.borderTopWidth = "3px"
        context.frag.borderTopColor = "black"
        context.frag.borderLeftStyle = "solid"
        context.frag.borderLeftWidth = "3px"
        context.frag.borderLeftColor = "black"
        context.frag.borderRightStyle = "solid"
        context.frag.borderRightWidth = "3px"
        context.frag.borderRightColor = "black"
        context.frag.borderBottomStyle = "solid"
        context.frag.borderBottomWidth = "3px"
        context.frag.borderBottomColor = "black"
        instance = self.sut()
        instance.add_cell_styles(context, (0, 1), (3, 5), mode="tr")
        self.assertEqual(
            instance.styles[0], ("LINEABOVE", (0, 1), (3, 1), "3px", "black", "squared")
        )
        self.assertEqual(
            instance.styles[1],
            ("LINEBEFORE", (0, 1), (0, 5), "3px", "black", "squared"),
        )
        self.assertEqual(
            instance.styles[2], ("LINEAFTER", (3, 1), (3, 5), "3px", "black", "squared")
        )
        self.assertEqual(
            instance.styles[3], ("LINEBELOW", (0, 5), (3, 5), "3px", "black", "squared")
        )


class PisaTagTableTestCase(TestCase):
    def setUp(self) -> None:
        self.element = self._getElement("rootElement")
        self.attrs: Any = AttrContainer(
            {
                "border": "",
                "bordercolor": "",
                "cellpadding": "",
                "align": "",
                "repeat": "",
                "width": None,
            }
        )

    @staticmethod
    def _getElement(tagName, body="filler"):
        dom = minidom.parseString(f"<{tagName}>{body}</{tagName}>")
        return dom.getElementsByTagName(tagName)[0]

    def test_will_set_attrs_on_tabledata(self) -> None:
        self.attrs.cellpadding = 4
        self.attrs.align = "left"
        self.attrs.repeat = True
        self.attrs.width = 100
        tag = tables.pisaTagTABLE(self.element, self.attrs)
        context = pisaContext()
        tag.start(context)
        self.assertEqual(context.tableData.padding, 4)
        self.assertEqual(
            context.tableData.styles[0], ("LEFTPADDING", (0, 0), (-1, -1), 4)
        )
        self.assertEqual(
            context.tableData.styles[1], ("RIGHTPADDING", (0, 0), (-1, -1), 4)
        )
        self.assertEqual(
            context.tableData.styles[2], ("TOPPADDING", (0, 0), (-1, -1), 4)
        )
        self.assertEqual(
            context.tableData.styles[3], ("BOTTOMPADDING", (0, 0), (-1, -1), 4)
        )
        self.assertEqual(context.tableData.align, "LEFT")
        self.assertEqual(context.tableData.col, 0)
        self.assertEqual(context.tableData.row, 0)
        self.assertEqual(context.tableData.colw, [])
        self.assertEqual(context.tableData.rowh, [])
        self.assertEqual(context.tableData.repeat, True)
        self.assertEqual(context.tableData.width, 100.0)

    def test_start_will_add_borders_if_border_and_border_color_set_in_attrs(
        self,
    ) -> None:
        self.attrs.border = 2
        self.attrs.bordercolor = "green"
        tag = tables.pisaTagTABLE(self.element, self.attrs)
        context = pisaContext()
        tag.start(context)
        self.assertEqual(context.frag.borderLeftWidth, 2)
        self.assertEqual(context.frag.borderRightWidth, 2)
        self.assertEqual(context.frag.borderTopWidth, 2)
        self.assertEqual(context.frag.borderBottomWidth, 2)
        self.assertEqual(context.frag.borderLeftColor, "green")
        self.assertEqual(context.frag.borderRightColor, "green")
        self.assertEqual(context.frag.borderTopColor, "green")
        self.assertEqual(context.frag.borderBottomColor, "green")
        self.assertEqual(context.frag.borderLeftStyle, "solid")
        self.assertEqual(context.frag.borderRightStyle, "solid")
        self.assertEqual(context.frag.borderTopStyle, "solid")
        self.assertEqual(context.frag.borderBottomStyle, "solid")


class PisaTagTDTestCase(TestCase):
    def test_td_tag_doesnt_collapse_when_empty(self) -> None:
        dom = minidom.parseString("<td></td>")
        element = dom.getElementsByTagName("td")[0]
        attrs = AttrContainer(
            {
                "align": None,
                "colspan": None,
                "rowspan": None,
                "width": None,
                "valign": None,
            }
        )
        context = pisaContext()
        table_data = tables.TableData()
        table_data.col = 0
        table_data.row = 0
        table_data.colw = []
        table_data.rowh = []
        context.tableData = table_data
        context.frag.paddingLeft = 0
        context.frag.paddingRight = 0

        instance = tables.pisaTagTD(element, attrs)
        instance.start(context)

        self.assertEqual(context.tableData.colw, [None])


class EmptyCellColumnWidthTestCase(TestCase):
    """
    An empty <td> must not decide the width of its whole column.

    A cell with no children cannot be sized by its content, so it offers its
    own padding as the column width. That was applied per cell, before the
    table had been read to the end, so one empty cell was enough to overwrite
    the width declared in the header -- and, with no width declared anywhere,
    to overwrite the "let reportlab share it out" that a cell with content had
    left. In a statement with an empty debit or credit cell on half its rows,
    both columns came out ten points wide and their neighbours overlapped them.
    """

    #: Padding is what makes the offered width non-zero, and so is what makes
    #: the bug visible at all: with `padding: 0` the column was left alone.
    STYLE = "td, th { padding: 3pt 5pt; }"

    def widths(self, rows: str, style: str = "") -> list:
        """
        The column widths the parser computed, before anything is built.

        Through pisaStory rather than pisaParser: only the former loads
        DEFAULT_CSS, and without it a <td> is inline, CSS2Frag never applies
        its padding, and the whole bug is unreachable.
        """
        html = (
            f"<html><head><style>{self.STYLE}{style}</style></head><body>"
            f'<table width="100%" cellpadding="0">{rows}</table>'
            "</body></html>"
        )
        context = pisaStory(html)
        table = next(f for f in context.story if isinstance(f, PmlTable))
        return list(table._colWidths)

    def test_a_declared_width_survives_an_empty_cell(self) -> None:
        rows = (
            '<tr><th width="60mm">a</th><th width="30mm">b</th>'
            '<th width="30mm">c</th></tr>'
            "<tr><td>x</td><td>y</td><td>z</td></tr>"
            "<tr><td>x</td><td>y</td><td></td></tr>"
        )
        third = self.widths(rows)[2]
        self.assertAlmostEqual(tables._width("30mm"), third, places=3)

    def test_an_empty_cell_does_not_size_a_column_that_has_content(self) -> None:
        """With no width declared, the column is reportlab's to share out."""
        rows = (
            "<tr><td>a</td><td>b</td><td>c</td></tr>"
            "<tr><td>x</td><td>y</td><td></td></tr>"
        )
        self.assertEqual([None, None, None], self.widths(rows))

    def test_a_column_that_is_empty_throughout_gets_its_padding(self) -> None:
        """The behaviour the code was reaching for, kept intact."""
        rows = (
            "<tr><td>a</td><td>b</td><td></td></tr>"
            "<tr><td>x</td><td>y</td><td></td></tr>"
        )
        widths = self.widths(rows)
        self.assertEqual([None, None], widths[:2])
        self.assertAlmostEqual(10.0, widths[2], places=3)  # 5pt + 5pt

    def test_an_empty_cell_without_padding_changes_nothing(self) -> None:
        rows = (
            "<tr><td>a</td><td>b</td><td>c</td></tr>"
            "<tr><td>x</td><td>y</td><td></td></tr>"
        )
        self.assertEqual([None, None, None], self.widths(rows, "td { padding: 0; }"))


class RepeatedHeaderTestCase(TestCase):
    """
    <thead> says which rows repeat at the top of every page.

    Repetition used to be available only through the non-standard
    `<table repeat="N">`, and thead/tbody/tfoot were not tags this library
    knew: a long table written the standard way printed its header on the
    first page and nowhere else, silently.
    """

    @staticmethod
    def repeat_rows(table_html: str) -> int:
        """
        What the parser will hand reportlab as repeatRows.

        Through pisaStory, not pisaParser: the default stylesheet is what makes
        a <td> a block, and the row bookkeeping depends on it.
        """
        html = f"<html><body>{table_html}</body></html>"
        context = pisaStory(html)
        table = next(f for f in context.story if isinstance(f, PmlTable))
        return table.repeatRows

    def test_a_header_row_repeats(self) -> None:
        self.assertEqual(
            1,
            self.repeat_rows(
                "<table><thead><tr><th>h</th></tr></thead>"
                "<tbody><tr><td>a</td></tr></tbody></table>"
            ),
        )

    def test_a_two_row_header_repeats_both(self) -> None:
        self.assertEqual(
            2,
            self.repeat_rows(
                "<table><thead><tr><th>h</th></tr><tr><th>sub</th></tr></thead>"
                "<tbody><tr><td>a</td></tr></tbody></table>"
            ),
        )

    def test_the_explicit_attribute_still_works(self) -> None:
        self.assertEqual(
            1,
            self.repeat_rows(
                '<table repeat="1"><tr><th>h</th></tr><tr><td>a</td></tr></table>'
            ),
        )

    def test_the_larger_of_the_two_wins(self) -> None:
        """Asking for two rows and marking one up should not lose a row."""
        self.assertEqual(
            2,
            self.repeat_rows(
                '<table repeat="2"><thead><tr><th>h</th></tr></thead>'
                "<tbody><tr><td>a</td></tr></tbody></table>"
            ),
        )

    def test_a_table_without_either_repeats_nothing(self) -> None:
        self.assertEqual(
            0, self.repeat_rows("<table><tr><th>h</th></tr><tr><td>a</td></tr></table>")
        )


class EmptyRowTestCase(TestCase):
    """A <tr> with no cells does not abort the document (#323)."""

    def render(self, html: str) -> str:
        from io import BytesIO

        from pypdf import PdfReader

        from xhtml2pdf import pisa

        out = BytesIO()
        result = pisa.CreatePDF(html, dest=out)
        self.assertFalse(result.err)
        return PdfReader(BytesIO(out.getvalue())).pages[0].extract_text()

    def test_empty_last_row(self) -> None:
        text = self.render(
            "<table><tr><td>first</td><td>second</td></tr><tr></tr></table>"
        )
        self.assertIn("first", text)

    def test_empty_last_row_under_a_rowspan(self) -> None:
        text = self.render(
            "<table><tr><td rowspan=2>span</td><td>b</td></tr><tr></tr></table>"
        )
        self.assertIn("span", text)

    def test_table_of_empty_rows_is_skipped(self) -> None:
        text = self.render("<p>before</p><table><tr></tr></table><p>after</p>")
        self.assertIn("after", text)


class RowGroupTestCase(TestCase):
    """thead/tbody/tfoot: their background (#806) and the rowspan boundary (#470)."""

    @staticmethod
    def table_commands(html: str) -> tuple[list, list]:
        from io import BytesIO
        from unittest import mock

        from xhtml2pdf import pisa

        seen: list = []
        original = PmlTable.__init__

        def spy(table, data, *args, **kwargs):
            seen.append((data, kwargs["style"].getCommands()))
            original(table, data, *args, **kwargs)

        with mock.patch.object(PmlTable, "__init__", spy):
            pisa.CreatePDF(html, dest=BytesIO())
        return seen[0]

    def test_thead_background_is_painted_behind_its_rows(self) -> None:
        _data, commands = self.table_commands(
            '<table><thead style="background-color: orange"><tr><th>H</th></tr></thead>'
            "<tbody><tr><td>a</td></tr></tbody></table>"
        )
        backgrounds = [c for c in commands if c[0] == "BACKGROUND"]
        self.assertEqual([((0, 0), (-1, 0))], [c[1:3] for c in backgrounds])

    def test_group_background_comes_before_its_rows(self) -> None:
        _data, commands = self.table_commands(
            '<table><tbody style="background-color: orange">'
            '<tr style="background-color: red"><td>a</td></tr></tbody></table>'
        )
        colours = [str(c[3]) for c in commands if c[0] == "BACKGROUND"]
        self.assertEqual(2, len(colours))
        self.assertIn("1,.647059,0", colours[0])

    def test_table_background_is_not_repeated_by_the_implied_tbody(self) -> None:
        _data, commands = self.table_commands(
            '<table style="background-color: orange"><tr><td>a</td></tr></table>'
        )
        self.assertEqual(1, len([c for c in commands if c[0] == "BACKGROUND"]))

    def test_rowspan_stops_at_the_end_of_its_tbody(self) -> None:
        data, commands = self.table_commands(
            "<table><tbody><tr><td rowspan=3>s</td><td>x</td></tr>"
            "<tr><td>y</td></tr></tbody>"
            "<tbody><tr><td>b</td><td>c</td></tr></tbody></table>"
        )
        self.assertEqual(
            [((0, 0), (0, 1))], [c[1:3] for c in commands if c[0] == "SPAN"]
        )
        # The second group's first cell is in the first column.
        self.assertNotEqual("", data[2][0])
        self.assertEqual(2, len(data[2]))


class CellKeepInFrameModeTestCase(TestCase):
    """-pdf-keep-in-frame-mode is the cell's own, whatever it holds (#220)."""

    @staticmethod
    def modes(html: str) -> list[str]:
        from io import BytesIO
        from unittest import mock

        from xhtml2pdf import pisa

        seen: list[str] = []
        original = tables.PmlKeepInFrame.__init__

        def spy(frame, *args, **kwargs):
            seen.append(kwargs["mode"])
            original(frame, *args, **kwargs)

        with mock.patch.object(tables.PmlKeepInFrame, "__init__", spy):
            pisa.CreatePDF(html, dest=BytesIO())
        return seen

    def test_a_cell_holding_a_block(self) -> None:
        self.assertEqual(
            ["truncate"],
            self.modes(
                '<table><tr><td style="-pdf-keep-in-frame-mode: truncate"><p>x</p></td></tr></table>'
            ),
        )

    def test_a_cell_holding_text(self) -> None:
        self.assertEqual(
            ["overflow"],
            self.modes(
                '<table><tr><td style="-pdf-keep-in-frame-mode: overflow">x</td></tr></table>'
            ),
        )


class TableMarginTestCase(TestCase):
    """A table's own margin-left/right and CSS width are applied (#386)."""

    @staticmethod
    def boxes(html: str) -> list[tuple[float, float]]:
        """(left, width) of each table, or each part of one, as drawn."""
        from io import BytesIO
        from unittest import mock

        from reportlab.platypus.tables import Table

        from xhtml2pdf import pisa

        seen = []
        draw = Table.drawOn

        def spy(self, canvas, x, y, _sW=0):
            seen.append((self._hAlignAdjust(x, _sW), self._width))
            return draw(self, canvas, x, y, _sW)

        with mock.patch.object(Table, "drawOn", spy):
            pisa.CreatePDF(html, dest=BytesIO())
        return seen

    def setUp(self) -> None:
        ((self.left, self.width),) = self.boxes("<table><tr><td>x</td></tr></table>")

    def assertBox(self, expected, actual) -> None:
        for e, a in zip(expected, actual, strict=True):
            self.assertAlmostEqual(e, a, places=3)

    def test_margins_narrow_the_table(self) -> None:
        (box,) = self.boxes(
            '<table style="margin-left: 72pt; margin-right: 36pt"><tr><td>x</td></tr></table>'
        )
        self.assertBox((self.left + 72, self.width - 108), box)

    def test_a_css_width_is_a_share_of_what_the_margins_leave(self) -> None:
        (box,) = self.boxes(
            '<table style="width: 50%; margin-left: 72pt"><tr><td>x</td></tr></table>'
        )
        self.assertBox((self.left + 72, (self.width - 72) / 2), box)

    def test_a_css_width_wins_over_the_attribute(self) -> None:
        (box,) = self.boxes(
            '<table width="10%" style="width: 200pt"><tr><td>x</td></tr></table>'
        )
        self.assertBox((self.left, 200), box)

    def test_auto_margins_align_the_table(self) -> None:
        cases = {
            "margin: 0 auto": self.left + (self.width - 200) / 2,
            "margin-left: auto": self.left + self.width - 200,
        }
        for css, left in cases.items():
            with self.subTest(css=css):
                (box,) = self.boxes(
                    f'<table style="width: 200pt; {css}"><tr><td>x</td></tr></table>'
                )
                self.assertBox((left, 200), box)

    def test_every_page_of_a_split_table_keeps_them(self) -> None:
        rows = "<tr><td>x</td></tr>" * 150
        parts = self.boxes(f'<table style="margin-left: 72pt">{rows}</table>')
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertBox((self.left + 72, self.width - 72), part)

    def test_the_indent_of_a_block_around_it_is_not_added(self) -> None:
        (box,) = self.boxes(
            '<div style="margin-left: 50pt"><table style="margin-left: 72pt">'
            "<tr><td>x</td></tr></table></div>"
        )
        self.assertBox((self.left + 72, self.width - 72), box)


class CellTextIndentTestCase(TestCase):
    """The text of a cell starts at the cell, whatever the table's margins."""

    TEXT = "MSKU 708 412 3"
    CELL = f'<tr><td style="padding: 0 6pt">{TEXT}</td><td>x</td></tr>'

    @staticmethod
    def positions(html: str, page: int = 0) -> dict[str, tuple[float, float]]:
        from tests.test_position import positions

        return positions(html, page)

    def setUp(self) -> None:
        ((self.left, _),) = TableMarginTestCase.boxes(f"<table>{self.CELL}</table>")

    def test_the_table_margin_is_not_an_indent_too(self) -> None:
        words = self.positions(
            f'<table style="margin-left: 72pt; margin-right: 36pt">{self.CELL}</table>'
        )
        # On one line: the cell's width is not taken by an indent.
        self.assertAlmostEqual(self.left + 72 + 6, words[self.TEXT][0], places=0)

    def test_the_indent_of_a_block_around_it_is_not_either(self) -> None:
        words = self.positions(
            f'<div style="margin-left: 72pt"><table>{self.CELL}</table></div>'
        )
        self.assertAlmostEqual(self.left + 6, words[self.TEXT][0], places=0)

    def test_every_page_of_a_split_table(self) -> None:
        rows = "".join(
            f'<tr><td style="padding: 0 6pt">row{i}</td></tr>' for i in range(150)
        )
        html = f'<table style="margin-left: 72pt">{rows}</table>'
        first, second = self.positions(html, 0), self.positions(html, 1)
        self.assertAlmostEqual(self.left + 78, first["row0"][0], places=0)
        last = max(second, key=lambda word: int(word[3:]))
        self.assertAlmostEqual(self.left + 78, second[last][0], places=0)

    def test_a_margin_inside_the_cell_still_indents(self) -> None:
        words = self.positions(
            '<table style="margin-left: 72pt"><tr><td style="padding: 0 6pt">'
            '<p style="margin-left: 10pt">Inside</p></td></tr></table>'
        )
        self.assertAlmostEqual(self.left + 72 + 6 + 10, words["Inside"][0], places=0)

    def test_the_cell_padding_is_applied_once(self) -> None:
        for html in (
            '<td style="padding: 10pt">Text</td>',
            '<td style="padding: 10pt"><p>Text</p></td>',
        ):
            with self.subTest(html=html):
                words = self.positions(f"<table><tr>{html}</tr></table>")
                self.assertAlmostEqual(self.left + 10, words["Text"][0], places=0)


class DrawnTable(NamedTuple):
    """A table, or one part of a split one, as it was drawn."""

    page: int
    left: float
    width: float
    columns: list[float]
    rows: list[float]


def drawn_tables(html: str) -> list[DrawnTable]:
    """Every table, or part of one, in the order it was drawn."""
    from io import BytesIO
    from unittest import mock

    from reportlab.platypus.tables import Table

    from xhtml2pdf import pisa

    seen = []
    draw = Table.drawOn

    def spy(self, canvas, x, y, _sW=0):
        seen.append(
            DrawnTable(
                canvas.getPageNumber(),
                self._hAlignAdjust(x, _sW),
                self._width,
                list(self._colWidths),
                list(self._rowHeights),
            )
        )
        return draw(self, canvas, x, y, _sW)

    with mock.patch.object(Table, "drawOn", spy):
        pisa.CreatePDF(html, dest=BytesIO())
    return seen


class TableShrinkToFitTestCase(TestCase):
    """
    An auto margin on a table with no width of its own makes it as wide as
    its content, not as the frame (#562); a table without one still fills
    the frame, and a declared width is kept.
    """

    def setUp(self) -> None:
        ((_, self.left, self.width, _, _),) = drawn_tables(
            "<table><tr><td>x</td></tr></table>"
        )

    @staticmethod
    def table(css: str, cells: str = "<td>x</td>") -> DrawnTable:
        (drawn,) = drawn_tables(f'<table style="{css}"><tr>{cells}</tr></table>')
        return drawn

    def test_centred_without_a_width_it_shrinks_to_its_content(self) -> None:
        drawn = self.table("margin: 0 auto")

        self.assertLess(drawn.width, 40)
        self.assertAlmostEqual(self.left + (self.width - drawn.width) / 2, drawn.left)

    def test_margin_left_auto_shrinks_it_to_the_right(self) -> None:
        drawn = self.table("margin-left: auto")

        self.assertLess(drawn.width, 40)
        self.assertAlmostEqual(self.left + self.width, drawn.left + drawn.width)

    def test_margin_right_auto_shrinks_it_on_the_left(self) -> None:
        drawn = self.table("margin-right: auto")

        self.assertLess(drawn.width, 40)
        self.assertAlmostEqual(self.left, drawn.left)

    def test_without_an_auto_margin_it_still_fills_the_frame(self) -> None:
        drawn = self.table("margin-left: 0")

        self.assertAlmostEqual(self.width, drawn.width)

    def test_a_declared_width_is_kept(self) -> None:
        for css in ("width: 300pt; margin: 0 auto", "margin: 0 auto"):
            with self.subTest(css=css):
                (drawn,) = drawn_tables(
                    f'<table width="300pt" style="{css}"><tr><td>x</td></tr></table>'
                )
                self.assertAlmostEqual(300, drawn.width)

    def test_each_column_is_as_wide_as_its_content(self) -> None:
        drawn = self.table(
            "margin: 0 auto", "<td>a</td><td>a much longer piece of text</td>"
        )

        narrow, wide = drawn.columns
        self.assertLess(narrow, wide)
        self.assertAlmostEqual(drawn.width, narrow + wide)
        self.assertLess(drawn.width, self.width / 2)

    def test_content_wider_than_the_frame_fills_it_and_wraps(self) -> None:
        text = "word " * 200
        drawn = self.table("margin: 0 auto", f"<td>short</td><td>{text}</td>")

        self.assertAlmostEqual(self.width, drawn.width, places=3)
        short, long = drawn.columns
        self.assertLess(short, long)

    def test_a_fixed_column_keeps_its_width(self) -> None:
        drawn = self.table(
            "margin: 0 auto", '<td style="width: 100pt">a</td><td>b</td>'
        )

        self.assertAlmostEqual(100, drawn.columns[0])
        self.assertLess(drawn.width, 140)

    def test_a_spanning_cell_widens_every_column_it_spans(self) -> None:
        (drawn,) = drawn_tables(
            '<table style="margin: 0 auto"><tr><td colspan="2">'
            "a rather long heading over both</td></tr>"
            "<tr><td>a</td><td>b</td></tr></table>"
        )

        first, second = drawn.columns
        self.assertAlmostEqual(first, second)
        self.assertLess(drawn.width, self.width / 2)

    def test_a_percentage_column_keeps_the_table_full_width(self) -> None:
        drawn = self.table("margin: 0 auto", '<td style="width: 50%">a</td><td>b</td>')

        self.assertAlmostEqual(self.width, drawn.width)

    def test_every_page_of_a_split_table_keeps_its_width_and_place(self) -> None:
        rows = "<tr><td>x</td></tr>" * 150
        parts = drawn_tables(f'<table style="margin: 0 auto">{rows}</table>')

        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertAlmostEqual(parts[0].width, part.width)
            self.assertAlmostEqual(parts[0].left, part.left)
        self.assertLess(parts[0].width, 40)


class TableHeightTestCase(TestCase):
    """A CSS height on a <table> is the least it is high, as in a browser."""

    ROWS = "<tr><td>a</td></tr><tr><td>b</td></tr>"

    def test_the_rows_share_what_the_height_adds(self) -> None:
        (drawn,) = drawn_tables(f'<table style="height: 300pt">{self.ROWS}</table>')

        self.assertAlmostEqual(300, sum(drawn.rows))
        self.assertAlmostEqual(drawn.rows[0], drawn.rows[1])

    def test_taller_content_makes_it_taller(self) -> None:
        (natural,) = drawn_tables(f"<table>{self.ROWS}</table>")
        (drawn,) = drawn_tables(f'<table style="height: 2pt">{self.ROWS}</table>')

        self.assertEqual(natural.rows, drawn.rows)

    def test_a_percentage_height_is_ignored(self) -> None:
        (natural,) = drawn_tables(f"<table>{self.ROWS}</table>")
        (drawn,) = drawn_tables(f'<table style="height: 50%">{self.ROWS}</table>')

        self.assertEqual(natural.rows, drawn.rows)

    def test_a_height_and_a_width_are_both_kept(self) -> None:
        (drawn,) = drawn_tables(
            f'<table style="width: 200pt; height: 100pt; margin: 0 auto">{self.ROWS}'
            "</table>"
        )

        self.assertAlmostEqual(200, drawn.width)
        self.assertAlmostEqual(100, sum(drawn.rows))

    def test_a_table_that_fits_only_without_its_height_moves_on(self) -> None:
        """It goes whole to the next page, where it gets its height."""
        filler = '<div style="height: 500pt"></div>' + "<p>filler</p>" * 40
        (drawn,) = drawn_tables(
            f'{filler}<table style="height: 300pt">{self.ROWS}</table>'
        )

        self.assertEqual(2, drawn.page)
        self.assertAlmostEqual(300, sum(drawn.rows))

    def test_a_table_taller_than_a_page_splits_at_its_own_height(self) -> None:
        rows = "<tr><td>x</td></tr>" * 150
        parts = drawn_tables(f'<table style="height: 2000pt">{rows}</table>')

        self.assertGreater(len(parts), 1)


class CellHeightAttributeTestCase(TestCase):
    """
    <td height="..."> sets the row's height, as style="height: ..." does.

    The cell looked the attribute up, but td and th did not declare it, so it
    was dropped before it got there: only the CSS property ever worked.
    """

    @staticmethod
    def row_heights(html: str) -> list:
        (table,) = [f for f in pisaStory(html).story if isinstance(f, PmlTable)]
        return table._argH

    def test_the_attribute_is_read(self) -> None:
        for tag in ("td", "th"):
            with self.subTest(tag):
                (height,) = self.row_heights(
                    f'<table><tr><{tag} height="32mm">a</{tag}></tr></table>'
                )
                self.assertAlmostEqual(32 * 72 / 25.4, height)

    def test_as_the_property_is(self) -> None:
        self.assertEqual(
            self.row_heights('<table><tr><td style="height: 32mm">a</td></tr></table>'),
            self.row_heights('<table><tr><td height="32mm">a</td></tr></table>'),
        )

    def test_a_number_is_points_as_for_width(self) -> None:
        self.assertEqual(
            [90.0], self.row_heights('<table><tr><td height="90">a</td></tr></table>')
        )

    def test_the_property_wins(self) -> None:
        (height,) = self.row_heights(
            '<table><tr><td height="90" style="height: 20pt">a</td></tr></table>'
        )
        self.assertAlmostEqual(20, height)
