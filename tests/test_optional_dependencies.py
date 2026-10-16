"""
xhtml2pdf without pyHanko, or with an svglib that cannot be imported.

pyHanko is the ``signing`` extra, not installed with xhtml2pdf itself.
Without it a document still renders and a signature asks for the extra by
name. Without svglib an SVG image is left out with a warning that says why.

Each case runs in a fresh interpreter in which importing the missing
package fails, as it does where it is not installed.
"""

import subprocess
import sys
import textwrap
from unittest import TestCase

BLOCK = """
import sys
for name in {blocked!r}:
    sys.modules[name] = None
"""

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    '<rect width="10" height="10" fill="red"/></svg>'
)


def run(blocked: tuple[str, ...], code: str) -> subprocess.CompletedProcess:
    script = BLOCK.format(blocked=blocked) + textwrap.dedent(code)
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


class WithoutPyHankoTest(TestCase):
    BLOCKED = ("pyhanko", "pyhanko_certvalidator")

    def test_a_document_renders(self) -> None:
        result = run(
            self.BLOCKED,
            """
            import io
            from xhtml2pdf import pisa
            out = io.BytesIO()
            print(pisa.CreatePDF("<p>hello</p>", dest=out).err)
            """,
        )
        self.assertEqual("0", result.stdout.strip(), result.stderr)

    def test_a_signature_asks_for_the_extra(self) -> None:
        result = run(
            self.BLOCKED,
            """
            import io
            from xhtml2pdf import pisa
            try:
                pisa.CreatePDF(
                    "<p>hello</p>", dest=io.BytesIO(), signature={"type": "simple"}
                )
            except ImportError as e:
                print(e)
            """,
        )
        self.assertIn("xhtml2pdf[signing]", result.stdout, result.stderr)


class WithoutSvglibTest(TestCase):
    def test_an_svg_image_is_left_out_with_the_reason(self) -> None:
        result = run(
            ("svglib",),
            f"""
            import base64, io
            from xhtml2pdf import pisa
            uri = "data:image/svg+xml;base64," + base64.b64encode({SVG!r}.encode()).decode()
            html = f'<p>before</p><img src="{{uri}}"/><p>after</p>'
            print(pisa.CreatePDF(html, dest=io.BytesIO()).err)
            """,
        )
        self.assertEqual("0", result.stdout.strip(), result.stderr)
        self.assertIn("pip install svglib", result.stderr)
