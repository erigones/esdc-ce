:mod:`api.vm.define`
====================

/vm/define
----------

.. autofunction:: api.vm.define.views.vm_define_list

    |es example|:

    .. sourcecode:: bash

        es get /vm/define

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/define/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    {
                        "node": null, 
                        "ram": 1024, 
                        "hostname": "example.cust.erigones.com", 
                        "owner": "user@example.com", 
                        "alias": "example", 
                        "vcpus": 1, 
                        "template": null, 
                        "ostype": 1
                    }, 
                ], 
                "task_id": "0-6f75849b-71fc-44b9-a2b5"
            }
        }

/vm/*(hostname_or_uuid)*/define
-------------------------------

.. autofunction:: api.vm.define.views.vm_define

    |es example|:

    .. sourcecode:: bash

        es create /vm/example.cust.erigones.com/define -alias example -vcpus 1 -ram 1024 -ostype 1

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/define/", 
            "status": 201, 
            "method": "POST", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "node": null, 
                    "ram": 1024, 
                    "hostname": "example.cust.erigones.com", 
                    "owner": "user@example.com", 
                    "alias": "example", 
                    "vcpus": 1, 
                    "template": null, 
                    "ostype": "1"
                }, 
                "task_id": "0-6a11849b-71fc-44b9-d31d"
            }
        }


/vm/*(hostname_or_uuid)*/define/disk
------------------------------------

.. autofunction:: api.vm.define.views.vm_define_disk_list

    |es example|:

    .. sourcecode:: bash

        es get /vm/example.cust.erigones.com/define/disk

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/define/disk/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    {
                        "compression": "off", 
                        "image": "centos-6.4", 
                        "boot": true, 
                        "zpool": "zones", 
                        "model": "virtio", 
                        "size": 51200
                    }
                ], 
                "task_id": "0-6f75849b-1907-42a7-888f"
            }
        }

/vm/*(hostname_or_uuid)*/define/disk/*(disk_id)*
------------------------------------------------

.. autofunction:: api.vm.define.views.vm_define_disk

    |es example|:

    .. sourcecode:: bash

        es create /vm/example.cust.erigones.com/define/disk/1 -size 51200 -image centos-6.4 -boot true

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/define/disk/1/", 
            "status": 201, 
            "method": "POST", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "compression": "off", 
                    "image": "centos-6.4", 
                    "boot": true, 
                    "zpool": "zones", 
                    "model": "virtio", 
                    "size": 51200
                }, 
                "task_id": "0-6f75849b-fd32-4d02-a08a"
            }
        }


/vm/*(hostname_or_uuid)*/define/nic
-----------------------------------

.. autofunction:: api.vm.define.views.vm_define_nic_list

    |es example|:

    .. sourcecode:: bash

        es get /vm/example.cust.erigones.com/define/nic

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/define/nic/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    {
                        "ip": "46.229.234.100", 
                        "nic_tag": "external", 
                        "netmask": "255.255.255.0", 
                        "dns": true, 
                        "net": "external", 
                        "model": "virtio", 
                        "gateway": "46.229.234.1", 
                        "vlan_id": 0
                    }
                ], 
                "task_id": "0-6f75849b-fded-477d-b6de"
            }
        }

/vm/*(hostname_or_uuid)*/define/nic/*(nic_id)*
----------------------------------------------

.. autofunction:: api.vm.define.views.vm_define_nic

    |es example|:

    .. sourcecode:: bash

        es create /vm/example.cust.erigones.com/define/nic/1 -net external

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/vm/example.cust.erigones.com/define/nic/1/", 
            "status": 201, 
            "method": "POST", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "ip": "46.229.234.100", 
                    "nic_tag": "external", 
                    "netmask": "255.255.255.0", 
                    "dns": true, 
                    "net": "external", 
                    "model": "virtio", 
                    "gateway": "46.229.234.1", 
                    "vlan_id": 0
                }, 
                "task_id": "0-6f75849b-4b46-453f-acee"
            }
        }

/vm/*(hostname_or_uuid)*/define/revert
--------------------------------------

.. autofunction:: api.vm.define.views.vm_define_revert

