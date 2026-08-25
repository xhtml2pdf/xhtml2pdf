#!/usr/bin/env python3
"""
Compare xhtml2pdf output against a browser rendering the equivalent markup.

testrender.py compares xhtml2pdf against itself: the reference is produced by
the same library, so it detects changes in the output but never whether that
output is right. This harness introduces an external reference.

Each case has two sources that express the same intended result:

    data/source/<name>.html    fed to xhtml2pdf, may use <pdf:*>, @frame, -pdf-*
    data/browser/<name>.html   fed to Chromium, plain HTML/CSS

xhtml2pdf-only constructs are expressed with ordinary markup on the browser
side: @frame becomes absolute positioning, <pdf:toc> a hand-written list,
<pdf:pagenumber> a counter() in an @page margin box. Both sides are printed to
PDF with the same page geometry and rasterised by the same ghostscript, then
compared structurally (pagination and text) and perceptually (SSIM).

Because the two engines will never agree exactly, the check is not a fixed
threshold: scores are recorded in data/baseline.json and the run fails when a
score regresses against what was recorded.

The browser runs headless, so no window appears. See BrowserRenderer.FLAGS.
"""

from __future__ import annotations

import base64
import difflib
import json
import os
import re
import shutil
import sys
from optparse import OptionParser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self

sys.path.insert(0, str(Path(__file__).resolve().parent))

import testrender

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SOURCE_DIR = DATA_DIR / "source"
BROWSER_DIR = DATA_DIR / "browser"
MANIFEST = DATA_DIR / "manifest.toml"
BASELINE = DATA_DIR / "baseline.json"

#: A4 in centimetres, the unit the W3C print command uses.
A4_CM = (21.0, 29.7)

#: Default page margin, in centimetres. xhtml2pdf builds its default body frame
#: from getBox("1cm 1cm -1cm -1cm", pageSize) in xhtml2pdf/document.py:171, so a
#: document that declares no @page gets 1cm on all four sides. The browser has
#: to be asked for the same, or every fixture differs by a constant offset.
DEFAULT_MARGIN_CM = 1.0

#: How far a score may fall below the recorded baseline before it is a failure.
#: Scores are exactly reproducible on a given machine, so this only has to
#: absorb the difference between machines; it is not slack for real regressions.
DEFAULT_TOLERANCE = 0.01


def load_toml(path: Path) -> dict:
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover
        import tomli as tomllib
    with path.open("rb") as handle:
        return tomllib.load(handle)


# ---------------------------------------------------------------- browser side


