:mod:`api.vm.status`
====================

/vm/status
----------

.. autofunction:: api.vm.status.views.vm_status_list

    |es example|:

    .. sourcecode:: bash

        es get /vm/status

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/status/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    {
                        "status": "running", 
                        "alias": "example", 
                        "hostname": "example.cust.erigones.com", 
                        "status_change": "2012-01-22T23:23:23.365Z", 
                        "tasks": {}
                    }, 
                ], 
                "task_id": "0-6f75849b-fdaf-4e6e-b580"
            }
        }

/vm/*(hostname_or_uuid)*/status/*(action)*
------------------------------------------

.. autofunction:: api.vm.status.views.vm_status

    |es example|:

    .. sourcecode:: bash

        es set /vm/example.cust.erigones.com/status/start

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

