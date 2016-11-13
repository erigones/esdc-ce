:mod:`api.network.base`
=======================

/network
--------

.. autofunction:: api.network.base.views.net_list

    |es example|:

    .. sourcecode:: bash

        es get /network

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/network/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    "testlan", 
                    "private1"
                ], 
                "task_id": "1e1d1-6f75849b-0fbe-4295-9df3"
            }
        }


/network/*(name)*
-----------------

.. autofunction:: api.network.base.views.net_manage

    |es example|:

    .. sourcecode:: bash

        es create /network/private1 -network 10.1.1.0 -netmask 255.255.255.0 -gateway 10.1.1.1 -nic_tag internal -vlan_id 101

    .. sourcecode:: json

        {   
            "url": "https://my.erigones.com/api/network/private1/",
            "status": 200,
            "method": "POST",
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "resolvers": [], 
                    "ptr_domain": "", 
                    "name": "private1", 
                    "nic_tag": "internal", 
                    "dns_domain": "", 
                    "access": 3, 
                    "alias": "private1", 
                    "netmask": "255.255.255.0", 
                    "owner": "admin", 
                    "dc_bound": false,
                    "desc": "", 
                    "gateway": "10.1.1.1", 
                    "vlan_id": 101, 
                    "network": "10.1.1.0"
                }, 
                "task_id": "1e1d23-6f75849b-2018-4919-8164"
            }
        }

