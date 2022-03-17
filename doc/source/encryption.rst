How To Use Encryption
======================

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