class BrowserRenderer:
    """Prints a local HTML file to PDF with headless Chromium."""

    #: Flags chosen for determinism as much as for headlessness. The browser is
    #: the reference, so anything that makes its rasterisation vary between
    #: machines moves the baseline for reasons unrelated to xhtml2pdf.
    FLAGS = (
        # No window is created at all, and the X server is never touched.
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        # A HiDPI desktop would otherwise change the output.
        "--force-device-scale-factor=1",
        # Subpixel antialiasing adds colour fringing that wrecks comparison
        # against ghostscript's greyscale rasterisation.
        "--disable-lcd-text",
        # Makes glyph rasterisation reproducible across machines.
        "--font-render-hinting=none",
        "--run-all-compositor-stages-before-draw",
        "--disable-dev-shm-usage",
    )

    # NB: --virtual-time-budget must NOT be added here. It belongs to the
    # `chromium --print-to-pdf` CLI mode; in a driven session it tears the
    # renderer down and print_page() then fails with NoSuchWindowException.

    #: Waits for webfonts and images before printing, which --virtual-time-budget
    #: would otherwise have covered.
    READY_SCRIPT = (
        "const done = arguments[0];"
        "Promise.all(["
        "  document.fonts.ready,"
        "  ...[...document.images].filter(i => !i.complete)"
        "      .map(i => new Promise(r => { i.onload = i.onerror = r; }))"
        "]).then(() => done(true));"
    )

    def __init__(
        self,
        *,
        headed: bool = False,
        binary: str | None = None,
        driver: str | None = None,
    ) -> None:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        if binary:
            options.binary_location = binary
        for flag in self.FLAGS:
            if flag == "--headless=new" and headed:
                continue
            options.add_argument(flag)
        if os.environ.get("CI"):
            options.add_argument("--no-sandbox")

        self._driver = webdriver.Chrome(
            service=Service(driver) if driver else Service(), options=options
        )

    @property
    def version(self) -> str:
        caps = self._driver.capabilities
        return f"{caps.get('browserName', 'chrome')} {caps.get('browserVersion', '?')}"

    def render(self, html_path: Path, out_pdf: Path) -> None:
        from selenium.webdriver.common.print_page_options import PrintOptions

        self._driver.get(html_path.resolve().as_uri())
        self._driver.execute_async_script(self.READY_SCRIPT)

        print_options = PrintOptions()
        print_options.page_width, print_options.page_height = A4_CM
        print_options.margin_top = DEFAULT_MARGIN_CM
        print_options.margin_bottom = DEFAULT_MARGIN_CM
        print_options.margin_left = DEFAULT_MARGIN_CM
        print_options.margin_right = DEFAULT_MARGIN_CM
        # xhtml2pdf paints backgrounds; a browser drops them when printing
        # unless asked, which would make every coloured fixture diverge.
        print_options.background = True
        print_options.scale = 1.0
        print_options.shrink_to_fit = False

        out_pdf.write_bytes(base64.b64decode(self._driver.print_page(print_options)))

    def close(self) -> None:
        self._driver.quit()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


# ------------------------------------------------------------------- metrics


def ssim(path_a: Path, path_b: Path) -> float:
    """
    Structural similarity between two page images, in [-1, 1].

    Implemented here on numpy rather than pulling in scikit-image for a single
    function. Uses the 11x11 gaussian window and the C1/C2 constants from Wang
    et al. (2004), which is what scikit-image's default configuration uses.
    """
    import numpy as np
    from PIL import Image

    def load(path: Path) -> np.ndarray:
        return np.asarray(Image.open(path).convert("L"), dtype=np.float64)

    img_a, img_b = load(path_a), load(path_b)
    if img_a.shape != img_b.shape:
        height = min(img_a.shape[0], img_b.shape[0])
        width = min(img_a.shape[1], img_b.shape[1])
        img_a, img_b = img_a[:height, :width], img_b[:height, :width]

    # separable 11x11 gaussian, sigma 1.5
    radius, sigma = 5, 1.5
    offsets = np.arange(-radius, radius + 1)
    kernel = np.exp(-(offsets**2) / (2 * sigma**2))
    kernel /= kernel.sum()

    def blur(img: np.ndarray) -> np.ndarray:
        padded = np.pad(img, radius, mode="symmetric")
        rows = np.stack(
            [padded[i : i + img.shape[0], :] for i in range(2 * radius + 1)]
        )
        horizontal = np.tensordot(kernel, rows, axes=(0, 0))
        cols = np.stack(
            [horizontal[:, i : i + img.shape[1]] for i in range(2 * radius + 1)]
        )
        return np.tensordot(kernel, cols, axes=(0, 0))

    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mu_a, mu_b = blur(img_a), blur(img_b)
    mu_a_sq, mu_b_sq, mu_ab = mu_a**2, mu_b**2, mu_a * mu_b
    sigma_a = blur(img_a**2) - mu_a_sq
    sigma_b = blur(img_b**2) - mu_b_sq
    sigma_ab = blur(img_a * img_b) - mu_ab

    numerator = (2 * mu_ab + c1) * (2 * sigma_ab + c2)
    denominator = (mu_a_sq + mu_b_sq + c1) * (sigma_a + sigma_b + c2)
    return float(np.mean(numerator / denominator))


_WS = re.compile(r"\s+")

