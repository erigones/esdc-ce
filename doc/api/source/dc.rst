.. _dc:

Virtual Datacenters
*******************

Virtual Datacenters is a concept for achieving user, group and resource isolation and at the same time allowing some form of software and hardware resource sharing.

All tasks created in *Danube Cloud* are executed inside a virtual datacenter. Especially the logging of all API functions is strictly related to the currently chosen datacenter, and there is a separate task log for each virtual datacenter.

*Danube Cloud* comes with a pre-installed public datacenter, which is available for all users. The datacenter name is *main* and it cannot be changed.


.. _dc-unbound:

DC-unbound API functions
------------------------

Some of the API modules and functions are not related to a chosen virtual datacenter and are always executed and logged in the *main* datacenter. This is especially true for compute node and user management related API functions.


.. _dc-bound:

DC-bound API functions
----------------------

Most of the API modules and functions show, create, modify or delete virtual objects (virtual machines, disk images, networks ...) which are part of a virtual datacenter. These API functions are marked as **DC-bound** and always work in the scope of a virtual datacenter. Unless a datacenter is specified manually the selection of current datacenter is ambiguous and most likely to correspond to the datacenter chosen last via the GUI.

To specify a virtual datacenter, the :ref:`resource <es-resources>` must be prefixed with the ``/dc/(dc)`` path. Optionally, when using :ref:`es <es-tool>`, the current virtual datacenter can be set by using a ``-dc (dc)`` :ref:`parameter <es-parameters>`.

    |es example|:

    .. sourcecode:: bash

        es get /dc/admin/vm

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/dc/admin/vm/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    "mgmt01.local", 
                    "zabbix01.local" 
                ], 
                "task_id": "1e1d2-6f75849b-fc64-4e1c-9a7f"
            }
        }


.. note:: Always remember to specify a virtual datacenter when using a DC-bound API function.

