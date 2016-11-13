Danube Cloud :: Community Edition
#################################

Danube Cloud web management console.

Directory structure
===================

* api/  - Implementation of Danube Cloud REST API (Django app)
* bin/  - Binaries and scripts used for controlling and executing maintenance tasks
* doc/  - Documentation regarding project
* core/ - Danube Cloud main Django project
* etc/  - Configuration files
* gui/  - Danube Cloud web interface (Django app)
* log/  - Symbolic link to var/log
* pdns/ - Django app for PowerDNS
* que/  - Celery bindings (Django app)
* sio/  - SocketIO bindings (Django app)
* tmp/  - Symbolic link to var/tmp
* var/  - Logs, static and temporary files
* vms/  - Django app facilitating DB interaction with VMs and other DB objects


Links
=====

- Homepage: https://danubecloud.org
- Wiki: https://github.com/erigones/esdc-ce/wiki
- Bug Tracker: https://github.com/erigones/esdc-ce/issues
- Twitter: https://twitter.com/danubecloud


License
=======

::

    Copyright 2016 Erigones, s. r. o.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this project except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

