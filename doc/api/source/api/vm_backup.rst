:mod:`api.vm.backup`
====================

/vm/define/backup
-----------------

.. autofunction:: api.vm.backup.views.vm_define_backup_list_all


/vm/*(hostname)*/define/backup
------------------------------

.. autofunction:: api.vm.backup.views.vm_define_backup_list

    |es example|:

    .. sourcecode:: bash

        es get /vm/example.cust.erigones.com/define/backup

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/demo01.cust.erigones.com/define/backup/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    {
                        "node": "node99.erigones.com", 
                        "name": "daily", 
                        "schedule": "0 4 * * *", 
                        "hostname": "example.cust.erigones.com", 
                        "disk_id": 1, 
                        "active": true, 
                        "zpool": "zones", 
                        "retention": 30, 
                        "bwlimit": null, 
                        "desc": ""
                    }
                ], 
                "task_id": "1e1-6f75849b-11b8-4bf1-8f66"
            }
        }

/vm/*(hostname)*/define/backup/*(bkpdef)*
-----------------------------------------

.. autofunction:: api.vm.backup.views.vm_define_backup

    |es example|:

    .. sourcecode:: bash

        es create /vm/example.cust.erigones.com/define/backup/daily -disk_id 1 -schedule "0 4 * * *" -retention 30 -node node99.erigones.com

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/demo01.cust.erigones.com/define/backup/daily/", 
            "status": 201, 
            "method": "POST", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "node": "node99.erigones.com", 
                    "name": "daily", 
                    "schedule": "0 4 * * *", 
                    "hostname": "example.cust.erigones.com", 
                    "disk_id": 1, 
                    "active": true, 
                    "zpool": "zones", 
                    "retention": 30, 
                    "bwlimit": null, 
                    "desc": ""
                }, 
                "task_id": "1e1-6f75849b-3e19-400b-9108"
            }
        }

/vm/*(hostname)*/backup
-----------------------

.. autofunction:: api.vm.backup.views.vm_backup_list

    |es example|:

    .. sourcecode:: bash

        es get /vm/example.cust.erigones.com/backup

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/backup/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    {
                        "status": 1, 
                        "name": "daily-20131014_133701", 
                        "created": "2013-10-14T13:37:01.123Z", 
                        "hostname": "example.cust.erigones.com", 
                        "disk_id": 1, 
                        "note": "", 
                        "node": "node99.erigones.com",
                        "size": 41843149,
                        "time": 1337,
                        "define": "daily"
                    }
                ], 
                "task_id": "0-6a75b49b-e63b-4a45-4ffa"
            }
        }

/vm/*(hostname)*/backup/*(bkpname)*
-----------------------------------

.. autofunction:: api.vm.backup.views.vm_backup

    |es example|:

    .. sourcecode:: bash

        es create /vm/example.cust.erigones.com/backup/daily -disk 1

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/backup/daily/", 
            "status": 200, 
            "method": "POST", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "message": "Backup successfully created", 
                    "returncode": 0, 
                    "detail": "name=daily-20131014_133701, disk_id=1"
                }, 
                "task_id": "0-8b37f604-4930-41d6-1dbb"
            }
        }
