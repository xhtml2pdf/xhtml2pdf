"""Coverage for the background image builder."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from PIL import Image

from xhtml2pdf.builders.watermarks import WaterMarks
from xhtml2pdf.files import cleanFiles, pisaFileObject


class BackgroundOpacityTestCase(TestCase):
    """
    background-opacity fades an image; it does not flatten what was cut out.

    putalpha with a single number replaces the whole alpha channel, so the
    fully transparent pixels of a cut-out PNG -- black, as a rule -- came out
    half opaque and the page carried a grey rectangle instead of the faded
    figure.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "probe.png"
        # Half cut out, half solid red.
        image = Image.new("RGBA", (4, 2), (255, 0, 0, 255))
        image.putpixel((0, 0), (0, 0, 0, 0))
        image.putpixel((1, 0), (0, 0, 0, 0))
        image.save(self.path)

    def tearDown(self) -> None:
        # Each pisaFileObject leaves a temp file behind otherwise.
        cleanFiles()
        self.tmp.cleanup()

    def faded(self, opacity: float | None) -> Image.Image:
        result = WaterMarks.get_img_with_opacity(
            pisaFileObject(str(self.path)), {"opacity": opacity}
        )
        result.seek(0)
        return Image.open(result).convert("RGBA")

    @staticmethod
    def alphas(image: Image.Image) -> set[int]:
        return {pixel[3] for pixel in image.getdata()}

    def test_a_cut_out_pixel_stays_cut_out(self) -> None:
        self.assertIn(0, self.alphas(self.faded(0.5)))

    def test_the_opaque_part_is_faded(self) -> None:
        self.assertIn(127, self.alphas(self.faded(0.5)))

    def test_a_fully_opaque_image_behaves_as_before(self) -> None:
        Image.new("RGBA", (4, 2), (255, 0, 0, 255)).save(self.path)

        self.assertEqual({127}, self.alphas(self.faded(0.5)))

    def test_no_opacity_leaves_the_image_alone(self) -> None:
        self.assertEqual({0, 255}, self.alphas(self.faded(None)))
