from nose import tools

from xhtml2pdf.w3c.css import CSSBuilder, CSSParser


def test_selector_lt():
    # test html:
    # <html>
    #   <head>
    #     <style>
    #         p { color: yellow;}
    #         .red { color: red;}
    #     </style>
    #   </head>
    #   <body>
    #       <p>I want to be yellow</p>
    #       <p class="red">I want to be red</p>
    #   </body>
    # </html>

    general_css = "p { color: yellow;}"
    specific_css = ".red { color: red;}"

    parser = CSSParser(CSSBuilder(mediumSet=['pdf']))

    general_selector = list(parser.parse(general_css)[0].keys())[0]
    specific_selector = list(parser.parse(specific_css)[0].keys())[0]

    tools.assert_false(specific_selector < general_selector)
