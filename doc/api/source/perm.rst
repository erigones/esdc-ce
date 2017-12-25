API Permissions
***************

.. note:: To be able to log in to the API and access all of the API functions the user **must have** the ``api_access`` attribute enabled.

.. note:: You can use the ``ES-API-KEY`` HTTP header or ``-api-key`` :ref:`es parameter <es-parameters>` to perform an authenticated API request.

The API functions may use the following permissions to restrict access to certain users:

================== ================== ======== ===============
**Permission**     **API name**       **ACL?** **Description**
------------------ ------------------ -------- ---------------
APIAccess                             |no|     The user must have the ``api_access`` attribute enabled.
SuperAdmin                            |no|     The user must have the ``is_super_admin`` attribute enabled.
Admin              admin              |yes|    The user must have the Admin permission or be a DC owner or SuperAdmin.
NetworkAdmin       network_admin      |yes|    The user must have the NetworkAdmin and Admin permissions or be a SuperAdmin.
ImageAdmin         image_admin        |yes|    The user must have the ImageAdmin and Admin permissions or be a SuperAdmin.
ImageImportAdmin   image_import_admin |yes|    The user must have the ImageAdmin, ImageImportAdmin and Admin permissions or be a SuperAdmin.
TemplateAdmin      template_admin     |yes|    The user must have the TemplateAdmin and Admin permissions or be a SuperAdmin.
IsoAdmin           iso_admin          |yes|    The user must have the IsoAdmin and Admin permissions or be a SuperAdmin.
UserAdmin          user_admin         |yes|    The user must have the UserAdmin and Admin permissions or be a SuperAdmin.
DnsAdmin           dns_admin          |yes|    The user must have the DnsAdmin and Admin permissions or be a SuperAdmin.
MonitoringAdmin    monitoring_admin   |yes|    The user must have the MonitoringAdmin and Admin permissions or be a SuperAdmin.
ProfileOwner                          |no|     The user must be the owner of the Profile or SuperAdmin.
VmOwner                               |no|     The user must be the owner of the Virtual Machine or have the Admin or SuperAdmin permission.
TaskCreator                           |no|     The user must be the one who created the task or have the Admin or SuperAdmin permission.
UserTask                              |no|     The user must be the owner of the object modified by the task or have the Admin or SuperAdmin permission.
DomainOwner                           |no|     The user must be the owner of the DNS Domain or SuperAdmin.
================== ================== ======== ===============

.. _ACL:

ACL
---

The ACL permissions can be assigned to groups via the :ref:`group and permission API <group_api>` and used for advanced user and group policies.
