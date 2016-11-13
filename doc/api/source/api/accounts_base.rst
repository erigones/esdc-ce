:mod:`api.accounts.base` --- API login & logout
===============================================

/accounts/login
---------------

.. note:: Instead of logging into the API, you can use the ``ES-API-KEY`` HTTP header or ``-api-key`` :ref:`es parameter <es-parameters>` to perform an authenticated API request.

.. autofunction:: api.accounts.base.views.api_login

    |es example|:

    .. sourcecode:: bash

        es login -username user@example.com -password Y0urPassw0rd

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/accounts/login/", 
            "status": 200, 
            "method": "POST", 
            "text": {
                "token": "00000a000aa0a00000a0aa0a0a00000a00000000", 
                "detail": "Welcome to Danube Cloud API."
            }
        }

.. warning:: :ref:`es <es-tool>` stores the session token in a plain text file (by default: ``/tmp/esdc.session``)

.. note:: The API session token expires after 1 hour after successful login.


/accounts/logout
----------------

.. autofunction:: api.accounts.base.views.api_logout

    |es example|:

    .. sourcecode:: bash

        es logout

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/accounts/logout/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "detail": "Bye."
            }
        }

