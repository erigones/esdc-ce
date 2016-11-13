.. _group_api:

:mod:`api.accounts.group` --- Group manipulation
================================================

/accounts/group
---------------

.. autofunction:: api.accounts.group.views.group_list

/accounts/group/(*name*)
------------------------

.. autofunction:: api.accounts.group.views.group_manage

    |es example|:

    .. sourcecode:: bash

        es create /accounts/group/testers -permissions admin,image_admin -users admin,tester@erigones.com -alias 'Testers User Group'

    .. sourcecode:: json

        { 
            "url": "https://my.erigones.com/api/accounts/group/testers/",
            "status": 201, 
            "method": "POST",
            "text": {
                "status": "SUCCESS",
                "result": {
                    "alias": "Testers User Group",
                    "users": [
                        "admin",
                        "testerx@erigones.com"
                    ],
                    "name": "testers",
                    "permissions": [
                        "admin",
                        "image_admin"
                    ]
                },
                "task_id": "1e1d1-6f75849b-f4e5-4a88-9d7d"
            }
        }

