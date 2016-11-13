:mod:`api.accounts.user` --- User manipulation
==============================================

/accounts/user
--------------

.. autofunction:: api.accounts.user.base.views.user_list

/accounts/user/profile
----------------------

.. autofunction:: api.accounts.user.base.views.userprofile_list

/accounts/user/(*username*)
---------------------------

.. autofunction:: api.accounts.user.base.views.user_manage

/accounts/user/(*username*)/apikeys
-----------------------------------

.. autofunction:: api.accounts.user.base.views.user_apikeys

/accounts/user/(*username*)/profile
-----------------------------------

.. autofunction:: api.accounts.user.profile.views.userprofile_manage

/accounts/user/(*username*)/sshkey
----------------------------------

.. autofunction:: api.accounts.user.sshkey.views.sshkey_list

    |es example|:

    .. sourcecode:: bash

        es get /accounts/user/admin/sshkey

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/accounts/user/admin/sshkey/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    "admin@support", 
                ], 
                "task_id": "1e1d1-6f75849b-ca49-40d3-81d5"
            }
        }

/accounts/user/(*username*)/sshkey/(*title*)
--------------------------------------------

.. autofunction:: api.accounts.user.sshkey.views.sshkey_manage

    |es example|:

    .. sourcecode:: bash

        es create /accounts/user/admin/sshkey/admin@management -key 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDqEN0oe+exk6cQK+goychxNY05xkvoARqbMq4/mRqc0EjRkgXrSJGVt/vsXU/rfMDIn1hUohaGyzlXfNPFjcmJ9Ws/P25ts2OsZlZNlngFXyswAKDJU/i9CYavHFaxwKvpiSU5Bm7q7nte++77oiM+4HBxcwRCiBfry09wHPWmM/qG9roOA2C9pLJQBHc6q4HkLgFAn5HrFuFwEPZfwtQtxxR46yT9iy4lOth1/apOqNp7ABBziE3fZQ//o3e1ngtT7jW5UltMYCsX2UXI2hcgl-Hh5WkrRGls+whHlNRztL8Utt03dgXwPaxdVezTM6CN7mv6X6K8EZ72ixQ24Ai9 admin@management'

    .. sourcecode:: json
    
        {
            "url": "https://my.erigones.com/api/accounts/user/admin/sshkey/testkey/", 
            "status": 201, 
            "method": "POST", 
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "fingerprint": "9e:23:25:c5:02:28:f2:0a:42:f3:e4:af:a7:5b:75:c0", 
                    "key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDqEN0oe+exk6cQK+goychxNY05xkvoARqbMq4/mRqc0EjRkgXrSJGVt/vsXU/rfMDIn1hUohaGyzlXfNPFjcmJ9Ws/P25ts2OsZlZNlngFXyswAKDJU/i9CYavHFaxwKvpiSU5Bm7q7nte++77oiM+4HBxcwRCiBfry09wHPWmM/qG9roOA2C9pLJQBHc6q4HkLgFAn5HrFuFwEPZfwtQtxxR46yT9iy4lOth1/apOqNp7ABBziE3fZQ//o3e1ngtT7jW5UltMYCsX2UXI2hcgl-Hh5WkrRGls+whHlNRztL8Utt03dgXwPaxdVezTM6CN7mv6X6K8EZ72ixQ24Ai9 admin@management"
                    "title": "admin@management"
                }, 
                "task_id": "1e1d1-6f75849b-0b87-4dfd-a157"
            }
        }

