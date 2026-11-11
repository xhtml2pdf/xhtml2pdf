from __future__ import annotations

import ssl
from unittest import TestCase

from xhtml2pdf.config.httpconfig import HttpConfig


class HttpConfigTest(TestCase):
    def test_default_timeout(self) -> None:
        self.assertEqual({"timeout": 5}, HttpConfig())

    def test_constructor_arguments_are_kept(self) -> None:
        config = HttpConfig(source_address=("127.0.0.1", 0))
        self.assertEqual(("127.0.0.1", 0), config["source_address"])

    def test_constructor_cannot_override_default_timeout(self) -> None:
        """
        __init__ sets the default timeout after dict.__init__, so a timeout
        passed to the constructor is overwritten. Options set later, as the
        CLI does through is_http_config, are kept.
        """
        self.assertEqual(5, HttpConfig(timeout=30)["timeout"])

    def test_http_options_are_stored_without_prefix(self) -> None:
        for option in ("--http_timeout", "-http_timeout", "http_timeout"):
            with self.subTest(option=option):
                config = HttpConfig()
                self.assertTrue(config.is_http_config(option, 10))
                self.assertEqual(10, config["timeout"])

    def test_http_options_with_other_keys(self) -> None:
        config = HttpConfig()
        self.assertTrue(config.is_http_config("--http_key_file", "client.key"))
        self.assertTrue(config.is_http_config("--http_cert_file", "client.crt"))
        self.assertEqual("client.key", config["key_file"])
        self.assertEqual("client.crt", config["cert_file"])

    def test_non_http_options_are_ignored(self) -> None:
        for option in ("--encoding", "-q", "debug"):
            with self.subTest(option=option):
                config = HttpConfig()
                self.assertFalse(config.is_http_config(option, "value"))
                self.assertEqual({"timeout": 5}, config)

    def test_nosslcheck_creates_unverified_context(self) -> None:
        config = HttpConfig()
        self.assertTrue(config.is_http_config("--http_nosslcheck", ""))

        self.assertNotIn("nosslcheck", config)
        context = config["context"]
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertEqual(ssl.CERT_NONE, context.verify_mode)
        self.assertFalse(context.check_hostname)

    def test_save_keys_stores_value(self) -> None:
        config = HttpConfig()
        config.save_keys("timeout", 1)
        self.assertEqual(1, config["timeout"])

    def test_repr_lists_every_item(self) -> None:
        config = HttpConfig()
        config["cert_file"] = "client.crt"
        self.assertEqual("'timeout' = 5, 'cert_file' = 'client.crt', ", repr(config))

    def test_repr_of_empty_config(self) -> None:
        config = HttpConfig()
        config.clear()
        self.assertEqual("", repr(config))
