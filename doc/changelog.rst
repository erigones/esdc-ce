Changelog
#########

3.1.0
=====
Released on `TBD`

Features
--------

- Moved VM replication from Enterprise Edition to Community Edition - `#381 <https://github.com/erigones/esdc-ce/issues/381>`__
- Moved HA scripts and playbooks from Enterprise Edition to Community Edition - `#381 <https://github.com/erigones/esdc-ce/issues/381>`__


3.0.0
=====
Released on 2018-05-07

Features
--------

- Added script for automating overlays creation - `#91 <https://github.com/erigones/esdc-factory/issues/91>`__
- Monitoring hostgroups are either datacenter-based or global - `#93 <https://github.com/erigones/esdc-ce/issues/93>`__
- Monitoring hostgroups are automatically created on VM and Node update if they don't exist - `#93 <https://github.com/erigones/esdc-ce/issues/93>`__
- Added API for managing monitoring hostgroups - `#94 <https://github.com/erigones/esdc-ce/issues/94>`__
- Added API for managing monitoring actions - `#94 <https://github.com/erigones/esdc-ce/issues/94>`__
- Added monitoring alert listing into API and GUI - `#95 <https://github.com/erigones/esdc-ce/issues/95>`__
- Added confirmation dialog to delete/restore of snapshots and backups - `#203 <https://github.com/erigones/esdc-ce/issues/203>`__
- Updated registration module to work without SMS - `#235 <https://github.com/erigones/esdc-ce/issues/235>`__
- Added ability to restore snapshot into another VM - `#236 <https://github.com/erigones/esdc-ce/issues/236>`__
- Updated the VM templates API + removed *experimental* flag from the ``template_manage`` API call - `#256 <https://github.com/erigones/esdc-ce/issues/256>`__
- DC settings implied monitoring hostgroups are shown near the VM, node monitoring_hostgroups setting - `#266 <https://github.com/erigones/esdc-ce/issues/266>`__
- Added node version caching and internal update events - `#271 <https://github.com/erigones/esdc-ce/issues/271>`__
- Added automatic synchronization of overlay ARP files - `#286 <https://github.com/erigones/esdc-ce/issues/286>`__
- Added script for automating platform upgrade - `#289 <https://github.com/erigones/esdc-ce/issues/289>`__
- Added status update button to compute node list - `#291 <https://github.com/erigones/esdc-ce/issues/291>`__
- Changed CPU resource accounting to use VM's cpu_cap parameter and added VMS_VM_CPU_CAP_REQUIRED setting - `#296 <https://github.com/erigones/esdc-ce/issues/296>`__
- Made compute node IP address changeable - `#305 <https://github.com/erigones/esdc-ce/issues/305>`__
- Enabled SSH multiplexing and connection reuse for inter-node communication - `#306 <https://github.com/erigones/esdc-ce/issues/306>`__
- Added experimental support for live migration - `#306 <https://github.com/erigones/esdc-ce/issues/306>`__
- Added value size limit to metadata - `#321 <https://github.com/erigones/esdc-ce/issues/321>`__
- Changed VM reboot action to perform a VM configuration update by default - `#328 <https://github.com/erigones/esdc-ce/issues/328>`__
- Changed system update API and added maintenance view with system update functionality into GUI - `#338 <https://github.com/erigones/esdc-ce/issues/338>`__
- Disabled sending of the first email during new VM creation - `#357 <https://github.com/erigones/esdc-ce/issues/357>`__
- Added support for setting DNS search domain in SunOS zones - `#363 <https://github.com/erigones/esdc-ce/issues/363>`__
- Do not allow ``vm_define*`` API calls when a read-write task is running - `#367 <https://github.com/erigones/esdc-ce/issues/367>`__

Bugs
----

