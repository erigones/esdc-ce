:mod:`api.system.stats`
=======================

/system/stats
-------------

.. autofunction:: api.system.stats.views.system_stats

    |es example|:

    .. sourcecode:: bash

        es get /system/stats

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/system/stats/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "created": "2017-02-26T15:13:42.274394Z",
                    "vms_total": 61,
                    "vms": {
                        "frozen": 1,
                        "unknown": 0,
                        "running": 58,
                        "stopped": 2,
                        "notcreated": 0
                    },
                    "nodes_total": 7,
                    "nodes": {
                        "unreachable": 0,
                        "offline": 1,
                        "unlicensed": 0,
                        "online": 6
                    },
                    "dcs_total": 16,
                    "dcs": {
                        "public": 2,
                        "private": 14
                    }
                },
                "task_id": "1e1d1-6f75849b-0fbe-4295-9df4"
            }
        }
