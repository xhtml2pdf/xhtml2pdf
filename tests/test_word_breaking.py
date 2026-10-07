"""
Where a word may be broken: overflow-wrap, word-wrap and word-break (#339).

A word wider than its line used to run off the page whatever the stylesheet
said; only -pdf-word-wrap: CJK, which breaks every word anywhere, kept it in.
"""

from unittest import TestCase

from xhtml2pdf.document import pisaStory

LONG = "x" * 40 + "w" * 40 + "m" * 40
WIDTH = 200


def _str(text: str | bytes) -> str:
    return text.decode("utf8") if isinstance(text, bytes) else text


def _lines(html: str) -> list[tuple[float, str]]:
    """(unused width, text) of every line of every paragraph, at WIDTH points."""
    lines = []
    for flowable in pisaStory(html).story:
        if not hasattr(flowable, "blPara") and not hasattr(flowable, "breakLines"):
            continue
        flowable.wrap(WIDTH, 10_000)
        para = flowable.blPara
        for line in para.lines:
            if para.kind == 0:
                extra, words = line
                lines.append((extra, " ".join(map(_str, words))))
            else:
                text = "".join(_str(w.text) for w in line.words)
                lines.append((line.extraSpace, text))
    return lines


class OverflowWrapTest(TestCase):
    def test_a_long_word_is_kept_whole_by_default(self) -> None:
        lines = _lines(f"<p>a {LONG} b</p>")
        self.assertTrue(any(extra < 0 for extra, _ in lines))

    def test_break_word_splits_a_long_word_to_the_line(self) -> None:
        for css in (
            "overflow-wrap: break-word",
            "overflow-wrap: anywhere",
            "word-wrap: break-word",
            "word-break: break-word",
        ):
            with self.subTest(css=css):
                lines = _lines(f'<p style="{css}">before {LONG} after</p>')
                self.assertTrue(all(extra >= -0.01 for extra, _ in lines), lines)
                text = "".join(t for _, t in lines).replace(" ", "")
                self.assertEqual(f"before{LONG}after", text)

    def test_only_the_long_word_is_broken(self) -> None:
        lines = _lines(f'<p style="overflow-wrap: break-word">short {LONG} words</p>')
        texts = [t for _, t in lines]
        self.assertEqual("short", texts[0].strip())
        self.assertTrue(texts[-1].strip().endswith("words"))

    def test_on_an_inline_element(self) -> None:
        # -pdf-word-wrap is read for the whole paragraph, so it never worked
        # on an <a>; overflow-wrap belongs to the text.
        lines = _lines(
            f'<p>see <a href="https://x.org/{LONG}" style="overflow-wrap: anywhere">'
            f"https://x.org/{LONG}</a> here</p>"
        )
        self.assertTrue(all(extra >= -0.01 for extra, _ in lines), lines)

    def test_with_text_glued_to_the_element(self) -> None:
        # The "." after the link, or the "(" before it, is the same word as
        # the link's text but is not the link's: it is never broken off.
        url = f"https://x.org/{LONG}"
        cases = {
            "after a link": (f'<a href="{url}" class="w">{url}</a>. end', f"{url}.end"),
            "after a span": (f'<span class="w">{url}</span>. end', f"{url}.end"),
            "before a link": (
                f'(<a href="{url}" class="w">{url}</a> end',
                f"({url}end",
            ),
        }
        for name, (body, text) in cases.items():
            with self.subTest(name):
                lines = _lines(
                    f"<style>.w {{ overflow-wrap: anywhere }}</style><p>{body}</p>"
                )
                self.assertGreater(len(lines), 2)
                self.assertTrue(all(extra >= -0.01 for extra, _ in lines), lines)
                self.assertEqual(text, "".join(t for _, t in lines).replace(" ", ""))
                if name.startswith("after"):
                    self.assertTrue(lines[-1][1].startswith("m"), lines)
                    self.assertIn("m. end", lines[-1][1])
                else:
                    self.assertTrue(lines[0][1].startswith("(h"), lines)

    def test_with_an_anchor_inside(self) -> None:
        # A marker inside the word, here a named anchor, is kept and does not
        # stop the word from being broken.
        lines = _lines(
            f'<p style="overflow-wrap: anywhere">{LONG}<a name="here"></a>{LONG}</p>'
        )
        self.assertTrue(all(extra >= -0.01 for extra, _ in lines), lines)
        self.assertEqual(LONG * 2, "".join(t for _, t in lines).replace(" ", ""))

    def test_across_fragments(self) -> None:
        lines = _lines(
            f'<p style="overflow-wrap: break-word">a <b>{LONG}</b>{LONG} b</p>'
        )
        self.assertTrue(all(extra >= -0.01 for extra, _ in lines), lines)

    def test_inherited(self) -> None:
        lines = _lines(f'<div style="overflow-wrap: break-word"><p>{LONG}</p></div>')
        self.assertTrue(all(extra >= -0.01 for extra, _ in lines), lines)

    def test_normal_turns_it_off(self) -> None:
        lines = _lines(
            f'<div style="overflow-wrap: break-word">'
            f'<p style="overflow-wrap: normal">{LONG}</p></div>'
        )
        self.assertTrue(any(extra < 0 for extra, _ in lines))

    def test_break_all_breaks_anywhere(self) -> None:
        lines = _lines(f'<p style="word-break: break-all">some words {LONG}</p>')
        self.assertTrue(all(extra >= -0.01 for extra, _ in lines), lines)
        # The long word starts on the first line rather than on a new one.
        self.assertIn("x", lines[0][1])
