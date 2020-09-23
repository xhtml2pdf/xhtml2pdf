from io import BytesIO

import html5lib
import unittest
from xhtml2pdf.document import pisaDocument

__doc__="""
        arabic_font_support_tests provides us auxiliary functions to check 
        the correct operation of arabic fonts.
        """

class arabic_font_support_tests(unittest.TestCase):

    HTML_CONTENT = """
    <html>
    <head>
    <title></title>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

    <style type="text/css">

	    @font-face {
            font-family: DejaVuSans;
            src: url('../samples/font/DejaVuSans.ttf')
            }

        body {
    	    font-family: DejaVuSans;
		    background-color: red;
	    }
	    p.extra {
		    background-color: yellow;
		    line-height: 200%;
	    }
	    div {
		    background-color: orange;
	    }
	    table {
		    border: 2px solid black;
	    }
	    h1 {
		    page-break-before: always;
	    }

	    tr {
	    background-color:red;
	    }


    </style>
    </head>

    <body>
    <div>
        <pdf:language name="arabic"/>
        <span>رقم الغرفة:</span>
    </div>

    Test
    <p>
    Block 1
    <br>
    Neue Zeile
    <br><br>
      Und noch eine!
    <p class="extra">
    Block 2
    
    <div style="page-break-after: always;">
        DIV 1 BEGIN
    
        <div class="extra">
            INNERDIV A
    
            <p style="background-color: blue;">
            INNERP
    
        </div>
    
        DIV 1 END
    </div>
    
    (NEW PAGE?) AFTERDIV
    
    <h1>Heading 1(NEW PAGE?)</h1>
    
    AFTERH1
    
    <table>
        <tr>
            <td>رقم الغرفة:</td>
            <td>Oben rechts</td>
        </tr>
        <tr>
            <td>Unten links</td>
            <td>
    
    <table>
        <tr>
            <td>xxx links</td>
            <td>yyy rechts</td>
        </tr>
        <tr>
            <td>xxx links</td>
            <td>yyy rechts</td>
        </tr>
    </table>
    
            </td>
        </tr>
    </table>
    
    <p>
    ENDE
    </p>
    </body>
    </html>
    """


    def test_arabic_check_pdf_language_tag(self):
        """
            this function is used to check if the "Custom Tag" <pdf:language/>
            is located in the document through asssertNotEqual()
        """

        html = self.HTML_CONTENT

        parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
        document = parser.parse(html)
        tag_element = document.getElementsByTagName("pdf:language")
        self.assertNotEqual(tag_element,[])

    def test_arabic_check_language_in_pdf(self):
        """
            this function is used to check if the "attr language" is
            is located in the pdf result.
        """
        html = self.HTML_CONTENT
        res = False
        result = BytesIO()

        pdf = pisaDocument(BytesIO(html.encode('utf-8')), result)
        if hasattr(pdf,'language'):
            res = True
        self.assertTrue(res)

