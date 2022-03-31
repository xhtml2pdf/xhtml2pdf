Https option
==============

Using in python
--------------------------------

Basically you need to set httpConfig before call pisa.CreatePDF

.. code:: python

    from xhtml2pdf.config.httpconfig import httpConfig
    httpConfig.save_keys('nosslcheck', True)
    pisaStatus = pisa.CreatePDF(
            sourceHtml,               
            dest=resultFile) 

Other way is setting as a dict

.. code:: python

    import ssl
    from xhtml2pdf.config.httpconfig import httpConfig
    httpConfig['context']=ssl._create_unverified_context()

In this way you can insert arbitrary httplib.HTTPSConnection parameters, for more information see: 

- python2 : https://docs.python.org/2/library/httplib.html#httplib.HTTPSConnection
- python3 : https://docs.python.org/3.4/library/http.client.html#http.client.HTTPSConnection


Using in shell
--------------------------------

So you can call to xhtml2pdf passing httplib parameters with something like:

.. code:: bash

    xhtml2pdf --http_nosslcheck https://domain yourfile.pdf

the ``--http_nosslcheck`` is a special argument that help to disable the ssl certificate check.

See http.client.HTTPSConnection documentation for this parameters

Those are the available options:

- http_nosslcheck
- http_key_file
- http_cert_file
- http_source_address
- http_timeout



available settings 

- http_key_file
- http_cert_file
- http_source_address
- http_timeout
