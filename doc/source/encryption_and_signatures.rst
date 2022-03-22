Encryption and signing
=========================

Simple encryption
--------------------

If the argument is a string object, it is used as the User password to the PDF.
The argument can also be an instance of the class
`reportlab.lib.pdfencrypt.StandardEncryption`, which allows more finegrained control over
encryption settings

.. code:: python

    pisaStatus = pisa.CreatePDF(
            sourceHtml,
            encrypt="MyPassword",
            dest=resultFile)

Complex encryption
--------------------

The `StandardEncryption` constructor takes the following arguments:

.. code:: python

    def __init__(self, userPassword,
        ownerPassword=None,
        canPrint=1,
        canModify=1,
        canCopy=1,
        canAnnotate=1,
        strength=40):

The userPassword and ownerPassword parameters set the relevant password on the encrypted PDF.
The boolean flags `canPrint, canModify, canCopy, canAnnotate` determine wether a user can
perform the corresponding actions on the PDF when only a user password has been supplied.
If the user supplies the owner password while opening the PDF, all actions can be performed regardless of the
flags

.. code:: python

    from reportlab.lib import pdfencrypt
    enc=pdfencrypt.StandardEncryption("rptlab",canPrint=0)
    pisaStatus = pisa.CreatePDF(
            sourceHtml,
            encrypt=enc,
            dest=resultFile)

Signing pdf
=================

`CreatePDF` now has a `signature` parameter that allow to pass signature configuration


Simple Signing
--------------------

Signature use `Pyhanko <https://pyhanko.readthedocs.io/en/latest/>`__ internally, so `signature` parameter
allow many of the available configurations on that documentation.

The control parameters are required:

- **engine**: Possible options `pkcs12`, `pkcs11`, `simple`, define what engine load for manage certificates.
- **type**: Possible options `lta` and `simple`, define the mode for signing
- **passphrase**: Password to decrypt private key  (not required on pkcs11).

.. note::
    ``passphrase`` is always required, because ``None`` value prevents signing and empty string failed


.. code:: python

    signature={
        'engine': 'simple',
        'type': 'simple',
        'passphrase': 'mypassword',
        'key': 'enckey.pem',
        'cert': 'cert.pem',
        'ca_chain': 'chain.pem'
    }
    pisaStatus = pisa.CreatePDF(
            sourceHtml,
            signature=signature,
            dest=resultFile)

**ca_chain**: Could be a list or Path, define the chain of trust

PKCS12 Signing
--------------------

**pfx_file**: String or Path to pkcs12 file.

.. code:: python

    signature={
        'engine': 'pkcs12',
        'type': 'simple',
        'pfx_file': 'yourpkcs12file.p12',
        'passphrase': 'yourpassword'
    }


PKCS11 Signing
--------------------

.. note::
    You need to install `pyHanko[pkcs11]`

Must of the above settings are form

- `pades signatures <https://pyhanko.readthedocs.io/en/latest/lib-guide/signing.html#creating-pades-signatures>`__
- `PKCS11Signer <https://github.com/MatthiasValvekens/pyHanko/blob/042d6c70e74df34faeaa3eebc5843b5fc4856224/pyhanko/sign/pkcs11.py#L139>`__
- `ValidationContext <https://github.com/MatthiasValvekens/certvalidator/blob/0c67ec0eda36908dfcf35c4be58ffd9961253718/pyhanko_certvalidator/context.py#L53>`__
- `PdfSignatureMetadata <https://pyhanko.readthedocs.io/en/latest/api-docs/pyhanko.sign.signers.pdf_signer.html?highlight=PdfSignatureMetadata#pyhanko.sign.signers.pdf_signer.PdfSignatureMetadata>`__

You configure `PdfSignatureMetadata` using `meta` keyword, and `ValidationContext` using `validation_context`.  In my test
use of `ca_chain` append root certificates to signature, and `other_certs` allow to append chain certificates that are ignored
from `ca_chain` when build pdf signature.


.. code:: python

    signature={
        'engine': 'pkcs11',
        'type': 'lta',
        'lib_location': "/usr/lib/x64-athena/libASEP11.so",
        'tsa': "http://tsa.example.com/tsa/",
        'slot_no': 0,
        #'token_label': 'ChipDoc',
        'user_pin': '000000',
        'cert_label':  'cetificate label on smartcard',
        'key_label': 'key label label on smartcard',
        'meta': {
            'use_pades_lta': True,
            'signer_key_usage': {'digital_signature', 'non_repudiation'},
        },
        'ca_chain': ["/path/to/ca.pem" ],
        'validation_context': {'revocation_mode': "hard-fail",
                               'trust_roots':
                                   ['/path/to/ca/in/certitificate.pem' ],
                               'other_certs':['/path/to/external_chains.pem' ],
                               'retroactive_revinfo': True,
                               'crls': ['http://your.crl', '/path/to/file.crl']}
    }