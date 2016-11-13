:mod:`api.network.ip`
=====================

/network/*(name)*/ip
--------------------

.. autofunction:: api.network.ip.views.net_ip_list

    |es example|:

    .. sourcecode:: bash

        es get /network/private1/ip

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/network/private1/ip/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    "10.1.1.20", 
                    "10.1.1.21", 
                    "10.1.1.22", 
                    "10.1.1.23", 
                    "10.1.1.24"
                ], 
                "task_id": "1e1d1-6f75849b-0fbe-4295-9df3"
            }
        }


/network/*(name)*/ip/*(ip)*
---------------------------

.. autofunction:: api.network.ip.views.net_ip

    |es example|:

    .. sourcecode:: bash

        es create /network/private1/ip/10.1.1.20

    .. sourcecode:: json

        {   
            "url": "https://my.erigones.com/api/network/private1/ip/10.1.1.20/",
            "status": 200,
            "method": "POST",
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "ip": "10.1.1.20", 
                    "note": "", 
                    "usage": 1,
                    "mac": null, 
                    "hostname": null, 
                    "nic_id": null, 
                    "dc": null
                }, 
                "task_id": "1e1d23-6f75849b-2018-4919-8164"
            }
        }


/network/ip/*(subnet)*
----------------------

.. autofunction:: api.network.ip.views.subnet_ip_list

