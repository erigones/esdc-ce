:mod:`api.vm.migrate`
=====================

/vm/*(hostname)*/migrate
------------------------

.. autofunction:: api.vm.migrate.views.vm_migrate

    |es example|:

    .. sourcecode:: bash

        es set /vm/example.cust.erigones.com/migrate -node node99.erigones.com

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/migrate/", 
            "status": 200, 
            "method": "PUT", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "returncode": 0, 
                    "message": "Successfully migrated VM example.cust.erigones.com"
                }, 
                "task_id": "0-da1343e4-6010-4939-347d"
            }
        }


/vm/*(hostname)*/migrate/dc
---------------------------

.. autofunction:: api.vm.migrate.views.vm_dc

