:mod:`api.task` - Task results and task log
*******************************************

/task
-----

.. autofunction:: api.task.views.task_list

    |es example|:

    .. sourcecode:: bash

        es get /task

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/task/", 
            "status": 200, 
            "method": "GET", 
            "text": [ 
                    "0-fdc277df-84d6-4102-a6d5", 
                    "0-4b48594c-2d77-4b72-a1e1" 
           ]  
        }


/task/*(task_id)*
-----------------

.. autofunction:: api.task.views.task_details

    |es example|:

    .. sourcecode:: bash

        es get /task/0-4b48594c-2d77-4b72-a1e1

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/task/0-4b48594c-2d77-4b72-a1e1", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "method": "PUT", 
                "hostname": "example.cust.erigones.com", 
                "action": "start", 
                "view": "vm_status", 
                "task_id": "0-4b48594c-2d77-4b72-a1e1"
            }
        }


/task/*(task_id)*/status
------------------------

.. autofunction:: api.task.views.task_status

    |es example|:

    .. sourcecode:: bash

        es get /task/0-4b48594c-2d77-4b72-a1e1/status

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/task/0-4b48594c-2d77-4b72-a1e1/status/", 
            "status": 201, 
            "method": "GET", 
            "text": {
                "status": "PENDING", 
                "result": null, 
                "task_id": "0-4b48594c-2d77-4b72-a1e1"
            }
        }


/task/*(task_id)*/done
----------------------

.. autofunction:: api.task.views.task_done

    |es example|:

    .. sourcecode:: bash

        es get /task/0-4b48594c-2d77-4b72-a1e1/done

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/task/0-4b48594c-2d77-4b72-a1e1/done/", 
            "status": 201, 
            "method": "GET", 
            "text": {
                "done": false, 
                "task_id": "0-4b48594c-2d77-4b72-a1e1"
            }
        }


/task/*(task_id)*/cancel
------------------------

.. autofunction:: api.task.views.task_cancel

    |es example|:

    .. sourcecode:: bash

        es set /task/0-4b48594c-2d77-4b72-a1e1/cancel

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/task/0-4b48594c-2d77-4b72-a1e1/cancel/", 
            "status": 410, 
            "method": "PUT", 
            "text": {
                "status": "REVOKED", 
                "result": "terminated", 
                "task_id": "0-4b48594c-2d77-4b72-a1e1"
            }
        }


/task/log
---------

.. autofunction:: api.task.views.task_log

    |es example|:

    .. sourcecode:: bash

        es get /task/log

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/task/log/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "results": [
                    {
                        "time": "2012-22-01T23:23:23.1337+00:00", 
                        "status": "PENDING", 
                        "task": "0-b6c8aa88-c7a2-4977-8738",
                        "object_type": "vm",
                        "object_name": "example.cust.erigones.com", 
                        "object_alias": "example", 
                        "username": "user@example.com", 
                        "msg": "Start server",
                        "detail": ""
                    }, 
                    {
                        "...": "..."
                    } 
                ]
            }
        }
