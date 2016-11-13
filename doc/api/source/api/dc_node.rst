:mod:`api.dc.node`
==================

/dc/*(dc)*/node
---------------

.. autofunction:: api.dc.node.views.dc_node_list

    |es example|:

    .. sourcecode:: bash

        es get /dc/cloud1/node

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/dc/cloud1/node/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    "node99.erigones.com"
                ], 
                "task_id": "1e1d23-6f75849b-21ea-4187-8e00"
        }

/dc/*(dc)*/node/*(hostname)*
----------------------------

.. autofunction:: api.dc.node.views.dc_node

    |es example|:

    .. sourcecode:: bash

        es create /dc/cloud1/node/node99.erigones.com -strategy 1

    .. sourcecode:: json

        {   
            "url": "https://my.erigones.com/api/dc/cloud1/node/node99.erigones.com/",
            "status": 200,
            "method": "POST",
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "ram_free": 7680, 
                    "ram": 16384, 
                    "hostname": "node99.erigones.com", 
                    "strategy": 1, 
                    "priority": 100, 
                    "disk_free": 109772, 
                    "cpu_free": 3, 
                    "disk": 314572, 
                    "cpu": 8
                }, 
                "task_id": "1e7d23-6f75849b-8e41-4f5d-8393"
            }
        }

