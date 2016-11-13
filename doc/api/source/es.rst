.. _es-tool:

`es` - Danube Cloud command-line tool
*************************************

`es` is a Swiss Army Knife command-line interface (CLI) for the Danube Cloud API.


Installation
============

Requirements
------------

 - **Python >= 2.6**
 - **Python requests** - http://python-requests.org/
 - Python tabulate (optional) - https://bitbucket.org/astanin/python-tabulate

Download
--------

 - `es </static/api/bin/es>`_ (python script)
 - `es bash completion </static/api/bin/es_bash_completion.sh>`_ (shell script, optional)

Configuration
-------------

Shell variables used by `es`:

============= ===============
**Variable**  **Description**
------------- ---------------
ES_API_KEY    Optional API key used to perform authenticated requests.
============= ===============

You can further customize the downloaded `es` python script by opening it in a text editor and changing the following configuration variables:

============= ===============
**Variable**  **Description**
------------- ---------------
API_URL       URL of your *Danube Cloud* installation (`SITE_URL`) with `/api` path appended to it.
API_KEY       Optional API key used to perform authenticated requests (may be read from ``ES_API_KEY`` environment variable).
TOKEN_STORE   `es` session file location.
SSL_VERIFY    Whether to verify server SSL certificate.
TIMEOUT       HTTP connect and read timeout in seconds.
============= ===============

.. note:: Always use **HTTPS** for API_URL to achieve optimal transport security.


Usage
=====

.. sourcecode:: text

    es action [/resource] [parameters] [output format]

      action:        {login|logout|get|create|set|delete|options}
      resource:      /some/resource/in/api
      parameters:    -foo baz -bar qux ...
      output format: --json (default)
                     --csv
                     --tabulate
                     --tabulate-<tablefmt>

.. note:: The tabulate output format will be only available if python-tabulate package is installed.

Input
=====

.. _es-actions:

Actions
-------

Action is a command translated into a HTTP method according to this table:

============= =======================================================
**es action** **HTTP method**
------------- -------------------------------------------------------
get           GET
create        POST
set           PUT
delete        DELETE
options       OPTIONS
login         :http:post:`POST /api/accounts/login </accounts/login>`
logout        :http:get:`GET /api/accounts/logout </accounts/logout>`
============= =======================================================

.. _es-resources:

Resources
---------

Every resource begins with a slash and is represented by a path which is used to create a URL. Most of the available resources are bound to a :ref:`virtual datacenter <dc>` and should be prefixed with a ``/dc/(dc)/`` path.

.. note:: Please check the `routing table <http-routingtable.html>`_ for all available resources.

.. _es-parameters:

Parameters
----------

Parameters begin with a single dash followed by the name of the parameter, then followed by a value.
Parameters are internally translated into :http:method:`POST`/:http:method:`PUT`/:http:method:`DELETE` JSON encoded data or :http:method:`GET` query strings and send to the server.

.. note:: A special parameter ``-api-key`` can be used to perform an authenticated request without the need to log in.


Output
======

`es` supports different output formatters. The default output formatter is `json`_ and it can be changed by using the ``--<output-formatter>`` command-line parameter. Some output formatters may require additional python dependencies.

json
----

The default output is a JSON object with following attributes:

* url - full URL built from the :ref:`resource <es-resources>` (and parameters if the :ref:`get action <es-actions>` is specified)
* status - response HTTP status code
* method - `es` action translated to HTTP method
* text - HTTP output in JSON format


    |es example|:

    .. sourcecode:: bash

        es login -username admin -password Passw0rd

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/accounts/login/", 
            "status": 200, 
            "method": "POST", 
            "text": {
                "detail": "Welcome to Danube Cloud API." 
            }
        }

csv
---

Uses the python built-in csv module to print the API results in CSV (Comma Separated Values) format using the semicolon (``;``) as a field delimiter.

    |es example|:

    .. sourcecode:: bash

        es get /image -full --csv

    .. sourcecode:: bash

        name;deploy;access;alias;version;ostype;owner;size;desc
        centos-6.4;True;1;centos-6.4;1.0.3;1;admin;10240;CentOS Linux 6.4 64-bit
        scientific-6.4;True;1;scientific-6.4;1.0.3;1;admin;10240;Scientific Linux 6.4 64-bit
        ubuntu-12.04;True;1;ubuntu-12.04;1.0.3;1;admin;10240;Ubuntu Linux 12.04.2 LTS 64-bit

tabulate
--------

The tabulate output formatter requires `python tabulate <https://bitbucket.org/astanin/python-tabulate>`_ to be installed. Following table formats are supported:

* plain
* simple (default)
* grid
* pipe
* orgtbl
* rst
* mediawiki
* latex
* latex_booktabs


    |es example|:

    .. sourcecode:: bash

        es get /image -full --tabulate-grid

    .. sourcecode:: bash

        +----------------+----------+----------+----------------+-----------+----------+---------+--------+---------------------------------+
        | name           |   deploy |   access | alias          | version   |   ostype | owner   |   size | desc                            |
        +================+==========+==========+================+===========+==========+=========+========+=================================+
        | centos-6.4     |        1 |        1 | centos-6.4     | 1.0.3     |        1 | admin   |  10240 | CentOS Linux 6.4 64-bit         |
        +----------------+----------+----------+----------------+-----------+----------+---------+--------+---------------------------------+
        | scientific-6.4 |        1 |        1 | scientific-6.4 | 1.0.3     |        1 | admin   |  10240 | Scientific Linux 6.4 64-bit     |
        +----------------+----------+----------+----------------+-----------+----------+---------+--------+---------------------------------+
        | ubuntu-12.04   |        1 |        1 | ubuntu-12.04   | 1.0.3     |        1 | admin   |  10240 | Ubuntu Linux 12.04.2 LTS 64-bit |
        +----------------+----------+----------+----------------+-----------+----------+---------+--------+---------------------------------+

