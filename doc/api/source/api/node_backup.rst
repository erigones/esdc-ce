:mod:`api.node.backup`
======================

/node/*(hostname)*/define/backup
--------------------------------

.. autofunction:: api.node.backup.views.node_vm_define_backup_list


/node/*(hostname)*/backup
-------------------------

.. autofunction:: api.node.backup.views.node_vm_backup_list

    |es example|:

    .. sourcecode:: bash

        es get /vm/node99.erigones.com/backup

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/node/node99.erigones.com/backup/", 
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
