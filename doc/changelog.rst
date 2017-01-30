Changelog
#########


2.4.0 (unreleased)
==================

Features
--------

- Reveal snapshot and backup IDs - `#24 <https://github.com/erigones/esdc-ce/issues/24>`__
- Changed all VM-related API calls to be able to handle UUID-based requests instead of only hostname - `#16 <https://github.com/erigones/esdc-ce/issues/16>`__
- Added support for nics.*.allowed_ips (multiple IPs per NIC) - `#3 <https://github.com/erigones/esdc-ce/issues/3>`__
- Added VM UUID output value across all relevant API calls - `#23 <https://github.com/erigones/esdc-ce/issues/23>`__
- Backup restore and snapshot restore accept VM UUID besides hostname as a parameter - `#26 <https://github.com/erigones/esdc-ce/issues/26>`__
- Backup restore API call has no default target vm and disk anymore, which makes the call less error-prone - `#26 <https://github.com/erigones/esdc-ce/issues/26>`__
- Implemented task retries after operational errors (mgmt callbacks) - `#38 <https://github.com/erigones/esdc-ce/issues/38>`__
- Added DNS_ENABLED module into DC settings (API & GUI) - `#45 <https://github.com/erigones/esdc-ce/issues/45>`__
- Exposed compute node, network and image UUIDs via API - `#49 <https://github.com/erigones/esdc-ce/issues/49>`__
- Added harvest_vm function into API documentation - `#51 <https://github.com/erigones/esdc-ce/issues/51>`__
- Made image server optional and configurable (``VMS_IMAGE_VM``) - `#52 <https://github.com/erigones/esdc-ce/issues/52>`__
- Implemented update mechanism of Danube Cloud infrastructure/OS services - `#44 <https://github.com/erigones/esdc-ce/issues/44>`__
- Added explanations to DC settings GUI section - `#56 <https://github.com/erigones/esdc-ce/issues/56>`__
- Changed system initialization to include all images imported on head node - `#61 <https://github.com/erigones/esdc-ce/issues/61>`__


Bugs
----

- Fixed bug with monitoring synchronization called twice during new VM deployment - `#32 <https://github.com/erigones/esdc-ce/issues/32>`__
- Patched celery beat to achieve correct behavior during program termination - `#40 <https://github.com/erigones/esdc-ce/issues/40>`__
- Updated message box that displays information about unavailable nodes to show/hide dynamically - `#35 <https://github.com/erigones/esdc-ce/issues/35>`__
- Fixed image import of images with same name - `#61 <https://github.com/erigones/esdc-ce/issues/61>`__
- Fixed initial VM harvest problem with temporary unreachable worker - `#61 <https://github.com/erigones/esdc-ce/issues/61>`__


2.3.3 (unreleased)
==================

Features
--------

Bugs
----

- Fixed permission problems during byte-compilation of modules in production - `#28 <https://github.com/erigones/esdc-ce/issues/28>`__
- Fixed validation of MON_ZABBIX_TEMPLATES_VM_NIC and MON_ZABBIX_TEMPLATES_VM_DISK DC settings - `#31 <https://github.com/erigones/esdc-ce/issues/31>`__
- Fixed validation of placeholders supported in DC Settings - `#34 <https://github.com/erigones/esdc-ce/issues/34>`__
- Fixed update script to call its NEW self - `#44 <https://github.com/erigones/esdc-ce/issues/44>`__


2.3.2 (released on 2016-12-17)
==============================

Features
--------

- Added info about Danube Cloud release edition into output of GET system_version - `#21 <https://github.com/erigones/esdc-ce/issues/21>`__

Bugs
----

- Fixed post-update reload of application (api, sio) web services - `#20 <https://github.com/erigones/esdc-ce/issues/20>`__
- Fixed problem when reading big log files via GET system_logs and system_node_logs - `#22 <https://github.com/erigones/esdc-ce/issues/22>`__


2.3.1 (released on 2016-12-15)
==============================

Features
--------

- Updated names of KVM OS types - `#1 <https://github.com/erigones/esdc-ce/issues/1>`__
- Added explanatory help text to the tags field - `#2 <https://github.com/erigones/esdc-ce/issues/2>`__

Bugs
----

- Fixed user details broken page (email address validation problem) - `#14 <https://github.com/erigones/esdc-ce/issues/14>`__
- Fixed broken link to http-routingtable.html - `#5 <https://github.com/erigones/esdc-ce/issues/5>`__
- Fixed broken 404 page - `#5 <https://github.com/erigones/esdc-ce/issues/5>`__
- Fixed multiple broken links in API documentation - `#10 <https://github.com/erigones/esdc-ce/issues/10>`__
- Fixed ``KeyError: 'get_image_manifes_url'`` error during POST imagestore_image_manage - `#8 <https://github.com/erigones/esdc-ce/issues/8>`__
- Added support for Danube Cloud (erigones) image tags into POST image_manage - `#7 <https://github.com/erigones/esdc-ce/issues/7>`__
- Fixed dhcp_passthrough missing default value in POST net_manage - `#15 <https://github.com/erigones/esdc-ce/issues/15>`__
- Fixed error causing inability of SuperAdmin user to add SSH key for another user - `#18 <https://github.com/erigones/esdc-ce/issues/18>`__


2.3.0 (released on 2016-11-14)
==============================

Features
--------

- Going open source. Yeah!

Bugs
----