#: Control characters are dropped before comparing. Neither engine means them
#: as content: a browser PDF yields NUL for glyphs it embedded without a usable
#: ToUnicode mapping (any CJK text with no font installed).
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

#: Unordered list markers, dropped from both sides before comparing.
#:
#: Chromium's print-to-PDF puts no ::marker content in the text stream at all,
#: so a marker present on the xhtml2pdf side is not a difference in content --
#: it is xhtml2pdf being the more complete of the two, and penalising it would
#: reward going back to leaving markers out. An ordered marker cannot be
#: filtered the same way, since "a." is indistinguishable from content, so
#: those do show up in the score; data/manifest.toml says so for
#: css-list-style.
_LIST_MARKERS = re.compile(r"[\u2022\u25a0\u25aa\u25e6\u25cb\u25cf]")


def page_texts(pdf_path: Path) -> list[str]:
    from pypdf import PdfReader

    return [
        _WS.sub(
            " ", _LIST_MARKERS.sub("", _CONTROL.sub("", page.extract_text() or ""))
        ).strip()
        for page in PdfReader(str(pdf_path)).pages
    ]


def text_similarity(left: str, right: str) -> float:
    """
    Similarity of two extracted texts, ignoring whitespace entirely.

    Comparing word by word would measure an extraction artifact rather than the
    content: Chromium's PDF emits no space where a line wraps, so "consectetur
    adipisicing" comes back as "consecteturadipisicing" and every wrapped line
    looks like two wrong words. Collapsing whitespace away and comparing the
    character sequence asks the question that actually matters here -- are the
    same characters present, in the same order.
    """
    left, right = _WS.sub("", left), _WS.sub("", right)
    if not left and not right:
        return 1.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def headings_by_page(pdf_path: Path, headings: list[str]) -> dict[str, list[int]]:
    """
    Map each expected heading to every 1-based page it appears on.

    Every page, not the first one: a table of contents repeats each heading at
    the front of the document, so "the first page containing this text" is page
    1 for all of them and the check passes without proving anything. Comparing
    the full set of pages catches both a heading that moved and a table of
    contents that lost an entry.
    """
    pages = page_texts(pdf_path)
    return {
        heading: [
            n
            for n, text in enumerate(pages, 1)
            if _WS.sub("", heading).lower() in _WS.sub("", text).lower()
        ]
        for heading in headings
    }


# ------------------------------------------------------------------ comparing


