from unittest import TestCase

from xhtml2pdf.w3c.css import CSSBuilder, CSSParser


class CssMediaRuleTest(TestCase):
    """Test cases for the css @media rule (https://www.w3.org/TR/css3-mediaqueries/)"""

    def setUp(self) -> None:
        """Setup css parser for all test cases"""
        self.parser = CSSParser(CSSBuilder(mediumSet=["all"]))

    def test_media_all(self) -> None:
        """Test if the rule "@media all {" works"""
        media_all = """
            @media all {
                p { color: yellow; }
            }
        """

        selector_media_all = self.parser.parse(media_all)[0]
        css_media_all = self._get_first_dict_value(selector_media_all)

        self.assertDictEqual(css_media_all, {"color": "yellow"})

    def test_media_all_and(self) -> None:
        """Test if the rule "@media all and (...) {" works"""
        media_all_and = """
            @media all and (max-width: 500px) {
                p { color: yellow; }
            }
        """

        selector_media_all_and = self.parser.parse(media_all_and)[0]
        css_media_all_and = self._get_first_dict_value(selector_media_all_and)

        self.assertDictEqual(css_media_all_and, {"color": "yellow"})

    def test_media_all_default(self) -> None:
        """Test if the rule "@media (...) {" works (no media type defaults to "all")"""
        media_all_default = """
            @media (max-width: 500px) {
                p { color: yellow; }
            }
        """

        selector_media_all_default = self.parser.parse(media_all_default)[0]
        css_media_all_default = self._get_first_dict_value(selector_media_all_default)

        self.assertDictEqual(css_media_all_default, {"color": "yellow"})

    @staticmethod
    def _get_first_dict_value(dictionary):
        return dictionary[next(iter(dictionary.keys()))]
