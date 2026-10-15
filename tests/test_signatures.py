"""
Signing a document end to end, with each engine and type the docs describe.

Every certificate is made here, and the timestamp authority is pyHanko's
DummyTimeStamper, so nothing is fetched. Each signed PDF is read back and
validated by pyHanko against the throwaway CA.
"""

from __future__ import annotations

import datetime
import io
import tempfile
from pathlib import Path
from typing import ClassVar
from unittest import TestCase, mock

from asn1crypto import keys as asn1_keys
from asn1crypto import x509 as asn1_x509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import timestamps
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from xhtml2pdf.builders import signs
from xhtml2pdf.builders.signs import PDFSignature
from xhtml2pdf.document import pisaDocument

PASSPHRASE = "secret"


def _key_usage(*, ca: bool) -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=not ca,
        content_commitment=not ca,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=ca,
        crl_sign=ca,
        encipher_only=False,
        decipher_only=False,
    )


def _certificate(name, issuer=None, issuer_key=None, *, ca=False, eku=None):
    # RSA: DummyTimeStamper signs with RSA only.
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer.subject if issuer else subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(hours=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        .add_extension(_key_usage(ca=ca), critical=True)
    )
    if eku:
        builder = builder.add_extension(x509.ExtendedKeyUsage(eku), critical=True)
    return key, builder.sign(issuer_key or key, hashes.SHA256())


def _asn1(cert: x509.Certificate) -> asn1_x509.Certificate:
    return asn1_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))


class SigningTest(TestCase):
    tmp: ClassVar[tempfile.TemporaryDirectory]
    files: ClassVar[Path]
    ca: ClassVar[asn1_x509.Certificate]
    timestamper: ClassVar[timestamps.DummyTimeStamper]

    @classmethod
    def setUpClass(cls) -> None:
        ca_key, ca = _certificate("test CA", ca=True)
        key, cert = _certificate("signer", ca, ca_key)
        tsa_key, tsa = _certificate(
            "test TSA", ca, ca_key, eku=[ExtendedKeyUsageOID.TIME_STAMPING]
        )
        cls.tmp = tempfile.TemporaryDirectory()
        files = Path(cls.tmp.name)
        pem = serialization.Encoding.PEM
        encrypted = serialization.BestAvailableEncryption(PASSPHRASE.encode())
        (files / "ca.pem").write_bytes(ca.public_bytes(pem))
        (files / "cert.pem").write_bytes(cert.public_bytes(pem))
        (files / "key.pem").write_bytes(
            key.private_bytes(pem, serialization.PrivateFormat.PKCS8, encrypted)
        )
        (files / "signer.p12").write_bytes(
            pkcs12.serialize_key_and_certificates(b"signer", key, cert, [ca], encrypted)
        )
        cls.files = files
        cls.ca = _asn1(ca)
        cls.timestamper = timestamps.DummyTimeStamper(
            tsa_cert=_asn1(tsa),
            tsa_key=asn1_keys.PrivateKeyInfo.load(
                tsa_key.private_bytes(
                    serialization.Encoding.DER,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            ),
            certs_to_embed=[cls.ca],
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def sign(self, signature: dict):
        """The signatures of a one-paragraph document signed with `signature`."""
        dest = io.BytesIO()
        with mock.patch.object(
            PDFSignature,
            "get_timestamps",
            return_value=self.timestamper if "tsa" in signature else None,
        ):
            result = pisaDocument(
                io.StringIO("<p>signed</p>"), dest, signature=signature
            )
        self.assertEqual(0, result.err)
        return PdfFileReader(io.BytesIO(dest.getvalue())).embedded_signatures

    def assert_valid(self, embedded) -> None:
        context = ValidationContext(trust_roots=[self.ca], allow_fetching=False)
        status = validate_pdf_signature(embedded, context)
        self.assertTrue(status.intact)
        self.assertTrue(status.valid)
        self.assertTrue(status.trusted)

    def test_simple_engine_with_a_ca_chain(self) -> None:
        """
        The first example in the docs. The parsed chain goes to pyHanko as
        certificates, not as the file names ca_chain_files expects.
        """
        signatures = self.sign(
            {
                "engine": "simple",
                "type": "simple",
                "passphrase": PASSPHRASE,
                "key": str(self.files / "key.pem"),
                "cert": str(self.files / "cert.pem"),
                "ca_chain": str(self.files / "ca.pem"),
            }
        )
        self.assertEqual(1, len(signatures))
        self.assert_valid(signatures[0])

    def test_pkcs12_engine(self) -> None:
        signatures = self.sign(
            {
                "engine": "pkcs12",
                "type": "simple",
                "passphrase": PASSPHRASE,
                "pfx_file": str(self.files / "signer.p12"),
            }
        )
        self.assertEqual(1, len(signatures))
        self.assert_valid(signatures[0])

    def test_lta_adds_a_document_timestamp(self) -> None:
        signatures = self.sign(
            {
                "engine": "pkcs12",
                "type": "lta",
                "passphrase": PASSPHRASE,
                "pfx_file": str(self.files / "signer.p12"),
                "tsa": "http://tsa.invalid",
                "validation_context": {
                    "trust_roots": [str(self.files / "ca.pem")],
                    "allow_fetching": False,
                },
            }
        )
        # The signature, then the document timestamp PAdES-LTA adds over it.
        self.assertEqual(2, len(signatures))
        self.assert_valid(signatures[0])


class PKCS11SessionTest(TestCase):
    """
    The session is opened by token label through token_criteria.

    open_pkcs11_session has no token_label argument since pyHanko 0.37.
    There is no token here, so this pins the call; it has been checked
    against SoftHSM.
    """

    CONFIG: ClassVar[dict] = {"lib_location": "/lib/p11.so", "user_pin": "1234"}

    def test_a_token_label_becomes_token_criteria(self) -> None:
        with mock.patch.object(signs, "open_pkcs11_session") as opened:
            PDFSignature.get_session({**self.CONFIG, "token_label": "token"})

        kwargs = opened.call_args.kwargs
        self.assertNotIn("token_label", kwargs)
        self.assertEqual("token", kwargs["token_criteria"].label)

    def test_a_slot_alone_has_no_criteria(self) -> None:
        with mock.patch.object(signs, "open_pkcs11_session") as opened:
            PDFSignature.get_session({**self.CONFIG, "slot_no": 0})

        self.assertIsNone(opened.call_args.kwargs["token_criteria"])
        self.assertEqual(0, opened.call_args.kwargs["slot_no"])