def compare_fixture(name: str, config: dict, options) -> dict:
    """Render both sides, measure, and return the score record for one fixture."""
    output_dir = Path(options.output_dir)
    checks = config.get("compare", ["pages", "text", "ssim"])
    result: dict = {"name": name, "checks": checks, "problems": [], "observations": []}

    pdf_pisa = Path(
        testrender.render_pdf(
            str(SOURCE_DIR / name) + ".html", str(output_dir), options
        )
    )
    pdf_browser = output_dir / f"{name}.browser.pdf"
    options.browser.render(BROWSER_DIR / f"{name}.html", pdf_browser)

    texts_pisa, texts_browser = page_texts(pdf_pisa), page_texts(pdf_browser)
    result["pages"] = {"xhtml2pdf": len(texts_pisa), "browser": len(texts_browser)}

    # A page-count difference against the browser is an observation, not a
    # failure: xhtml2pdf is not a browser engine and the two legitimately break
    # pages differently, especially around overflow. What must not change is
    # xhtml2pdf's own page count, which is checked against the baseline.
    if "pages" in checks and len(texts_pisa) != len(texts_browser):
        result["observations"].append(
            f"paginates differently: xhtml2pdf {len(texts_pisa)} pages, "
            f"browser {len(texts_browser)}"
        )

    if "text" in checks:
        # Two separate questions, deliberately scored apart:
        #
        #   text      worst page, so it drops as soon as content lands on a
        #             different page than the browser puts it on
        #   text_doc  the whole document, which stays high when all the content
        #             is present and in the same order but paginated differently
        #
        # A fixture where text is low and text_doc is high has a pagination
        # difference; one where both are low is missing or reordering content.
        common = min(len(texts_pisa), len(texts_browser))
        per_page = [
            text_similarity(texts_pisa[i], texts_browser[i]) for i in range(common)
        ]
        result["text"] = round(min(per_page), 4) if per_page else 0.0
        result["text_per_page"] = [round(v, 4) for v in per_page]
        result["text_doc"] = round(
            text_similarity(" ".join(texts_pisa), " ".join(texts_browser)), 4
        )

    if "headings" in checks:
        expected = config.get("headings", [])
        left = headings_by_page(pdf_pisa, expected)
        right = headings_by_page(pdf_browser, expected)
        misplaced = {h: (left[h], right[h]) for h in expected if left[h] != right[h]}
        result["headings"] = {
            "expected": len(expected),
            "misplaced": {
                h: {"xhtml2pdf": a, "browser": b} for h, (a, b) in misplaced.items()
            },
        }
        for heading, (a, b) in misplaced.items():
            result["problems"].append(
                f"heading {heading!r} on pages {a or 'none'} in xhtml2pdf "
                f"but {b or 'none'} in browser"
            )

    if "ssim" in checks:
        pngs_pisa = testrender.convert_to_png(str(pdf_pisa), str(output_dir), options)
        pngs_browser = testrender.convert_to_png(
            str(pdf_browser), str(output_dir), options
        )
        # zip() stops at the shorter side on purpose: a page-count mismatch is
        # already reported by the "pages" check, and the pages they do have in
        # common are still worth scoring.
        scores = [
            round(ssim(Path(a), Path(b)), 4)
            for a, b in zip(pngs_pisa, pngs_browser, strict=False)
        ]
        result["ssim"] = round(min(scores), 4) if scores else 0.0
        result["ssim_per_page"] = scores
        result["images"] = {"xhtml2pdf": pngs_pisa, "browser": pngs_browser}

    return result


def baseline_entry(result: dict) -> dict:
    """
    The part of a result that is recorded, and therefore enforced.

    Only xhtml2pdf's own page count is kept. A difference against the browser
    is already reported as an observation, and recording the browser's count
    would turn a browser upgrade into an apparent xhtml2pdf regression. What
    must not drift is the number of pages this library produces for a fixture.
    """
    entry: dict = {"pages": {"xhtml2pdf": result["pages"]["xhtml2pdf"]}}
    entry.update({k: result[k] for k in ("text", "text_doc", "ssim") if k in result})
    return entry


def check_against_baseline(
    results: list[dict], baseline: dict, tolerance: float
) -> list[str]:
    """Return a list of regressions relative to the recorded scores."""
    failures: list[str] = []
    recorded = baseline.get("fixtures", {})
    for result in results:
        failures.extend(f"{result['name']}: {p}" for p in result["problems"])
        previous = recorded.get(result["name"])
        if not previous:
            continue

        was = (previous.get("pages") or {}).get("xhtml2pdf")
        now = result["pages"]["xhtml2pdf"]
        if was is not None and was != now:
            failures.append(
                f"{result['name']}: xhtml2pdf page count changed {was} -> {now}"
            )

        for metric in ("text", "text_doc", "ssim"):
            if metric not in result or metric not in previous:
                continue
            drop = previous[metric] - result[metric]
            if drop > tolerance:
                failures.append(
                    f"{result['name']}: {metric} regressed "
                    f"{previous[metric]:.4f} -> {result[metric]:.4f} "
                    f"(tolerance {tolerance})"
                )
    return failures


# -------------------------------------------------------------------- report


