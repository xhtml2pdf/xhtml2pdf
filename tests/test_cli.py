"""
Coverage for the ``pisa`` / ``xhtml2pdf`` console entry point.

``xhtml2pdf.pisa.command`` is what both console scripts declared in
pyproject.toml resolve to, and no test exercised it: argument parsing, file
resolution and exit codes were entirely uncovered.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import TestCase, mock

from pypdf import PdfReader

from xhtml2pdf import __version__, pisa

SAMPLES = Path(__file__).parent / "samples"
HTML = "<html><body><h1>cli</h1><p>hello</p></body></html>"


def run_cli(*argv: str) -> tuple[int | str, str]:
    """Run ``command()`` with ``argv``; returns (exit code, stdout)."""
    out = io.StringIO()
    code: int | str = 0
    with mock.patch("sys.argv", ["xhtml2pdf", *argv]), redirect_stdout(out):
        try:
            pisa.command()
        except SystemExit as exc:
            code = 0 if exc.code is None else exc.code
    return code, out.getvalue()


class CommandTest(TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name) / "input.html"
        self.src.write_text(HTML, encoding="utf-8")

    def test_version(self) -> None:
        code, out = run_cli("--version")
        self.assertEqual(0, code)
        self.assertEqual(__version__, out.strip())

    def test_help_exits_cleanly(self) -> None:
        code, out = run_cli("--help")
        self.assertEqual(0, code)
        self.assertIn("USAGE: pisa [options] SRC [DEST]", out)

    def test_system_reports_the_reportlab_version(self) -> None:
        import reportlab

        code, out = run_cli("--system")
        self.assertEqual(0, code)
        self.assertIn(reportlab.Version, out)

    def test_no_arguments_is_a_usage_error(self) -> None:
        code, _ = run_cli()
        self.assertEqual(2, code)

    def test_too_many_arguments_is_a_usage_error(self) -> None:
        code, _ = run_cli("a.html", "b.pdf", "c.pdf")
        self.assertEqual(2, code)

    def test_unknown_option_is_a_usage_error(self) -> None:
        code, _ = run_cli("--definitely-not-an-option")
        self.assertEqual(2, code)

    def test_converts_a_file(self) -> None:
        dest = Path(self.tmp.name) / "out.pdf"
        code, _ = run_cli("-q", str(self.src), str(dest))
        self.assertEqual(0, code)
        self.assertTrue(dest.is_file())
        self.assertEqual("cli\nhello", PdfReader(dest).pages[0].extract_text().strip())

    def test_destination_defaults_to_the_source_name(self) -> None:
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, cwd)

        code, _ = run_cli("-q", "input.html")
        self.assertEqual(0, code)
        self.assertTrue((Path(self.tmp.name) / "input.pdf").is_file())

    def test_missing_source_file_fails(self) -> None:
        dest = Path(self.tmp.name) / "out.pdf"
        with self.assertRaises(OSError):
            run_cli("-q", str(Path(self.tmp.name) / "nope.html"), str(dest))

    def test_css_option_is_applied(self) -> None:
        css = Path(self.tmp.name) / "extra.css"
        css.write_text("h1 { color: #ff0000; }", encoding="utf-8")
        dest = Path(self.tmp.name) / "out.pdf"

        code, _ = run_cli("-q", "--css", str(css), str(self.src), str(dest))
        self.assertEqual(0, code)
        self.assertTrue(dest.is_file())

    def test_relative_images_resolve_against_the_source(self) -> None:
        src = Path(self.tmp.name) / "with-image.html"
        src.write_text(
            f'<html><body><img src="{SAMPLES / "img" / "denker.png"}"></body></html>',
            encoding="utf-8",
        )
        dest = Path(self.tmp.name) / "img.pdf"

        code, _ = run_cli("-q", str(src), str(dest))
        self.assertEqual(0, code)

        xobjects = PdfReader(dest).pages[0]["/Resources"]["/XObject"]
        self.assertEqual(
            1, sum(1 for name in xobjects if xobjects[name]["/Subtype"] == "/Image")
        )

    def test_resource_root_confines_local_reads(self) -> None:
        """
        The command line does not confine local reads by default -- the
        document is the operator's own -- but --resource-root asks for it, for
        converting HTML that came from somewhere else.
        """
        src = Path(self.tmp.name) / "with-image.html"
        src.write_text(
            f'<html><body><img src="{SAMPLES / "img" / "denker.png"}"></body></html>',
            encoding="utf-8",
        )
        dest = Path(self.tmp.name) / "img.pdf"

        code, _ = run_cli("-q", "--resource-root", self.tmp.name, str(src), str(dest))

        self.assertEqual(0, code)
        self.assertNotIn("/XObject", PdfReader(dest).pages[0]["/Resources"])

    def test_no_remote_refuses_a_remote_image(self) -> None:
        src = Path(self.tmp.name) / "remote.html"
        src.write_text(
            '<html><body><img src="https://example.com/x.png"></body></html>',
            encoding="utf-8",
        )
        dest = Path(self.tmp.name) / "remote.pdf"

        with mock.patch("xhtml2pdf.files.NetworkFileUri._request") as request:
            code, _ = run_cli("-q", "--no-remote", str(src), str(dest))

        self.assertEqual(0, code)
        self.assertEqual([], request.call_args_list)


class RunAsAModuleTest(TestCase):
    """
    ``python -m xhtml2pdf`` is the form people reach for first, and it was the
    one that did not work: the package had no __main__.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "source.html"
        self.src.write_text(HTML, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_module_converts_a_file(self) -> None:
        dest = Path(self.tmp.name) / "out.pdf"

        result = subprocess.run(
            [sys.executable, "-m", "xhtml2pdf", "-q", str(self.src), str(dest)],
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertTrue(dest.is_file())
        self.assertEqual(1, len(PdfReader(dest).pages))


class StartViewerTest(TestCase):
    """
    ``startViewer`` used to build a shell command by string interpolation
    (``os.system('open "%s"' % filename)``), so a destination carrying shell
    metacharacters ran as a command. The name must reach the opener as one
    argument, with no shell in between.
    """

    hostile = '/tmp/report"; touch /tmp/pwned; #.pdf'

    def test_no_shell_is_used(self) -> None:
        with (
            mock.patch("os.system") as system,
            mock.patch("subprocess.run") as run,
            mock.patch.object(sys, "platform", "linux"),
        ):
            pisa.startViewer(self.hostile)

        system.assert_not_called()
        run.assert_called_once()
        self.assertEqual(["xdg-open", self.hostile], run.call_args.args[0])

    def test_macos_uses_open(self) -> None:
        with (
            mock.patch("subprocess.run") as run,
            mock.patch.object(sys, "platform", "darwin"),
        ):
            pisa.startViewer("/tmp/report.pdf")

        self.assertEqual(["open", "/tmp/report.pdf"], run.call_args.args[0])

    def test_windows_uses_startfile(self) -> None:
        with (
            mock.patch.object(sys, "platform", "win32"),
            mock.patch.object(os, "startfile", create=True) as startfile,
            mock.patch("subprocess.run") as run,
        ):
            pisa.startViewer("C:\\report.pdf")

        self.assertEqual([mock.call("C:\\report.pdf")], startfile.call_args_list)
        self.assertEqual([], run.call_args_list)

    def test_a_missing_opener_is_only_logged(self) -> None:
        with (
            mock.patch("subprocess.run", side_effect=OSError("no xdg-open")),
            mock.patch.object(sys, "platform", "linux"),
            self.assertLogs("xhtml2pdf.pisa", level="WARNING") as logs,
        ):
            pisa.startViewer("/tmp/report.pdf")

        self.assertIn("Could not start a viewer", logs.output[0])

    def test_no_file_name_does_nothing(self) -> None:
        with mock.patch("subprocess.run") as run:
            pisa.startViewer("")

        self.assertEqual([], run.call_args_list)
