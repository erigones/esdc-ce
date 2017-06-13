Changelog
#########

2.5.3 (released on 2017-05-16)
==============================

Features
--------

- Added requests and esdc-api into requirements on mgmt and CN - commit `d7be2ca <https://github.com/erigones/esdc-ce/commit/d7be2ca1065103459a1708b5d1c5d6be7bcfac3f>`__
- Removed head node flag in GUI - `esdc-docs#13 <https://github.com/erigones/esdc-docs/issues/13>`__
- Add support for appending additional SSH authorized_keys into the service VMs - `esdc-factory#43 <https://github.com/erigones/esdc-factory/issues/43>`__
- Added GET mon_template_list and GET mon_hostgroup_list API views for listing monitoring templates and hostgroups - `#90 <https://github.com/erigones/esdc-ce/issues/90>`__
- Added dropdown menus (with tags support) to form fields for selecting monitoring templates and hostgroups - `#90 <https://github.com/erigones/esdc-ce/issues/90>`__
- Hidden input fields for disabled modules - `#146 <https://github.com/erigones/esdc-ce/issues/146>`__
- Create required `domainmetadata` for every newly created domain - `#151 <https://github.com/erigones/esdc-ce/issues/151>`__
- Updated API call `PUT vm_manage` to support forced change of the node on the VM - `#154 <https://github.com/erigones/esdc-ce/issues/154>`__
- Updated backup functionality to store metadata on backup node - `#155 <https://github.com/erigones/esdc-ce/issues/155>`__
- Added support for updating VLAN ID on admin network during mgmt initialization - `#166 <https://github.com/erigones/esdc-ce/issues/166>`__
- Allowed migration of Danube Cloud internal (service) VMs - `#167 <https://github.com/erigones/esdc-ce/issues/167>`__

Bugs
----

- Create required `domainmetadata` for every newly created domain - `#151 <https://github.com/erigones/esdc-ce/issues/151>`__
- Do not display *pending* status when desired VM status was already reached - `#152 <https://github.com/erigones/esdc-ce/issues/152>`__
- Fixed VM hostname fetching in `message_callback` (GUI/JS) - `#159 <https://github.com/erigones/esdc-ce/issues/159>`__


2.5.2 (released on 2017-04-11)
==============================

Features
--------

- Added more help texts about input fields accepting byte conversion units - `#86 <https://github.com/erigones/esdc-ce/issues/86>`__
- Renamed "offline" compute node status to "maintenance" - `#87 <https://github.com/erigones/esdc-ce/issues/87>`__
- Added new variables storing path to update key/cert files in core.settings - `#104 <https://github.com/erigones/esdc-ce/issues/104>`__
- Documented refreservation parameter in vm_define_disk API function - `#106 <https://github.com/erigones/esdc-ce/issues/106>`__
- Implemented SOA serial number incrementation when DNS record is updated - `#118 <https://github.com/erigones/esdc-ce/issues/118>`__
- Decreased MON_ZABBIX_TIMEOUT to 15 seconds - `#120 <https://github.com/erigones/esdc-ce/issues/120>`__
- Added visual flash for objects (table rows) added, updated or removed to/from a table - `#125 <https://github.com/erigones/esdc-ce/issues/125>`__
- Allow to update disk size of a running VM - requiring only one reboot to take effect - `#127 <https://github.com/erigones/esdc-ce/issues/127>`__
- Added current_dc (read_only) attribute to output of user_list, user_manage and dc_user(_list) views - `#131 <https://github.com/erigones/esdc-ce/issues/131>`__
- Moved Create DNS checkbox to non advanced section when creating (editing) NIC in VM - `#145 <https://github.com/erigones/esdc-ce/issues/145>`__
- Force VM status check after a failed status change - commit `ea2bfd2 <https://github.com/erigones/esdc-ce/commit/ea2bfd2203ed6559f17f095a6e619c0129d40786>`__

Bugs
----

- Added template for HTTP 403 status code - `#96 <https://github.com/erigones/esdc-ce/issues/96>`__
- Fixed errors in graph descriptions - `#112 <https://github.com/erigones/esdc-ce/issues/112>`__
- Fixed default image import list, where last 30 results were not selected by the published date - `#113 <https://github.com/erigones/esdc-ce/issues/113>`__
- Fixed 500 AttributeError: 'unicode' object has no attribute 'iteritems' when doing VM undo - `#115 <https://github.com/erigones/esdc-ce/issues/115>`__
- Fixed 500 error when DNS domain owner is NULL in DB - `#116 <https://github.com/erigones/esdc-ce/issues/116>`__
- Fixed list of images to be deleted in *Delete unused images* modal - `#117 <https://github.com/erigones/esdc-ce/issues/117>`__
- Fixed 500 error during xls bulk import when ostype does not exist - `#121 <https://github.com/erigones/esdc-ce/issues/121>`__
- Fixed race conditions when using `set_request_method()` and `call_api_view()` functions - `#123 <https://github.com/erigones/esdc-ce/issues/123>`__
- Fixed `get_owners` convenience function that sometimes returned duplicate users, which resulted in occasional errors - `#136 <https://github.com/erigones/esdc-ce/issues/136>`__
- Changed erigonesd mgmt worker systemd manifest - `#150 <https://github.com/erigones/esdc-ce/issues/150>`__


