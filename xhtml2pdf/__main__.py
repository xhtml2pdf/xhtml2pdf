"""
Entry point for ``python -m xhtml2pdf``.

The console scripts installed by this package -- ``pisa`` and ``xhtml2pdf`` --
both resolve to the same function, but running the module was the one form
that did not work.
"""

from __future__ import annotations

from xhtml2pdf.pisa import command

if __name__ == "__main__":
    command()
