:mod:`api.dc.base`
==================

/dc
---

.. autofunction:: api.dc.base.views.dc_list

    |es example|:

    .. sourcecode:: bash

        es get /dc

    .. sourcecode:: json

        {
            "url": "https://my.erigones.com/api/dc/", 
            "status": 200, 
            "method": "GET", 
            "text": {
                "status": "SUCCESS", 
                "result": [
                    "admin", 
                    "cloud1",
                    "main"
                ], 
                "task_id": "1e1d1-6f75849b-0fbe-4295-9df3"
            }
        }

/dc/*(dc)*
----------

.. autofunction:: api.dc.base.views.dc_manage

    |es example|:

    .. sourcecode:: bash

        es create /dc/cloud1 -site cloud.example.com

    .. sourcecode:: json

        {   
            "url": "https://my.erigones.com/api/dc/cloud1/",
            "status": 200,
            "method": "POST",
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "site": "cloud.example.com", 
                    "name": "cloud1", 
                    "access": 3, 
                    "alias": "cloud1", 
                    "owner": "admin", 
                    "groups": [], 
                    "desc": ""
                }, 
                "task_id": "1e1d23-6f75849b-2018-4919-8164"
            }
        }


/dc/*(dc)*/settings
-------------------

.. autofunction:: api.dc.base.views.dc_settings

    |es example|:

    .. sourcecode:: bash

        es get /dc/main/settings

    .. sourcecode:: json

        {   
            "url": "https://my.erigones.com/api/dc/main/settings/",
            "status": 200,
            "method": "POST",
            "text": {
                "status": "SUCCESS", 
                "result": {
                    "ACL_ENABLED": true, 
                    "API_ENABLED": true, 
                    "API_LOG_USER_CALLBACK": true,
                    "COMPANY_NAME": "Erigones, s. r. o.", 
                    "DEFAULT_FROM_EMAIL": "noreply@example.com", 
                    "DNS_HOSTMASTER": "hostmaster@example.com", 
                    "DNS_NAMESERVERS": [
                        "ns1.local"
                    ], 
                    "DNS_PTR_DEFAULT": "ptr-%(ipaddr)s.example.com", 
                    "DNS_SOA_DEFAULT": "%(nameserver)s %(hostmaster)s 2013010100 28800 7200 604800 86400", 
                    "EMAIL_ENABLED": true,
                    "EMAIL_HOST": "127.0.0.1", 
                    "EMAIL_HOST_PASSWORD": "***", 
                    "EMAIL_HOST_USER": "", 
                    "EMAIL_PORT": 25, 
                    "EMAIL_USE_SSL": false, 
                    "EMAIL_USE_TLS": false, 
                    "FAQ_ENABLED": true,
                    "MON_ZABBIX_ENABLED": true, 
                    "MON_ZABBIX_HOSTGROUPS_NODE": [], 
                    "MON_ZABBIX_HOSTGROUPS_VM": [], 
                    "MON_ZABBIX_HOSTGROUPS_VM_ALLOWED": [],
                    "MON_ZABBIX_HOSTGROUPS_VM_RESTRICT": true,
                    "MON_ZABBIX_HOSTGROUP_NODE": "Compute nodes", 
                    "MON_ZABBIX_HOSTGROUP_VM": "Virtual machines", 
                    "MON_ZABBIX_HTTP_PASSWORD": "***", 
                    "MON_ZABBIX_HTTP_USERNAME": "username", 
                    "MON_ZABBIX_NODE_SLA": true, 
                    "MON_ZABBIX_NODE_SYNC": true, 
                    "MON_ZABBIX_PASSWORD": "***", 
                    "MON_ZABBIX_SERVER": "https://zabbix.example.com/", 
                    "MON_ZABBIX_SERVER_SSL_VERIFY": true,
                    "MON_ZABBIX_TEMPLATES_NODE": [],
                    "MON_ZABBIX_TEMPLATES_VM": [],
                    "MON_ZABBIX_TEMPLATES_VM_ALLOWED": [],
                    "MON_ZABBIX_TEMPLATES_VM_DISK": [],
                    "MON_ZABBIX_TEMPLATES_VM_MAP_TO_TAGS": false,
                    "MON_ZABBIX_TEMPLATES_VM_NIC": [],
                    "MON_ZABBIX_TEMPLATES_VM_RESTRICT": true,
                    "MON_ZABBIX_TIMEOUT": 10, 
                    "MON_ZABBIX_USERNAME": "superadmin", 
                    "MON_ZABBIX_VM_SLA": true, 
                    "MON_ZABBIX_VM_SYNC": true, 
                    "PAYMENTS_EMAIL": "payments@example.com", 
                    "PAYMENTS_ENABLED": true, 
                    "PAYMENTS_NOTIFICATION_EMAIL": "payments@example.com", 
                    "PROFILE_COUNTRY_CODE_DEFAULT": "SK", 
                    "PROFILE_PHONE_PREFIX_DEFAULT": "+421", 
                    "PROFILE_SSH_KEY_LIMIT": 10, 
                    "PROFILE_TIME_ZONE_DEFAULT": "Europe/Bratislava", 
                    "REGISTRATION_ENABLED": true, 
                    "SHADOW_EMAIL": "", 
                    "SITE_LINK": "https://danubecloud.example.com", 
                    "SITE_NAME": "Erigones", 
                    "SITE_SIGNATURE": "Erigones\r\nhttps://danubecloud.example.com", 
                    "SITE_LOGO": "",
                    "SITE_ICON": "",
                    "SMS_ENABLED": true, 
                    "SMS_SMSAPI_FROM": "Erigones", 
                    "SMS_SMSAPI_PASSWORD": "***", 
                    "SMS_SMSAPI_USERNAME": "example", 
                    "SMS_PREFERRED_SERVICE": "smsapi", 
                    "SMS_PRIVATE_KEY": "***", 
                    "SUPPORT_EMAIL": "support@example.com", 
                    "SUPPORT_ENABLED": true, 
                    "SUPPORT_PHONE": "", 
                    "SUPPORT_USER_CONFIRMATION": true, 
                    "VMS_DC_ENABLED": true, 
                    "VMS_DISK_COMPRESSION_DEFAULT": "lz4", 
                    "VMS_DISK_IMAGE_DEFAULT": "", 
                    "VMS_DISK_IMAGE_ZONE_DEFAULT": "base64", 
                    "VMS_DISK_MODEL_DEFAULT": "virtio", 
                    "VMS_NET_DEFAULT": "lan", 
                    "VMS_NET_NIC_TAGS": [
                        "admin", 
                        "external", 
                        "internal", 
                        "storage"
                    ], 
                    "VMS_NET_VLAN_ALLOWED": [],
                    "VMS_NET_VLAN_RESTRICT": true,
                    "VMS_NET_LIMIT": null,
                    "VMS_ISO_LIMIT": null,
                    "VMS_IMAGE_LIMIT": null,
                    "VMS_IMAGE_REPOSITORIES": {
                        "danubecloud": "https://images.erigones.org"
                    },
                    "VMS_IMAGE_SOURCES": [],
                    "VMS_IMAGE_VM": "15bc0839-c49d-4489-a01b-4570d518fc9f",
                    "VMS_NIC_MONITORING_DEFAULT": 1,
                    "VMS_NIC_MODEL_DEFAULT": "virtio", 
                    "VMS_NODE_SSH_KEYS_SYNC": true,
                    "VMS_NODE_SSH_KEYS_DEFAULT": [],
                    "VMS_STORAGE_DEFAULT": "zones", 
                    "VMS_VGA_MODEL_DEFAULT": "std", 
                    "VMS_VM_BACKUP_COMPRESSION_DEFAULT": 0, 
                    "VMS_VM_BACKUP_DC_SIZE_LIMIT": null,
                    "VMS_VM_BACKUP_DEFINE_LIMIT": null, 
                    "VMS_VM_BACKUP_ENABLED": true, 
                    "VMS_VM_BACKUP_LIMIT": null, 
                    "VMS_VM_CPU_SHARES_DEFAULT": 100, 
                    "VMS_VM_DOMAIN_DEFAULT": "lan", 
                    "VMS_VM_MDATA_DEFAULT": {},
                    "VMS_VM_MONITORED_DEFAULT": true, 
                    "VMS_VM_OSTYPE_DEFAULT": 1, 
                    "VMS_VM_REPLICATION_ENABLED": true,
                    "VMS_VM_RESOLVERS_DEFAULT": [
                        "192.168.155.25"
                    ], 
                    "VMS_VM_SNAPSHOT_DC_SIZE_LIMIT": null,
                    "VMS_VM_SNAPSHOT_DEFINE_LIMIT": null,
                    "VMS_VM_SNAPSHOT_ENABLED": true,
                    "VMS_VM_SNAPSHOT_LIMIT_AUTO": null,
                    "VMS_VM_SNAPSHOT_LIMIT_MANUAL": null,
                    "VMS_VM_SNAPSHOT_LIMIT_MANUAL_DEFAULT": null,
                    "VMS_VM_SNAPSHOT_SIZE_LIMIT": null,
                    "VMS_VM_SNAPSHOT_SIZE_LIMIT_DEFAULT": null,
                    "VMS_VM_SSH_KEYS_DEFAULT": [],
                    "VMS_VM_ZFS_IO_PRIORITY_DEFAULT": 100, 
                    "VMS_ZONE_ENABLED": false, 
                    "dc": "main"
                }, 
                "task_id": "1e1d23-6f75849b-2018-4919-8165"
            }
        }


.. note:: Zabbix is a registered trademark of `Zabbix LLC <http://www.zabbix.com>`_.

