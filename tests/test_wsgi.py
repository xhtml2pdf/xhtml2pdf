from __future__ import annotations

from unittest import TestCase

from xhtml2pdf.wsgi import Filter, HTMLFilter, PisaMiddleware

HTML = "<html><body><p>hello wsgi</p></body></html>"


def make_app(body: str, status: str = "200 OK", content_type: str = "text/html"):
    def app(environ, start_response):  # noqa: ARG001
        start_response(status, [("content-type", content_type)])
        return [body]

    return app


def run(middleware, environ) -> tuple[str, list, list]:
    captured: list = []

    def start_response(status, headers, exc_info=None):  # noqa: ARG001
        captured[:] = [status, headers]
        return lambda _data: None

    body = middleware(environ, start_response)
    return captured[0], captured[1], body


class FilterTest(TestCase):
    def test_should_filter_is_abstract(self) -> None:
        """
        The base implementation used to be ``print(headers)``, which wrote to
        stdout and returned None, silently disabling filtering.
        """
        with self.assertRaises(NotImplementedError):
            Filter.should_filter("200 OK", [])

    def test_filter_is_abstract(self) -> None:
        with self.assertRaises(NotImplementedError):
            Filter.filter(None, "", "", {}, "200 OK", [], b"")  # type: ignore[arg-type]


class HTMLFilterTest(TestCase):
    def test_accepts_html_200(self) -> None:
        self.assertTrue(
            HTMLFilter.should_filter("200 OK", [("Content-Type", "text/html")])
        )

    def test_rejects_non_200(self) -> None:
        self.assertFalse(
            HTMLFilter.should_filter("404 Not Found", [("Content-Type", "text/html")])
        )

    def test_rejects_other_content_types(self) -> None:
        self.assertFalse(
            HTMLFilter.should_filter("200 OK", [("Content-Type", "application/json")])
        )

    def test_rejects_missing_content_type(self) -> None:
        self.assertFalse(HTMLFilter.should_filter("200 OK", []))


class PisaMiddlewareTest(TestCase):
    def test_passes_html_through_untouched(self) -> None:
        middleware = PisaMiddleware(make_app(HTML))
        status, headers, body = run(middleware, {})
        self.assertEqual("200 OK", status)
        self.assertEqual(HTML.encode(), b"".join(body))

    def test_converts_to_pdf_when_requested(self) -> None:
        middleware = PisaMiddleware(make_app(HTML))
        status, headers, body = run(middleware, {"pisa.topdf": "out.pdf"})

        self.assertEqual("200 OK", status)
        header_map = {name.lower(): value for name, value in headers}
        self.assertEqual("application/pdf", header_map["content-type"])
        self.assertEqual(
            "attachment; filename=out.pdf", header_map["content-disposition"]
        )

        payload = b"".join(body)
        self.assertTrue(payload.startswith(b"%PDF"), payload[:20])

    def test_non_html_response_is_not_intercepted(self) -> None:
        middleware = PisaMiddleware(make_app("{}", content_type="application/json"))
        status, headers, body = run(middleware, {"pisa.topdf": "out.pdf"})
        self.assertEqual("200 OK", status)
        self.assertEqual(
            "application/json",
            {name.lower(): value for name, value in headers}["content-type"],
        )