def write_report(results: list[dict], output_dir: Path, browser: str) -> Path:
    """Write a side-by-side HTML report of every compared page."""

    def image_pairs(result: dict) -> str:
        images = result.get("images")
        if not images:
            return ""
        blocks = []
        pairs = zip(
            images.get("xhtml2pdf", []), images.get("browser", []), strict=False
        )
        for index, (left, right) in enumerate(pairs):
            score = result.get("ssim_per_page", [])
            caption = f"page {index + 1}"
            if index < len(score):
                caption += f" &middot; ssim {score[index]}"
            blocks.append(
                f"<div class='pair'><div class='caption'>{caption}</div>"
                f"<figure><img src='{Path(left).name}' loading='lazy'>"
                f"<figcaption>xhtml2pdf</figcaption></figure>"
                f"<figure><img src='{Path(right).name}' loading='lazy'>"
                f"<figcaption>browser</figcaption></figure></div>"
            )
        return "".join(blocks)

    rows = []
    for result in results:
        pages = result["pages"]
        notes = [f"<strong>{p}</strong>" for p in result["problems"]]
        notes += [f"<em>{o}</em>" for o in result["observations"]]
        problems = "<br>".join(notes) or "ok"
        row_class = (
            " class='error'"
            if result["problems"]
            else (" class='note'" if result["observations"] else "")
        )
        rows.append(
            f"<tr{row_class}><td>{result['name']}</td>"
            f"<td>{pages['xhtml2pdf']} / {pages['browser']}</td>"
            f"<td>{result.get('text', '-')}</td>"
            f"<td>{result.get('text_doc', '-')}</td>"
            f"<td>{result.get('ssim', '-')}</td>"
            f"<td>{problems}</td></tr>"
        )
        images = image_pairs(result)
        if images:
            rows.append(f"<tr><td colspan='6'>{images}</td></tr>")

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>xhtml2pdf vs browser</title><style>
body {{ font-family: sans-serif; margin: 2em; color: #222; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: .4em .6em; text-align: left;
          vertical-align: top; }}
