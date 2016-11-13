:mod:`api.vm.snapshot`
======================

/vm/define/snapshot
-------------------

.. autofunction:: api.vm.snapshot.views.vm_define_snapshot_list_all


/vm/*(hostname)*/define/snapshot
--------------------------------

.. autofunction:: api.vm.snapshot.views.vm_define_snapshot_list

    |es example|:

    .. sourcecode:: bash

        es get /vm/example.cust.erigones.com/define/snapshot

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/define/snapshot/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    {
                        "name": "daily", 
                        "schedule": "30 5 * * *", 
                        "hostname": "example.cust.erigones.com", 
                        "disk_id": 1, 
                        "active": true, 
                        "retention": 30, 
                        "desc": ""
                    }
                ], 
                "task_id": "1e1-6f75849b-f77a-4356-a00e"
            }
        }

/vm/*(hostname)*/define/snapshot/*(snapdef)*
--------------------------------------------

.. autofunction:: api.vm.snapshot.views.vm_define_snapshot

    |es example|:
    
    .. sourcecode:: bash

        es create /vm/example.cust.erigones.com/define/snapshot/daily -disk_id 1 -schedule "30 5 * * *" -retention 30

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/define/snapshot/daily/", 
            "status": 201, 
            "method": "POST", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "name": "daily", 
                    "schedule": "30 5 * * *", 
                    "hostname": "example.cust.erigones.com", 
                    "disk_id": 1, 
                    "active": true, 
                    "retention": 30, 
                    "desc": ""
                }, 
                "task_id": "1e1-6f75849b-564b-4be3-bff0"
            }
        }

/vm/*(hostname)*/snapshot
-------------------------

.. autofunction:: api.vm.snapshot.views.vm_snapshot_list

    |es example|:

    .. sourcecode:: bash

        es get /vm/example.cust.erigones.com/snapshot

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/snapshot/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    {
                        "status": 1, 
                        "name": "backup1", 
                        "created": "2012-01-22T23:23:23.465Z", 
                        "hostname": "example.cust.erigones.com", 
                        "disk_id": 1, 
                        "note": "", 
                        "type": 2,
                        "define": null
                    }
                ], 
                "task_id": "0-6f75849b-e62b-4d45-81f9"
            }
        }

/vm/*(hostname)*/snapshot/*(snapname)*
--------------------------------------

.. autofunction:: api.vm.snapshot.views.vm_snapshot

    |es example|:

    .. sourcecode:: bash

        es create /vm/example.cust.erigones.com/snapshot/backup1 -disk 1

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/snapshot/backup1/", 
            "status": 200, 
            "method": "POST", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "message": "Snapshot successfully created", 
                    "returncode": 0, 
                    "detail": "name=backup1, disk_id=1, type=2"
                }, 
                "task_id": "0-7b37f603-4930-41d6-8da6"
            }
        }
