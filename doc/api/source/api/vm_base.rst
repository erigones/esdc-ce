:mod:`api.vm.base`
==================

/vm
---

.. autofunction:: api.vm.base.views.vm_list

    |es example|:

    .. sourcecode:: bash

        es get /vm

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    "example2.cust.erigones.com", 
                    "example.cust.erigones.com" 
                ], 
                "task_id": "0-6f75849b-f2e0-4f1d-a891"
            }
        }

/vm/*(hostname)*
----------------

.. autofunction:: api.vm.base.views.vm_manage

    |es example|:

    .. sourcecode:: bash

        es create /vm/example.cust.erigones.com

    .. sourcecode:: json

        {   
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/",
            "status": 200,
            "method": "POST",
            "text": {
                "status": "SUCCESS",
                "result": {
                    "message": "Successfully created VM example.cust.erigones.com",
                    "returncode": 0
                },
                "task_id": "0-e0b6801c-dad9-4481-9bb2"
            }
        }