th {{ background: #f4f4f4; }}
tr.error {{ background: #fee; }}
tr.note {{ background: #ffd; }}
.pair {{ display: flex; gap: 1em; margin: .8em 0; align-items: flex-start; }}
.pair img {{ max-width: 30vw; border: 1px solid #ddd; }}
.caption {{ min-width: 12em; font-size: .85em; color: #555; }}
figcaption {{ font-size: .8em; color: #666; text-align: center; }}
</style></head><body>
<h1>xhtml2pdf vs browser</h1>
<p>Reference: <strong>{browser}</strong>. Each fixture is scored by its worst
page. The two engines never agree exactly, so what matters is whether the
agreement gets worse over time, not the absolute number.</p>
<table><tr><th>fixture</th><th>pages<br>xhtml2pdf / browser</th>
<th>text<br>worst page</th><th>text<br>document</th><th>ssim</th>
<th>problems</th></tr>
{"".join(rows)}
</table></body></html>"""

    report = output_dir / "browser-compare.html"
    report.write_text(html, encoding="utf-8")
    return report


# ---------------------------------------------------------------------- main

parser = OptionParser(
    usage="browsercompare.py [options]",
    description=(
        "Compare xhtml2pdf output against a browser rendering the equivalent "
        "markup from data/browser/, and check the scores against data/baseline.json."
    ),
)
parser.add_option(
    "--only", dest="only", default=None, help="Compare a single fixture by name"
)
parser.add_option(
    "--update-baseline",
    dest="update_baseline",
    action="store_true",
    default=False,
    help="Record the current scores as the new baseline",
)
parser.add_option(
    "--tolerance",
    dest="tolerance",
    type="float",
    default=DEFAULT_TOLERANCE,
    help="How far a score may drop before it fails (default %default)",
)
parser.add_option(
    "--headed",
    dest="headed",
    action="store_true",
    default=False,
    help="Run the browser with a visible window, for debugging",
)
parser.add_option(
    "--report",
    dest="report",
    action="store_true",
    default=False,
    help="Write an HTML report with side-by-side page images",
)
parser.add_option(
    "--browser-binary",
    dest="browser_binary",
    default=None,
    help="Path to the browser binary",
)
parser.add_option(
    "--browser-driver",
    dest="browser_driver",
    default=None,
    help="Path to the webdriver binary",
)
parser.add_option(
    "-o",
    "--output-dir",
    dest="output_dir",
    default=str(BASE_DIR / "output"),
    help="Where to write PDFs, images and the report",
)
parser.add_option(
    "--convert-cmd",
    dest="convert_cmd",
    default="/usr/bin/convert",
    help='Path to ImageMagick "convert"',
)
parser.add_option("--debug", dest="debug", action="store_true", default=False)


def main() -> int:
    options, _args = parser.parse_args()

    # testrender's helpers log through its module-level Printer.
    options.quiet = not options.debug
    options.only_errors = False
    options.nofail = True
    options.remove_transparencies = True
    testrender.pprint.setOptions(options)

    if not MANIFEST.is_file():
        sys.stderr.write(f"Manifest not found: {MANIFEST}\n")
        return 2

    manifest = load_toml(MANIFEST)
    fixtures = manifest.get("fixtures", {})
    if options.only:
        if options.only not in fixtures:
            sys.stderr.write(
                f"{options.only!r} is not in the manifest. Known: "
                f"{', '.join(sorted(fixtures))}\n"
            )
            return 2
        fixtures = {options.only: fixtures[options.only]}

    missing = [n for n in fixtures if not (BROWSER_DIR / f"{n}.html").is_file()]
    if missing:
        sys.stderr.write(
            "No browser equivalent for: " + ", ".join(missing) + "\n"
            f"Each fixture in the manifest needs a {BROWSER_DIR.name}/<name>.html\n"
        )
        return 2

    output_dir = Path(options.output_dir)
    if output_dir.is_dir():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    baseline = json.loads(BASELINE.read_text()) if BASELINE.is_file() else {}

    results = []
    with BrowserRenderer(
        headed=options.headed,
        binary=options.browser_binary,
        driver=options.browser_driver,
    ) as browser:
        options.browser = browser
        print(f"Reference browser: {browser.version}")
        for name, config in sorted(fixtures.items()):
            print(f"  {name} ... ", end="", flush=True)
            result = compare_fixture(name, config, options)
            results.append(result)
            print(
                f"pages {result['pages']['xhtml2pdf']}/{result['pages']['browser']}"
                f"  text {result.get('text', '-')}"
                f"  doc {result.get('text_doc', '-')}"
                f"  ssim {result.get('ssim', '-')}"
            )
        browser_version = browser.version

    if options.report:
        report = write_report(results, output_dir, browser_version)
        print(f"Report: {report}")

    if options.update_baseline:
        BASELINE.write_text(
            json.dumps(
                {
                    "browser": browser_version,
                    "note": (
                        "text and ssim are the worst page of a fixture; text_doc "
                        "is the whole document, so the two differ when content is "
                        "all present but paginated differently. pages records "
                        "xhtml2pdf's own page count only. The browser is the "
                        "reference, so pin its version: a browser upgrade moves "
                        "these numbers without xhtml2pdf changing."
                    ),
                    "fixtures": {r["name"]: baseline_entry(r) for r in results},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Baseline updated: {BASELINE}")
        return 0

    recorded_browser = baseline.get("browser")
    if baseline and recorded_browser != browser_version:
        # The browser IS the reference. Comparing today's scores against a
        # baseline recorded with a different build measures the browser
        # upgrade, not xhtml2pdf, so enforcement is meaningless here. Say so
        # loudly rather than emitting a green tick or a false failure.
        print(
            f"\nBaseline was recorded with {recorded_browser!r} but this run used "
            f"{browser_version!r}.\nScores are not comparable across browser "
            f"builds, so nothing is enforced. Re-record with --update-baseline "
            f"on a machine\nwhose browser and fonts you intend to treat as the "
            f"reference.",
            file=sys.stderr,
        )
        return 0

    failures = check_against_baseline(results, baseline, options.tolerance)
    if failures:
        print("\nRegressions:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    if not baseline:
        print("\nNo baseline recorded yet. Run with --update-baseline to create one.")
    else:
        print("\nNo regressions against the recorded baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
