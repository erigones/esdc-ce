:mod:`api.iso.base`
===================

/iso
----

.. autofunction:: api.iso.base.views.iso_list

    |es example|:

    .. sourcecode:: bash

        es get /iso

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/iso/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    "os-install.iso", 
                    "rescuecd.iso"
                ], 
                "task_id": "1e1d1-6f75849b-0fbe-4295-9df3"
            }
        }


/iso/*(name)*
-------------

.. autofunction:: api.iso.base.views.iso_manage

    |es example|:

    .. sourcecode:: bash

        es create /iso/os-install.iso -ostype 1

    .. sourcecode:: json

        {   
            "url": "https://my.erigones.com/api/iso/os-install.iso/",
            "status": 200,
            "method": "POST",
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "name": "os-install.iso", 
                    "access": 3, 
                    "alias": "os-install", 
                    "ostype": "1", 
                    "owner": "admin", 
                    "dc_bound": false,
                    "desc": ""
                }, 
                "task_id": "1e1d23-6f75849b-2018-4919-8164"
            }
        }

