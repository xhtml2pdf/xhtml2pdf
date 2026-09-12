"""
Rendering a document for measurement, and timing the phases it passes through.

The timers are installed from out here rather than from inside the library: a
document renders exactly the same whether or not this module was imported.
Each phase is wrapped at its outermost callable, so the numbers nest the way
the pipeline does and `reportlab` can be read off as what is left of the total.
"""

from __future__ import annotations

import contextlib
import io
import logging
import time
from collections import defaultdict
from contextlib import contextmanager

import reportlab.rl_config

from xhtml2pdf import document as _document
from xhtml2pdf import parser as _parser
from xhtml2pdf import pisa
from xhtml2pdf.context import pisaContext

#: Repeatable PDFs: without this reportlab stamps a creation date, and two
#: renders of the same document differ in bytes. golden.py depends on it.
reportlab.rl_config.invariant = 1

#: Documents in the corpus report missing images and unsupported constructs.
#: That is the fixtures being fixtures, and it is not what is being measured.
logging.getLogger("xhtml2pdf").setLevel(logging.CRITICAL)

#: Seconds spent in each phase during the most recent render.
timings: dict[str, float] = defaultdict(float)

#: What `total` is made of. `reportlab` is derived rather than measured: the
#: build step reaches into reportlab through so many entry points that timing
#: it directly would mean instrumenting reportlab itself.
PHASES = ("html5lib", "parseCSS", "CSSCollect", "story", "reportlab")


def _timed(name, func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            timings[name] += time.perf_counter() - start

    wrapper.__name__ = getattr(func, "__name__", name)
    return wrapper


@contextmanager
def phase_timers():
    """Install the phase timers for the duration of the block."""
    import html5lib

    originals = [
        (html5lib.HTMLParser, "parse", "html5lib"),
        (pisaContext, "parseCSS", "parseCSS"),
        (_parser, "CSSCollect", "CSSCollect"),
        (_document, "pisaStory", "story"),
    ]
    saved = [(obj, attr, getattr(obj, attr)) for obj, attr, _ in originals]
    try:
        for (obj, attr, name), (_, _, func) in zip(originals, saved, strict=True):
            setattr(obj, attr, _timed(name, func))
        yield
    finally:
        for obj, attr, func in saved:
            setattr(obj, attr, func)


def render(doc, dest) -> None:
    """Render one Document, raising if it did not come out."""
    # Fixtures log about images they cannot reach; pisa also writes some of
    # that straight to stderr, which would bury the table being printed.
    with contextlib.redirect_stderr(io.StringIO()):
        result = pisa.pisaDocument(
            io.BytesIO(doc.source), dest, path=doc.path, resource_policy=doc.policy()
        )
    if result.err:
        msg = f"{doc.name} failed to render: {result.err} error(s)"
        raise RuntimeError(msg)


def render_bytes(doc) -> bytes:
    dest = io.BytesIO()
    render(doc, dest)
    return dest.getvalue()


def timed_render(doc) -> tuple[float, dict[str, float]]:
    """
    Render once and return (total seconds, seconds per phase).

    The caller is responsible for having warmed up first: the first render of
    a process registers fonts and fills the module-level caches that
    util.reset_caches clears between documents, and charging that to whichever
    document happened to go first would make the corpus order matter.
    """
    timings.clear()
    with phase_timers():
        start = time.perf_counter()
        render(doc, _Sink())
        total = time.perf_counter() - start
    phases = dict(timings)
    phases["reportlab"] = total - phases.get("story", 0.0)
    return total, phases


#: How many times each unit of work ran during the most recent counted render.
#: Exactly reproducible, unlike a timing, so an optimisation meant to do less
#: work shows up here first and in the clock second.
counters: dict[str, int] = defaultdict(int)

COUNTERS = ("CSSCollect", "CSSCollect (miss)", "ruleset lookups", "selector matches")


def _counted(name, func):
    def wrapper(*args, **kwargs):
        counters[name] += 1
        return func(*args, **kwargs)

    wrapper.__name__ = getattr(func, "__name__", name)
    return wrapper


@contextmanager
def work_counters():
    """Count the units of work a render does, for the duration of the block."""
    from xhtml2pdf.w3c import css

    originals = [
        (_parser, "CSSCollect", "CSSCollect"),
        (css.CSSRuleset, "findCSSRulesFor", "ruleset lookups"),
        (css.CSSSelectorBase, "matches", "selector matches"),
    ]
    saved = [(obj, attr, getattr(obj, attr)) for obj, attr, _ in originals]
    try:
        for (obj, attr, name), (_, _, func) in zip(originals, saved, strict=True):
            setattr(obj, attr, _counted(name, func))
        yield
    finally:
        for obj, attr, func in saved:
            setattr(obj, attr, func)


def counted_render(doc) -> dict[str, int]:
    """Render once, counting work rather than timing it."""
    counters.clear()
    cache_misses = []
    real_collect = _parser.CSSCollect

    def collect(node, context):
        before = len(context.cssAttrCache)
        result = real_collect(node, context)
        if len(context.cssAttrCache) != before:
            cache_misses.append(1)
        return result

    _parser.CSSCollect = collect
    try:
        with work_counters():
            render(doc, _Sink())
    finally:
        _parser.CSSCollect = real_collect
    result = dict(counters)
    result["CSSCollect (miss)"] = len(cache_misses)
    return result


class _Sink:
    """Somewhere for the PDF to go when only the time spent matters."""

    @staticmethod
    def write(data):
        return len(data)

    def flush(self):
        pass