- Added missing user callbacks for mgmt tasks - `#308 <https://github.com/erigones/esdc-ce/issues/308>`__
- Added missing DNS record for ns1.local after install - `#301 <https://github.com/erigones/esdc-ce/issues/301>`__
- Fixed migration of LX zones - `#294 <https://github.com/erigones/esdc-ce/issues/294>`__
- Fixed VNC port issues in VM migration - `#306 <https://github.com/erigones/esdc-ce/issues/306>`__
- Fixed wrong free storage sizes after VM migration - `#306 <https://github.com/erigones/esdc-ce/issues/306>`__
- Added automatic synchronization of Zabbix hosts after changing DC settings - `#210 <https://github.com/erigones/esdc-ce/issues/210>`__
- Fixed race condition in Zabbix host group manipulation - `#309 <https://github.com/erigones/esdc-ce/issues/309>`__
- Removed reference to non-existing ``VMS_NET_NIC_TAGS`` setting in GUI - `#310 <https://github.com/erigones/esdc-ce/issues/310>`__
- Fixed reverse lock persistence - `#317 <https://github.com/erigones/esdc-ce/issues/317>`__
- Fixed emergency cleanup for cancelled or deleted VM migration task - `#318 <https://github.com/erigones/esdc-ce/issues/318>`__
- Fixed SSL cert update (restart haproxy after SSL cert change) - `#322 <https://github.com/erigones/esdc-ce/issues/322>`__
- Fixed stale task info after image creation from snapshot - `#334 <https://github.com/erigones/esdc-ce/issues/334>`__
- Fixed potential race condition when processing incoming VM status events - `#358 <https://github.com/erigones/esdc-ce/issues/358>`__
- Fixed logging of removed VMs when node is force removed from DB - `#361 <https://github.com/erigones/esdc-ce/issues/361>`__
- Fixed creating of new VM when using a template via vm_define API call - `#364 <https://github.com/erigones/esdc-ce/issues/364>`__
- Fixed task ID validation in /task/* API calls - `#370 <https://github.com/erigones/esdc-ce/issues/370>`__
- Fixed VM message to show only if DC-related nodes are not online - `#372 <https://github.com/erigones/esdc-ce/issues/372>`__


2.6.7
=====
Released on 2017-11-06

Features
--------

- Added overlay/VXLAN support to net_manage - `#228 <https://github.com/erigones/esdc-ce/issues/228>`__
- Updated default resolver for the admin network - `esdc-factory#57 <https://github.com/erigones/esdc-factory/issues/57>`__
- Added limit for maximum number of VMs in a virtual datacenter - `#280 <https://github.com/erigones/esdc-ce/issues/280>`__
- Added support for mounting snapshots in SunOS/LX zones - `#284 <https://github.com/erigones/esdc-ce/issues/284>`__

Bugs
----


2.6.6
=====
Released on 2017-10-11

Features
--------

Bugs
----

- Image creation from snapshot fixed - `#277 <https://github.com/erigones/esdc-ce/issues/277>`__
- Added longer timeout to gunicorn-gui - `#279 <https://github.com/erigones/esdc-ce/issues/279>`__


2.6.5
=====
Released on 2017-10-04

Features
--------

- NIC tags will no longer be hardcoded, but rather colected from nodes - `#227 <https://github.com/erigones/esdc-ce/issues/227>`__
- Added ability to send Post-registration email - `#261 <https://github.com/erigones/esdc-ce/issues/261>`__
- Added ability to sort backup definitions by the schedule column - `#272 <https://github.com/erigones/esdc-ce/issues/272>`__

Bugs
----

- Restricted dc_bound API calls to require datacenter to be explicitly set via dc parameter - `#265 <https://github.com/erigones/esdc-ce/issues/265>`__
- Fixed highlighting of backups clicked on in the node's backup list - `#260 <https://github.com/erigones/esdc-ce/issues/260>`__
- Fixed Super admin delete user and got error 500 - `#263 <https://github.com/erigones/esdc-ce/issues/263>`__
- Disabled cloud-init network configuration in mgmt and mon VMs - `#270 <https://github.com/erigones/esdc-ce/issues/270>`__ + `#276 <https://github.com/erigones/esdc-ce/issues/276>`__ 
- Fixed VM stop and reboot actions in compute node's server list - `#275 <https://github.com/erigones/esdc-ce/issues/275>`__


2.6.4
=====
Released on 2017-09-11

Features
--------

- Added code to collect NIC tags via node_sysinfo API call - `#226 <https://github.com/erigones/esdc-ce/issues/226>`__
- Added ``GET /system/stats`` API function - `#233 <https://github.com/erigones/esdc-ce/issues/233>`__
- Added ability to reset VM status back to ``notcreated`` when VM does not exist on compute node - `#248 <https://github.com/erigones/esdc-ce/issues/248>`__
- Added documentation of ``json::`` and ``file::`` prefixes for *es* parameters - `esdc-docs#23 <https://github.com/erigones/esdc-docs/issues/23>`__
- Changed *es* TOKEN_STORE default to be OS independent - `#251 <https://github.com/erigones/esdc-ce/issues/251>`__
- Added ``post`` and ``put`` actions into *es* - `#252 <https://github.com/erigones/esdc-ce/issues/252>`__

Bugs
----

- Documented and implemented hidden DELETE methods for snapshot, backup, DNS records, and IP list API calls - `#237 <https://github.com/erigones/esdc-ce/issues/237>`__
- Fixed allowed_ips type on all occurrences to list instead of set to enable JSON serialization - `#242 <https://github.com/erigones/esdc-ce/issues/242>`__
- Updated all internal service VM images to be available from the image server and mgmt system - `#244 <https://github.com/erigones/esdc-ce/issues/244>`__
- Fixed the process how disks are defined when template is used - `#247 <https://github.com/erigones/esdc-ce/issues/247>`__
- Fixed bug when deploying VM with dhcp_passthrough network - `#249 <https://github.com/erigones/esdc-ce/issues/249>`__


2.6.3
=====
Released on 2017-08-21

Features
--------

- Added homepage links to images in image lists - `#239 <https://github.com/erigones/esdc-ce/issues/239>`__
- Renamed ``GET /task/log/report`` to ``GET /task/log/stats`` to be consistent with future *stats* views - `#232 <https://github.com/erigones/esdc-ce/issues/232>`__
- Simplified registration and password reset - `#225 <https://github.com/erigones/esdc-ce/issues/225>`__

Bugs
----

- Fixed behaviour after user permission change that leads to change of user's current DC - `#108 <https://github.com/erigones/esdc-ce/issues/108>`__
- Fixed SMSAPI return response status code 200 but text of the response is ERROR - `#230 <https://github.com/erigones/esdc-ce/issues/230>`__


2.6.2
=====
Released on 2017-08-09

Features
--------

Bugs
----

- Corrected version list handling during node upgrade - `#229 <https://github.com/erigones/esdc-ce/pull/229>`__


2.6.1
=====
Released on 2017-08-07

Features
--------

- Updated DC-bound form field to be unchecked by default when SuperAdmin creates a new virt object - `#206 <https://github.com/erigones/esdc-ce/issues/206>`__
- Disabled GSSAPIAuthentication for every SSH operation - `#212 <https://github.com/erigones/esdc-ce/issues/212>`__
- Added support for markdown in vm and node notes field - `#214 <https://github.com/erigones/esdc-ce/issues/214>`__

Bugs
----

- Disabled locale switching when editing other user's settings - `#224 <https://github.com/erigones/esdc-ce/issues/224>`__
- Disabled form submit when pressing Enter in Add Ticket form - `#220 <https://github.com/erigones/esdc-ce/issues/220>`__
- Fixed critical problem with Detach button calling the Delete action - `#219 <https://github.com/erigones/esdc-ce/issues/219>`__
- Fixed single element representation in array fields - `#216 <https://github.com/erigones/esdc-ce/issues/216>`__
- Fixed rendering of long-term graphs in GUI - `#209 <https://github.com/erigones/esdc-ce/issues/209>`__
- Fixed memory leak on nodes by removing librabbitmq package and using pyamqp instead - `#207 <https://github.com/erigones/esdc-ce/issues/207>`__
- Fixed 403 Forbidden message when switching datacenter in DNS domain records - `#143 <https://github.com/erigones/esdc-ce/issues/143>`__


2.6.0
=====
Released on 2017-07-21

Features
--------

- Added reflection of users and user groups from management to Zabbix monitoring - `#91 <https://github.com/erigones/esdc-ce/issues/91>`__
- Added option to configure SMS, Jabber and Email alerting for users in their user profiles - `#92 <https://github.com/erigones/esdc-ce/issues/92>`__
- Added user editable notes for VM and node - `#98 <https://github.com/erigones/esdc-ce/issues/98>`__
- Added ability to disable reservation of replicated VM resources - `#99 <https://github.com/erigones/esdc-ce/issues/99>`__
- Added ability to change the timeout period for graceful VM stop, reboot and freeze operations - `#111 <https://github.com/erigones/esdc-ce/issues/111>`__
- Removed VM zoneid fetching and updated monitoring templates - `#129 <https://github.com/erigones/esdc-ce/issues/129>`__
- Added confirmation dialog for delete action of datacenter objects - `#135 <https://github.com/erigones/esdc-ce/issues/135>`__
- Added node_vm_define_backup_list API and GUI views -  `#139 <https://github.com/erigones/esdc-ce/issues/139>`__
- Added ability to import images from local image server - `#140 <https://github.com/erigones/esdc-ce/issues/140>`__
- Updated mbuffer to version 20170515 - `#156 <https://github.com/erigones/esdc-ce/issues/156>`__
- Added VM update capability to VM reboot and stop operations - `#170 <https://github.com/erigones/esdc-ce/issues/170>`__
- Added ability to sync/fix wrong status of snapshots and dataset backups after a disaster recovery - `#174 <https://github.com/erigones/esdc-ce/issues/174>`__
- Added comparative VM graphs (CPU, memory, disk) per compute node - `#182 <https://github.com/erigones/esdc-ce/issues/182>`__
- Added basic support for Linux Zones (lx brand) - `#183 <https://github.com/erigones/esdc-ce/issues/183>`__
- Updated Python requirements - `#185 <https://github.com/erigones/esdc-ce/issues/185>`__
- Disabled GSSAPIKeyExchange for every SSH operation - `#195 <https://github.com/erigones/esdc-ce/issues/195>`__

Bugs
----

- Fixed migration of Danube Cloud internal (service) VMs - `#167 <https://github.com/erigones/esdc-ce/issues/167>`__
- Allowed IP address <-> VM association updates after manual VM configuration on hypervisor - `#168 <https://github.com/erigones/esdc-ce/issues/168>`__
- Force change of the VM status in the DB with current status from vmadm - `#171 <https://github.com/erigones/esdc-ce/issues/171>`__
- Fixed IP address validation, when multiple IPs are being added - `#177 <https://github.com/erigones/esdc-ce/issues/177>`__
- Fixed problem with high amount of network traffic in the celeryev exchange - `#179 <https://github.com/erigones/esdc-ce/issues/179>`__
- Disable current compute in VM migration dialog - `#191 <https://github.com/erigones/esdc-ce/issues/191>`__
- Fixed displaying of disk IO monitoring graphs of KVMs - `#193 <https://github.com/erigones/esdc-ce/issues/193>`__
- Fixed plotting of stacked graph when a series has no data - `#205 <https://github.com/erigones/esdc-ce/issues/205>`__


2.5.3
=====
Released on 2017-05-16

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


2.5.2
=====
Released on 2017-04-11

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


2.5.1
=====
Released on 2017-03-07

Features
--------

Bugs
----

- Fixed bug that caused node monitoring graphs not to show, when not in main DC - `#100 <https://github.com/erigones/esdc-ce/issues/100>`__
- Fixed scrolling to first input field with an error in modal form - `#88 <https://github.com/erigones/esdc-ce/issues/88>`__


2.5.0
=====
Released on 2017-03-03

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


2.4.0
=====
Released on 2017-02-22

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


2.3.3
=====
Released on 2017-02-04

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


2.3.2
=====
Released on 2016-12-17

Features
--------

- Added info about Danube Cloud release edition into output of GET system_version - `#21 <https://github.com/erigones/esdc-ce/issues/21>`__

Bugs
----

- Fixed post-update reload of application (api, sio) web services - `#20 <https://github.com/erigones/esdc-ce/issues/20>`__
- Fixed problem when reading big log files via GET system_logs and system_node_logs - `#22 <https://github.com/erigones/esdc-ce/issues/22>`__


2.3.1
=====
Released on 2016-12-15

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


2.3.0
=====
Released on 2016-11-14

Features
--------

- Going open source. Yeah!

Bugs
----

