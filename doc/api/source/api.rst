.. _api-functions:

API functions
*************

The *Danube Cloud* API is built on top of modern technologies to provide fast and secure operations inside a virtualization based datacenter. Some of these technologies communicate together using asynchronous messages and others pass information using classic synchronous communication protocols. There are two types of functions available in the API depending on the kind of technologies they use to achieve the goal (synchronous and asynchronous).


.. _async-no:

Synchronous API functions
-------------------------

Most of the API functions are synchronous. The response from these functions is always a JSON object or array. In the case of a success response, the HTTP status code will be ``200`` or ``201`` (new object was created). The failure status codes (``>=400``) are different and well documented for each API function. If a function call leads to a database change, the results are logged into the task log (retrievable via :http:get:`GET /task/log </task/log>`). The task ID provided in the success response is only used as a reference to the task log entry.


.. _async-yes:

Asynchronous API functions
--------------------------

Some of the API functions can be asynchronous, which means that they can create tasks, and the result of the operation is not available immediately after the function ends. The task result can be retrieved later by using :http:get:`GET /task/(task_id)/status </task/(task_id)/status>` API call, or it can be delivered to a URL via a :ref:`user-defined HTTP callback <user-callbacks>`. The :ref:`es <es-tool>` command line client always tries to wait for the task result with a timeout set to 3600 seconds.

In the case of parameter processing errors or failed condition checks, the function behaves like a classical :ref:`synchronous API function <async-no>` giving a direct response with a failure status code (``>=400``). In some cases, the function can also create a synchronous success response with a ``200`` status code. When a task is created the function returns a ``201`` status code and the response contains a ``task_id`` and ``state`` attribute with the value set to *PENDING* or *STARTED*. The asynchronous API function always creates two task log entries with the same task ID (one when a task is created and another one when the task is finished).

.. _user-callbacks:

User Callbacks
++++++++++++++

All asynchronous functions support user-defined callbacks where the result of a *PENDING* or *STARTED* task is sent once it has finished. Function parameters required to create a callback are ``cb_url`` and ``cb_method``. The task result is sent as a JSON-encoded string in the body of an HTTP request to the URL provided in the ``cb_url`` parameter. Valid choices for the ``cb_method`` parameter are :http:method:`GET`/:http:method:`POST`/:http:method:`PUT`/:http:method:`DELETE`. The default value is ``POST``.

    |es example|:

    .. sourcecode:: bash

        es set /vm/example.cust.erigones.com/status/start -cb_method POST -cb_url http://remote.server.com/sample/callback/url/

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/status/start/",
            "status": 200,
            "method": "PUT",
            "text": {
                "status": "SUCCESS",
                "result": {
                    "message": "Successfully started VM example.cust.erigones.com",
                    "returncode": 0
                },
                "task_id": "0-a2327793-2600-423d-9f07"
            }
        }

With each callback, a ``random_token`` and ``security_token`` attribute is included in the JSON body of the HTTP request, so it is possible to check if callback request has not been faked. The ``random_token`` is randomly generated for every callback request. The ``security_token`` is a md5 hash of the ``random_token`` joined with user's ``callback_key``. To verify the request just join the ``random_token`` with your ``callback_key`` and create a md5 hash. Your md5 hash must be identical to the ``security_token`` provided in the request.

    **Callback verification example**:

    .. sourcecode:: php

        $json_response = json_decode($HTTP_RAW_POST_DATA, TRUE);

        if (md5($json_response['random_token'] . $user->callback_key) == $json_response['security_token']) {
	        print('Comparison of tokens SUCCEEDED! We can trust request... ');
        } else {
	        print('Comparison of tokens FAILED! Something dodgy is going on... ');
        }


.. _http-headers:

HTTP headers
------------

Every API response contains following HTTP headers:

=============== ================= =====================================
**Header name** **Example value** **Description**
--------------- ----------------- -------------------------------------
es_version      2.0.3             Danube Cloud version
es_username     admin             User who sent the API request
es_dc           main              Currently active virtual datacenter
=============== ================= =====================================


.. _api-parameters:

Common API parameters
---------------------

Many API functions accept the same :http:method:`GET`/:http:method:`POST`/:http:method:`PUT`/:http:method:`DELETE` parameters:

* **dc** - Used to specify the virtual datacenter for :ref:`DC-bound API functions <dc-bound>`.

.. _order_by:

* **order_by** - Comma-separated list of fields used for sorting a list of items. A ``+`` or ``-`` sign before the field name indicates sorting in descending order.

