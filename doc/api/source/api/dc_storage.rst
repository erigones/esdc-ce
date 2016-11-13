:mod:`api.dc.storage`
=====================

/dc/*(dc)*/storage
------------------

.. autofunction:: api.dc.storage.views.dc_storage_list

    |es example|:

    .. sourcecode:: bash

        es get /dc/cloud1/storage

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/dc/cloud1/storage/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    "zones@node99.erigones.com",
                    "db@node99.erigones.com"
                ], 
                "task_id": "1e1d23-6f75849b-21ea-4187-af26"
        }

/dc/*(dc)*/storage/*(zpool@node)*
---------------------------------

.. autofunction:: api.dc.storage.views.dc_storage

    |es example|:

    .. sourcecode:: bash

        es create /dc/cloud1/storage/db@node99.erigones.com

    .. sourcecode:: json

        {   
            "url": "https://my.erigones.com/api/dc/cloud1/storage/db/",
            "status": 200,
            "method": "POST",
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "access": 3, 
                    "alias": "db", 
                    "size_free": 245760, 
                    "owner": "admin", 
                    "zpool": "db", 
                    "desc": "", 
                    "type": "1", 
                    "size": 409600
                }, 
                "task_id": "1e1d23-6f75849b-b5cc-4544-8bdd"
        }

