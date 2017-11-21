:mod:`api.template.base`
========================

/template
---------

.. autofunction:: api.template.base.views.template_list

/template/*(name)*
------------------

.. autofunction:: api.template.base.views.template_manage


    |es example|:

    .. sourcecode:: bash

        es create /template/linux-small1 -ostype 1 -vm_define 'json::{"vcpus": 1, "ram":512}' -vm_define_disk 'json::[{"size": "10240"}]' -vm_define_snapshot 'json::[{"name": "hourly", "disk_id": 1, "retention": 48, "desc": "Automatic hourly snapshot of 1st disk"}]'

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/template/linux-small1/",
            "status": 201,
            "method": "POST",
            "text": {
                "status": "SUCCESS",
                "result": {
                    "vm_define_snapshot": [
                        {
                            "desc": "Automatic hourly snapshot of 1st disk",
                            "name": "hourly",
                            "disk_id": 1,
                            "retention": 48
                        }
                    ],
                    "name": "linux-small1",
                    "created": "2016-11-11T15:15:16.079537Z",
                    "vm_define_backup": [],
                    "access": 3,
                    "alias": "linux-small1",
                    "dc_bound": false,
                    "vm_define_disk": [
                        {
                            "size": "10240"
                        }
                    ],
                    "vm_define_disk": [],
                    "ostype": 1,
                    "owner": "admin",
                    "vm_define_nic": [],
                    "vm_define": {
                        "vcpus": 1,
                        "ram": 512
                    },
                    "desc": ""
                },
                "task_id": "1d1u23-6f75849b-f4a3-4c29-8fd9"
            }
        }