2.5.1 (released on 2017-03-07)
==============================

Features
--------

Bugs
----

- Fixed bug that caused node monitoring graphs not to show, when not in main DC - `#100 <https://github.com/erigones/esdc-ce/issues/100>`__
- Fixed scrolling to first input field with an error in modal form - `#88 <https://github.com/erigones/esdc-ce/issues/88>`__


2.5.0 (released on 2017-03-03)
==============================

Features
--------

- Added compute node monitoring and graphs to GUI and API - `#13 <https://github.com/erigones/esdc-ce/issues/13>`__
- Added ``cpu_type`` parameter into vm_define API call - `#76 <https://github.com/erigones/esdc-ce/issues/76>`__
- Updated metadata input fields to accept raw JSON input - `#79 <https://github.com/erigones/esdc-ce/issues/79>`__
- Added convenience button in the OnScreenKeyboard in the virtual console that emits Ctrl+Alt+Delete - `#80 <https://github.com/erigones/esdc-ce/issues/80>`__
- Updated version of the packages in requirement files - `#81 <https://github.com/erigones/esdc-ce/issues/81>`__

Bugs
----

- Fixed bug that assigned old IP address to the VM during the redeploy - `#77 <https://github.com/erigones/esdc-ce/issues/77>`__
- Disabled TOS acceptation checkbox when TOS_LINK is empty - `#78 <https://github.com/erigones/esdc-ce/issues/78>`__
- Fixed RAM/HDD size rounding in sample export spreadsheet - `#83 <https://github.com/erigones/esdc-ce/issues/83>`__
- Fixed race conditions that could happen during VM status changes - `#85 <https://github.com/erigones/esdc-ce/issues/85>`__


2.4.0 (released on 2017-02-22)
==============================

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
- Updated design of DC switch button - `#64 <https://github.com/erigones/esdc-ce/issues/64>`__
- Changed image repository view to show last 30 images by default - `#66 <https://github.com/erigones/esdc-ce/issues/66>`__
- Improved consistency and UX of modal button links - `#39 <https://github.com/erigones/esdc-ce/issues/39>`__
- Modified update script bin/esdc-git-update to fail when git fetch fails and display usage for invalid invocation - `#68 <https://github.com/erigones/esdc-ce/issues/68>`__
- Removed Linux Zone images from Import images view as it's not supported for now - `#73 <https://github.com/erigones/esdc-ce/issues/73>`__

Bugs
----

- Fixed bug with monitoring synchronization called twice during new VM deployment - `#32 <https://github.com/erigones/esdc-ce/issues/32>`__
- Patched celery beat to achieve correct behavior during program termination - `#40 <https://github.com/erigones/esdc-ce/issues/40>`__
- Updated message box that displays information about unavailable nodes to show/hide dynamically - `#35 <https://github.com/erigones/esdc-ce/issues/35>`__
- Fixed image import of images with same name - `#61 <https://github.com/erigones/esdc-ce/issues/61>`__
- Fixed initial VM harvest problem with temporary unreachable worker - `#61 <https://github.com/erigones/esdc-ce/issues/61>`__
- Changed reload to restart of application GUI service - commit `#05f9702 <https://github.com/erigones/esdc-ce/commit/05f97027ac542c4f284892fd3aa85e1576a553ed>`__
- Fixed redirect after VM hostname change - `#70 <https://github.com/erigones/esdc-ce/issues/70>`__
- Fixed minor issues in Import/Export functionality - `#71 <https://github.com/erigones/esdc-ce/issues/71>`__
- Fixed language switching in user profile - `#72 <https://github.com/erigones/esdc-ce/issues/72>`__
- Fixed ``GET /task/log -page <number>`` API view - `#74 <https://github.com/erigones/esdc-ce/pull/74>`__
- Fixed object_type filter in Task Log (API & GUI) - `#74 <https://github.com/erigones/esdc-ce/pull/74>`__


2.3.3 (released on 2017-02-04)
==============================

Features
--------

- Updated design of node color - commit `ed9534f <https://github.com/erigones/esdc-ce/commit/ed9534f223e56fd7a7a7074b71fe0e48f98691e0>`__

Bugs
----

- Fixed permission problems during byte-compilation of modules in production - `#28 <https://github.com/erigones/esdc-ce/issues/28>`__
- Fixed validation of MON_ZABBIX_TEMPLATES_VM_NIC and MON_ZABBIX_TEMPLATES_VM_DISK DC settings - `#31 <https://github.com/erigones/esdc-ce/issues/31>`__
- Fixed validation of placeholders supported in DC Settings - `#34 <https://github.com/erigones/esdc-ce/issues/34>`__
- Fixed update script to call its NEW self - `#44 <https://github.com/erigones/esdc-ce/issues/44>`__
- Removed DB object caching between GUI<->API internal requests - `#62 <https://github.com/erigones/esdc-ce/issues/62>`__
- Fixed DNS permission checking for DC-bound domains - `#63 <https://github.com/erigones/esdc-ce/issues/63>`__


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

