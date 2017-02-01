:mod:`api.vm.qga`
=================

/vm/*(hostname_or_uuid)*/qga/*(command)*
----------------------------------------

.. autofunction:: api.vm.qga.views.vm_qga

    |es example|:

    .. sourcecode:: bash

        es set /vm/example.cust.erigones.com/qga/get-time

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/qga/get-time", 
            "status": 200, 
            "method": "PUT", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "message": "1470161967939841000", 
                    "returncode": 0
                }, 
                "task_id": "0-a2327793-2600-423d-8f07"
            }
        }

