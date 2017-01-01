Changelog
#########


2.3.3 (unreleased)
========================================

Features
--------

Bugs
----

- Fixed permission problems during byte-compilation of modules in production - `#28 <https://github.com/erigones/esdc-ce/issues/28>`__
- Fixed validation of MON_ZABBIX_TEMPLATES_VM_NIC and MON_ZABBIX_TEMPLATES_VM_DISK DC settings - `#31 <https://github.com/erigones/esdc-ce/issues/31>`__


2.3.2 (released on 2016-12-17)
========================================

Features
--------

- Added info about Danube Cloud release edition into output of GET system_version - `#21 <https://github.com/erigones/esdc-ce/issues/21>`__

Bugs
----

- Fixed post-update reload of application (api, sio) web services - `#20 <https://github.com/erigones/esdc-ce/issues/20>`__
- Fixed problem when reading big log files via GET system_logs and system_node_logs - `#22 <https://github.com/erigones/esdc-ce/issues/22>`__


2.3.1 (released on 2016-12-15)
========================================

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
- Fixed dhcp_passthrough missing default value in POST net_manage `#15 <https://github.com/erigones/esdc-ce/issues/15>`__
- Fixed error causing inability of SuperAdmin user to add SSH key for another user `#18 <https://github.com/erigones/esdc-ce/issues/18>`__


2.3.0 (released on 2016-11-14)
========================================

Features
--------

- Going open source. Yeah!

Bugs
----

