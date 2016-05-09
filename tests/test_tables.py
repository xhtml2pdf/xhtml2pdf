import unittest
from xhtml2pdf import tables


class TablesWidthTestCase(unittest.TestCase):

    def test_width_returns_none_if_value_passed_is_none(self):
        result = tables._width(None)
        self.assertEqual(result, None)

    def test_width_returns_values_passed_if_string_and_ends_with_percent(self):
        result = tables._width("100%")
        self.assertEqual(result, "100%")

    def test_width_will_convert_string_to_float_if_string_passed_in_doesnt_end_with_percent(self):
        result = tables._width("100")
        self.assertEqual(type(result), float)

    def test_width_returns_X_if_string(self):
        result = tables._width("100")
        self.assertEqual(result, 100.0)
        result = tables._width("100")
        self.assertEqual(result, 100.0)


class TablesHeightTestCase(unittest.TestCase):

    def test_width_returns_none_if_value_passed_is_none(self):
        result = tables._height(None)
        self.assertEqual(result, None)

    def test_width_returns_values_passed_if_string_and_ends_with_percent(self):
        result = tables._height("100%")
        self.assertEqual(result, "100%")

    def test_width_will_convert_string_to_float_if_string_passed_in_doesnt_end_with_percent(self):
        result = tables._height("100")
        self.assertEqual(type(result), float)

    def test_width_returns_X_if_string(self):
        result = tables._height("100")
        self.assertEqual(result, 100.0)


class TableDataTestCase(unittest.TestCase):

    def setUp(self):
        self.sut = tables.TableData

    def test_init_defines_variables(self):
        instance = self.sut()
        self.assertEqual(instance.data, [])
        self.assertEqual(instance.styles, [])
        self.assertEqual(instance.span, [])
        self.assertEqual(instance.mode, "")
        self.assertEqual(instance.padding, 0)
        self.assertEqual(instance.col, 0)

    def test_add_cell_will_increment_col_and_append_data_to_instance_data(self):
        instance = self.sut()
        instance.data.append([])
        instance.add_cell("Foo")
        self.assertEqual(instance.data, [["Foo"]])
        self.assertEqual(instance.col, 1)

    def test_add_style_will_append_shallow_copy_of_passed_in_data(self):
        instance = self.sut()
        style_one = "bold"
        style_two = "italic"
        style_three = "foo"
        instance.add_style(style_one)
        self.assertEqual(instance.styles, ["bold"])
        instance.add_style(style_two)
        instance.add_style(style_three)
        self.assertEqual(instance.styles, ["bold", "italic", "foo"])

    def test_add_empty_will_add_tuple_of_args_to_span_instance_variable(self):
        instance = self.sut()
        instance.add_empty(1, 3)
        self.assertEqual(instance.span, [(1, 3)])

    def test_get_data_will_return_data_instance_variable_if_no_styles(self):
        instance = self.sut()
        instance.data.append([])
        instance.add_cell("Foo")
        data = instance.get_data()
        self.assertEqual(data, [["Foo"]])

    def test_get_data_will_add_empty_strings_where_they_have_been_defined_by_add_empty(self):
        instance = self.sut()
        instance.data.append([])
        instance.add_cell("Foo")
        instance.add_cell("Bar")
        instance.add_empty(0, 0)
        data = instance.get_data()
        self.assertEqual(data, [["", "Foo", "Bar"]])

    def test_get_data_fail_silently_if_invalid_empty_cell_found(self):
        instance = self.sut()
        instance.data.append([])
        instance.add_cell("Foo")
        instance.add_cell("Bar")
        instance.add_empty(0, 2)
        data = instance.get_data()
        self.assertEqual(data, [["Foo", "Bar"]])


if __name__ == "__main__":
    unittest.main()
