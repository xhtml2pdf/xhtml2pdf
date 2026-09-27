import logging
from pathlib import Path

from asn1crypto import crl, ocsp, pem, x509
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers, timestamps
from pyhanko.sign.fields import SigSeedSubFilter
from pyhanko_certvalidator import ValidationContext

try:
    from pyhanko.sign.pkcs11 import PKCS11Signer, open_pkcs11_session
except ImportError:
    open_pkcs11_session = PKCS11Signer = None

from xhtml2pdf.config.resources import PERMISSIVE_POLICY
from xhtml2pdf.files import getFile

log = logging.getLogger(__name__)


class PDFSignature:
    @staticmethod
    def get_passphrase(config):
        if "passphrase" in config:
            passphrase = config["passphrase"]
            if isinstance(passphrase, str):
                passphrase = passphrase.encode()
            return passphrase
        return None

    @staticmethod
    def read_input(config, source, what) -> bytes:
        """
        Read a signing input: a certificate chain, a CRL, an OCSP response.

        These are named in the signature dict, which is the caller's, not the
        document's, so they are read under the caller's policy --
        ``config["policy"]``, or no confinement -- rather than the document's.
        Under the document's, a chain outside the document's directory was
        refused, logged as a warning, and surfaced later as a TypeError from
        asn1crypto that named neither the input nor the reason.
        """
        policy = (config or {}).get("policy") or PERMISSIVE_POLICY
        data = getFile(source, policy=policy).getData()
        if not data:
            msg = f"signature: cannot read {what} from {str(source)[:200]!r}"
            raise ValueError(msg)
        return data

    @staticmethod
    def get_chains(config, key, source=None):
        """
        The certificates listed under ``key`` of ``source``, loaded.

        ``source`` is the signature dict itself for ``ca_chain`` and its
        ``validation_context`` for the lists that live there; ``config`` is
        always the signature dict, for the policy to read files under.
        """
        if source is None:
            source = config
        chains = []
        if key in source:
            chain = source[key]
            if not isinstance(chain, list):
                chain = [chain]
            for c in chain:
                if isinstance(c, Path | str):
                    data = PDFSignature.read_input(config, c, key)
                    _, _, digicert_ca_bytes = pem.unarmor(data)
                    chains.append(x509.Certificate.load(digicert_ca_bytes))
                else:
                    chains.append(c)
        if not chains:
            return None
        return chains

    @staticmethod
    def test_simple_signer(config):
        passphrase = PDFSignature.get_passphrase(config)
        if "key" in config and "cert" in config and passphrase:
            chain = PDFSignature.get_chains(config, "ca_chain")
            return signers.SimpleSigner.load(
                config["key"],
                config["cert"],
                ca_chain_files=chain,
                key_passphrase=passphrase,
            )
        return None

    @staticmethod
    def test_pkcs12_signer(config):
        passphrase = PDFSignature.get_passphrase(config)
        if "pfx_file" in config and passphrase:
            return signers.SimpleSigner.load_pkcs12(
                pfx_file=config["pfx_file"], passphrase=passphrase
            )
        return None

    @staticmethod
    def test_pkcs11_signer(config):
        session = PDFSignature.get_session(config)
        keys = {
            "pkcs11_session": session,
            "cert_label": None,
            "signing_cert": None,
            "ca_chain": None,
            "key_label": None,
            "prefer_pss": False,
            "embed_roots": True,
            "other_certs_to_pull": (),
            "bulk_fetch": True,
            "key_id": None,
            "cert_id": None,
            "use_raw_mechanism": False,
        }

        for key in keys:
            if key in config:
                if key == "ca_chain":
                    chain = PDFSignature.get_chains(config, "ca_chain")
                    keys[key] = chain
                else:
                    keys[key] = config[key]

        return PKCS11Signer(**keys)

    @staticmethod
    def get_timestamps(config):
        if "tsa" in config:
            return timestamps.HTTPTimeStamper(url=config["tsa"])
        return None

    @staticmethod
    def get_signers(config):
        if "engine" not in config:
            return None

        signer = None
        engine = config["engine"]
        if engine == "pkcs12":
            signer = PDFSignature.test_pkcs12_signer(config)
        elif engine == "pkcs11":
            if PKCS11Signer is None:
                msg = (
                    "pyhanko.sign.pkcs11 requires pyHanko to be installed with the"
                    " [pkcs11] option. You can install missing dependencies by running"
                    " \"pip install 'pyHanko[pkcs11]'\"."
                )
                raise ImportError(msg)

            signer = PDFSignature.test_pkcs11_signer(config)
        elif engine == "simple":
            signer = PDFSignature.test_simple_signer(config)
        return signer

    @staticmethod
    def sign(inputfile, output, config):
        if config["type"] == "lta":
            return PDFSignature.lta_sign(inputfile, output, config)
        return PDFSignature.simple_sign(inputfile, output, config)

    @staticmethod
    def parse_crls(crls, config=None):
        list_crls = []
        for x in crls:
            if isinstance(x, Path | str):
                data = PDFSignature.read_input(config, x, "crls")
                cert_list = crl.CertificateList.load(data)
                list_crls.append(cert_list)
            else:
                list_crls.append(x)
        return list_crls

    @staticmethod
    def parse_oscp(oscps, config=None):
        list_oscp = []
        for x in oscps:
            data = ocsp.OCSPResponse.load(PDFSignature.read_input(config, x, "ocsps"))
            list_oscp.append(data)
        return list_oscp

    @staticmethod
    def get_validation_context(config):
        context = {"allow_fetching": True}
        if "validation_context" in config:
            if "crls" in config["validation_context"]:
                config["validation_context"]["crls"] = PDFSignature.parse_crls(
                    config["validation_context"]["crls"], config
                )
            if "ocsps" in config["validation_context"]:
                config["validation_context"]["ocsps"] = PDFSignature.parse_oscp(
                    config["validation_context"]["ocsps"], config
                )

            if "trust_roots" in config["validation_context"]:
                config["validation_context"]["trust_roots"] = PDFSignature.get_chains(
                    config, "trust_roots", config["validation_context"]
                )

            if "extra_trust_roots" in config["validation_context"]:
                config["validation_context"]["extra_trust_roots"] = (
                    PDFSignature.get_chains(
                        config, "extra_trust_roots", config["validation_context"]
                    )
                )

            if "other_certs" in config["validation_context"]:
                config["validation_context"]["other_certs"] = PDFSignature.get_chains(
                    config, "other_certs", config["validation_context"]
                )

            context.update(config["validation_context"])
        return ValidationContext(**context)

    @staticmethod
    def get_signature_meta(config):
        meta = {
            "field_name": "Signature1",
            "md_algorithm": "sha256",
            "location": None,
            "reason": None,
            "name": None,
            "certify": False,
            "embed_validation_info": True,
            "use_pades_lta": True,
            "subfilter": SigSeedSubFilter.PADES,
            "timestamp_field_name": None,
            "validation_context": PDFSignature.get_validation_context(config),
        }
        if "meta" in config:
            meta.update(config["meta"])
        return meta

    @staticmethod
    def simple_sign(inputfile, output, config):
        signer = PDFSignature.get_signers(config)
        if signer:
            w = IncrementalPdfFileWriter(inputfile)
            timestamper = PDFSignature.get_timestamps(config)
            signers.sign_pdf(
                w,
                signers.PdfSignatureMetadata(field_name="Signature1"),
                signer=signer,
                output=output,
                timestamper=timestamper,
            )
            return True
        return None

    @staticmethod
    def lta_sign(inputfile, output, config):
        signer = PDFSignature.get_signers(config)
        timestamper = PDFSignature.get_timestamps(config)
        w = IncrementalPdfFileWriter(inputfile)
        meta = PDFSignature.get_signature_meta(config)

        signature_meta = signers.PdfSignatureMetadata(**meta)
        if signer and timestamper:
            signers.sign_pdf(
                w,
                signature_meta=signature_meta,
                signer=signer,
                timestamper=timestamper,
                output=output,
            )
            return True
        return None

    @staticmethod
    def get_session(config):
        lib_location = config.get("lib_location", None)
        slot_no = config.get("slot_no", None)
        token_label = config.get("token_label", None)
        user_pin = config.get("user_pin", None)

        if user_pin is not None and lib_location is not None:
            if slot_no is not None or token_label is not None:
                return open_pkcs11_session(
                    lib_location,
                    slot_no=slot_no,
                    token_label=token_label,
                    user_pin=user_pin,
                )
            return None
        return None
