from io import BytesIO
from unittest import TestCase

from xhtml2pdf.context import pisaContext
from xhtml2pdf.parser import pisaParser


class HttpTest(TestCase):
    def test_timeout(self) -> None:
        """Test why some http request doesn't have a timeout"""
        html = """<!DOCTYPE html>
<html lang="bs">
  <head>
    <meta charset="UTF-8" />
    <title></title>
  </head>

  <body>
    <h1>works</h1>

    <img src="https://cars.usnews.com/static/images/Auto/custom/14737/2022_Acura_ILX_1.jpg" alt="" />

  </body>
</html>
    """

        pisaParser(BytesIO(html.encode("utf-8")), pisaContext())

        self.assertEqual(1, 1)
