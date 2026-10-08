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

COUNTERS = (
    "CSSCollect",
    "CSSCollect (miss)",
    "ruleset lookups",
    "selector matches",
    "stringWidth",
)

#: Every module that holds its own reference to pdfmetrics.stringWidth, so that
#: counting it means replacing each of those names, not just the original.
_STRING_WIDTH_HOLDERS = (
    "reportlab.pdfbase.pdfmetrics",
    "xhtml2pdf.reportlab_paragraph",
    "xhtml2pdf.xhtml2pdf_reportlab",
    "xhtml2pdf.paragraph",
    "xhtml2pdf.builders.flex",
)


def _counted(name, func):
    def wrapper(*args, **kwargs):
        counters[name] += 1
        return func(*args, **kwargs)

    wrapper.__name__ = getattr(func, "__name__", name)
    return wrapper


@contextmanager
def work_counters():
    """Count the units of work a render does, for the duration of the block."""
    import importlib

    from xhtml2pdf.w3c import css

    originals = [
        (_parser, "CSSCollect", "CSSCollect"),
        (css.CSSRuleset, "findCSSRulesFor", "ruleset lookups"),
        (css.CSSSelectorBase, "matches", "selector matches"),
    ]
    originals += [
        (importlib.import_module(name), "stringWidth", "stringWidth")
        for name in _STRING_WIDTH_HOLDERS
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


def _rss_mb() -> float:
    """The resident set size of this process now, in MB (Linux only)."""
    try:
        with open("/proc/self/status", encoding="ascii") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return float("nan")


def memory_render(doc) -> dict[str, float]:
    """
    Render once under tracemalloc and report what the render held at its peak.

    `peak_mb` is the most Python-allocated memory alive at any moment of the
    render, net of what was alive before it started -- the number that decides
    how many renders fit on a server. `retained_mb` is what was still alive
    after the render and a collection: anything other than about zero means a
    render leaves something behind. `rss_mb` is the process's resident size
    after the render, which also counts what C extensions allocate and what
    the allocator has not handed back. The caller warms up first.
    """
    import gc
    import tracemalloc

    gc.collect()
    tracemalloc.start()
    base, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    dest = io.BytesIO()
    render(doc, dest)
    _, peak = tracemalloc.get_traced_memory()
    size = len(dest.getvalue())
    del dest
    gc.collect()
    after, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "peak_mb": (peak - base) / 1e6,
        "retained_mb": (after - base) / 1e6,
        "rss_mb": _rss_mb(),
        "pdf_kb": size / 1e3,
    }


def leak_check(doc, renders: int) -> dict[str, float]:
    """
    Render the same document `renders` times and report what grew.

    A server converts documents for as long as it runs, so whatever a render
    leaves behind -- an object in a module-level cache, a font in reportlab's
    registry -- adds up. Reports the growth between the first render and the
    last, after a collection each time, so a steady state reads as zero.
    """
    import gc

    from reportlab.pdfbase import pdfmetrics

    from xhtml2pdf.util import Memoized

    def state():
        gc.collect()
        return {
            "objects": len(gc.get_objects()),
            "rss_mb": _rss_mb(),
            "memoized": sum(len(m.cache) for m in Memoized._instances),
            "fonts": len(pdfmetrics.getRegisteredFontNames()),
        }

    render(doc, _Sink())
    first = state()
    for _ in range(renders - 1):
        render(doc, _Sink())
    last = state()
    return {key: last[key] - first[key] for key in first}


class _Sink:
    """Somewhere for the PDF to go when only the time spent matters."""

    @staticmethod
    def write(data):
        return len(data)

    def flush(self):
        pass
