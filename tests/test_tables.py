from __future__ import annotations

from typing import Any
from unittest import TestCase
from xml.dom import minidom

from xhtml2pdf import tables
from xhtml2pdf.context import pisaContext
from xhtml2pdf.parser import AttrContainer


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
