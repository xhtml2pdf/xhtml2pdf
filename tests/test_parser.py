import os
from unittest import TestCase

from xhtml2pdf.context import pisaContext
from xhtml2pdf.parser import pisaParser

_data = b"""
<!doctype html>
<html>
<title>TITLE</title>
<body>
BODY
</body>
</html>
"""


class ParserTest(TestCase):
    def testParser(self) -> None:
        c = pisaContext(".")
        r = pisaParser(_data, c)
        self.assertEqual(c, r)
        self.assertEqual(r.err, 0)
        self.assertEqual(r.warn, 0)

    def test_getFile(self) -> None:
        c = pisaContext(".")
        r = pisaParser(_data, c)
        self.assertEqual(c.getFile(None), None)
        self.assertEqual(r.err, 0)
        self.assertEqual(r.warn, 0)

    def test_height_as_list(self) -> None:
        """Asserts attributes like 'height: 10px !important" are parsed"""
        c = pisaContext(".")
        data = b"<p style='height: 10px !important;width: 10px !important'>test</p>"
        r = pisaParser(data, c)
        self.assertEqual(c, r)
        self.assertEqual(r.err, 0)
        self.assertEqual(r.warn, 0)

    def test_image_os_path(self) -> None:
        c = pisaContext(".")
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        img_path = os.path.join(tests_folder, "samples", "img", "denker.png")
        data = f'<img src="{img_path}">'.encode()
        r = pisaParser(data, c)
        self.assertEqual(c, r)
        self.assertEqual(r.err, 0)
        self.assertEqual(r.warn, 0)

    def test_image_base64(self) -> None:
        c = pisaContext(".")
        data = (
            b"<img"
            b' src="data:image/gif;base64,R0lGODlhAQABAIAAAAUEBAAAACwAAAAAAQABAAACAkQBADs=">'
        )
        r = pisaParser(data, c)
        self.assertEqual(r.warn, 0)

    def test_image_base64_urlencoded(self) -> None:
        c = pisaContext(".")
        data = (
            b"<img"
            b' src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAV4AAACWBAMAAABkyf1EAAAAG1BMVEXMzMyWlpacnJyqqqrFxcWxsbGjo6O3t7e%2Bvr6He3KoAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAEcElEQVR4nO2aTW%2FbRhCGh18ij1zKknMkbbf2UXITIEeyMhIfRaF1exQLA%2FJRclslRykO%2Brs7s7s0VwytNmhJtsA8gHZEcox9PTs7uysQgGEYhmEYhmEYhmEYhmEYhmEYhmEYhmEYhmEYhmEYhmGYr2OWRK%2FReIKI8Zt7Hb19wTcQ0uTkGh13bQupcw7gPOvdo12%2F5CzNtNR7xLUtNtT3CGBQ6g3InjY720pvofUec22LJPr8PhEp2OMPyI40PdwWUdronCu9yQpdPx53bQlfLKnfOVhlnDYRBXve4Ov%2BIZTeMgdedm0NR%2BxoXJeQvdJ3CvziykSukwil16W%2FOe7aGjIjqc%2F9ib4jQlJy0uArtN4A0%2BcvXFvDkmUJ47sJ1Y1ATLDNVXZkNPIepQzxy1ki9fqiwbUj%2FI%2B64zxWNzyZnPuhvohJ9K70VvXBixpcu2SAHU%2BXd9EKdEJDNpYP3AQr3bQSpPQ6Y6%2F4dl1z7ZDbArsszjA7L0g7ibB0CDcidUWVoErvIMKZh2Xs0LUzcLW6V5NfiUgNEbaYmAVL6bXl0nJRc%2B1S72ua%2FD%2FcTjGPlQj7eUqd7A096rYlRjdPYlhz7VIvxpVG3cemDKF%2BWAwLY%2F6XelOZKTXXzsC4xvDjjtSN6kHLhLke6PrwM8h1raf40qjrGO7H9aTEbduucjS04ZrYU%2F4iuS5Z2Hdt0rvCLFdmLEXcU30AGddST62o%2BsLcf5l6k7CP%2Bru4pLYqX%2FVFyxbm%2FutQbx%2Fr22ZEbTb2f5I2kns1Y1OQR8ZyofX%2BTjJxj1Rz7QQVnf1QzR26Oth0ueJVYcRP6ZUPac%2FRx%2F5M6ixO1dhSrT3Y1DpiYmx3tF4ZUdpz9LD%2FdSg9PXES0LB71BwcGjKROuV28lnvnv7HHJsezheBGH5%2BX2CfSfRbMKW%2B5aGs3JFjMrjGibJc0S7TJzqjHrh2hDybj9XRXNZa89Aro55XBdbW5wti2c%2F5WJ7jJ1RolVUn%2FHWpb0I58Tziup6Rx7Dm2hnbRP1GM9PW%2FNFmQ4PtVRVN63Wvxfmu5sowDMMwDMMwDMMwDMMwDMMwDMMwzL%2BCpT%2F%2FF%2F6beoV8zb2Jmt4Qryx6lTUCsENQ75HOkhXAO3EPVgyQtKtUy3C%2Fe%2BFJg17Zjnew1Xrdb9InbG4WqfUAftG%2BWhLwPVyfg536%2BMU7m4C1CMk4ZznpXZzDYI1PDL2nS1hpvc5cNd7E2sJg05Fe7%2F7d3Fln8Cvc3bwB616auxsKl4WPghjemHrDqyDWeu1UNW5s2btPnSQ75oOdunEwWazfwgVG0kqluYCM9OIjWOGnfA2b9G4Ha63XKpvQ8perTvTifJNhi6%2BWMWmi7smEZf6G8MmhlyGq%2BNqP8GV84TLuJr7UIQVx%2BbDEoEpRZIz42gs40OuN4Mv8hXzelV7KX1isH%2BewTWckikyVv%2BCfHuqVF7I16gN0VKypX6wPsE%2BzFPzkinolU9UH8OMGvSpnZqKsv13p%2FRsMun6X5x%2Fy2LeAr8O66lsBwzBMP%2FwJfyGq8pgBk6IAAAAASUVORK5CYII%3D">'
        )
        r = pisaParser(data, c)
        self.assertEqual(r.warn, 0)
