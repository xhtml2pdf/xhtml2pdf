from io import BytesIO
from unittest import TestCase

from xhtml2pdf.context import pisaContext
from xhtml2pdf.parser import pisaParser


class TableTest(TestCase):
    def test_empty_table(self) -> None:
        """
        Test, if an empty table will return an empty story;
        This will also raise a log.warning()
        """
        html = """
        <html>
        <head>
        </head>
        <body>
            <table>
            </table>
        </body>
        </html>
        """

        with self.assertLogs("xhtml2pdf.tables", level="DEBUG") as cm:
            context = pisaParser(BytesIO(html.encode("utf-8")), pisaContext())

            self.assertEqual(
                context.story, [], "Empty table doesn't return an empty story!"
            )
            self.assertEqual(
                cm.output,
                [
                    "DEBUG:xhtml2pdf.tables:Col widths: []",
                    "WARNING:xhtml2pdf.tables:<table> is empty\n'<table> </table>'",
                ],
            )

    def test_tr_background_color(self) -> None:
        """
        Test background on <tr> tag;
        If it works, "darkgreen" will be returned as hexval "0x006400"
        """
        html = """
        <html>
        <head>
            <style>
            tr { background-color: darkgreen }
            </style>
        </head>
        <body>
            <table>
                <tr>
                    <td>Test</td>
                </tr>
            </table>
        </body>
        </html>
        """

        context = pisaParser(BytesIO(html.encode("utf-8")), pisaContext())
        table = context.story[0]
        color = table._bkgrndcmds[0][3]
        self.assertEqual(
            color.hexval(),
            "0x006400",
            '"background-color" in CSS not equal with output!',
        )

    def test_td_colspan(self) -> None:
        """
        Test colspan on <td> tag;
        If it works, colspan="3" will be equal to (2, 0) in _spanCmds of the ReportLab table
        """
        html = """
        <html>
        <head>
            <style>
            </style>
        </head>
        <body>
            <table>
                <tr>
                    <td colspan="3">AAAAAAAAAAAA</td>
                </tr>
                <tr>
                    <td>BBB</td>
                    <td>CCC</td>
                    <td>DDD</td>
                </tr>
            </table>
        </body>
        </html>
        """

        context = pisaParser(BytesIO(html.encode("utf-8")), pisaContext())
        table = context.story[0]
        col_span = table._spanCmds[0][2]

        self.assertEqual(
            col_span, (2, 0), '"colspan=" not working properly in the <td> tag!'
        )

    def test_td_rowspan(self) -> None:
        """
        Test rowspan on <td> tag;
        If it works, rowspan="3" will be equal to (0, 2) in _spanCmds of the ReportLab table
        """
        html = """
        <html>
        <head>
            <style>
            </style>
        </head>
        <body>
            <table>
                <tr>
                    <td rowspan="3">AAAAAAAAAAAA</td>
                    <td>BBB</td>
                </tr>
                <tr>
                    <td>CCC</td>
                </tr>
                <tr>
                    <td>DDD</td>
                </tr>
            </table>
        </body>
        </html>
        """

        context = pisaParser(BytesIO(html.encode("utf-8")), pisaContext())
        table = context.story[0]
        row_span = table._spanCmds[0][2]

        self.assertEqual(
            row_span, (0, 2), '"rowspan=" not working properly in the <td> tag!'
        )

    def test_td_width_and_height(self) -> None:
        """
        Test width and height on <td> tag;
        If it works, width: 2pt will be equal to 2.0 and height: 3pt will be equal to 3.0 in the ReportLab table
        """
        html = """
        <html>
        <head>
            <style>
            td { width: 2pt; height: 3pt }
            </style>
        </head>
        <body>
            <table>
                <tr>
                    <td>AAA</td>
                    <td>BBB</td>
                </tr>
                <tr>
                    <td>CCC</td>
                    <td>DDD</td>
                </tr>
            </table>
        </body>
        </html>
        """

        context = pisaParser(BytesIO(html.encode("utf-8")), pisaContext())
        table = context.story[0]
        col_widths = table._colWidths
        row_heights = table._rowHeights

        for width in col_widths:
            self.assertEqual(width, 2.0, "<td> width in CSS not equal with output!")
        for height in row_heights:
            self.assertEqual(height, 3.0, "<td> height in CSS not equal with output!")
