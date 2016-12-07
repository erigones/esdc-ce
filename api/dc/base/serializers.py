from django.utils.translation import ugettext_lazy as _
from django.core.validators import RegexValidator
from django.conf import settings
from frozendict import frozendict

from core.external.decorators import (
    third_party_apps_dc_modules_and_settings, third_party_apps_default_dc_modules_and_settings
)
from api import serializers as s
from api.validators import validate_owner, validate_alias, validate_mdata, validate_ssh_key
from api.vm.utils import get_owners
from api.sms.utils import get_services
from api.mon.zabbix import VM_KWARGS
from gui.models import User, UserProfile, Role
from vms.models import Dc, DefaultDc, Vm, BackupDefine, Subnet
from vms.utils import DefAttrDict
from pdns.models import Domain


SENSITIVE_FIELD_NAMES = ('PASSWORD', 'PRIVATE_KEY')
SENSITIVE_FIELD_VALUE = '***'


def placeholder_validator(value, **valid_placeholders):
    """Helper for checking if the value has acceptable placeholders"""
    try:
        return value.format(**valid_placeholders)
    except (KeyError, ValueError, TypeError):
        raise s.ValidationError(_('Invalid placeholders.'))


def validate_array_placeholders(attrs, source, valid_placeholders):
    """Helper validate_ method"""
    try:
        value = attrs[source]
    except KeyError:
        pass
    else:
        for i in value:
            placeholder_validator(i, **valid_placeholders)

    return attrs


class DcSerializer(s.InstanceSerializer):
    """
    vms.models.Dc
    """
    _model_ = Dc
    _update_fields_ = ('alias', 'owner', 'access', 'desc', 'site', 'groups')
    _default_fields_ = ('name', 'alias', 'owner', 'site')
    owner_changed = None
    groups_changed = None
    groups_added = None
    groups_removed = None
    removed_users = None

    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=16)
    alias = s.SafeCharField(max_length=32)
    site = s.RegexField(r'^[a-z0-9][a-z0-9\.:-]+[a-z0-9]$', max_length=260, min_length=1)
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects, read_only=False, required=False)
    access = s.IntegerChoiceField(choices=Dc.ACCESS, default=Dc.PRIVATE)
    desc = s.SafeCharField(max_length=128, required=False)
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, instance, *args, **kwargs):
        super(DcSerializer, self).__init__(request, instance, *args, **kwargs)
        if not kwargs.get('many', False):
            self.fields['owner'].default = request.user.username  # Does not work
            self.fields['owner'].queryset = get_owners(request, all=True)

    def validate_alias(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            validate_alias(self.object, value)

        return attrs

    def validate_site(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object.pk and self.object.site == value:
                pass
            elif Dc.objects.filter(site__iexact=value).exists():
                raise s.ValidationError(_('This site hostname is already in use. '
                                          'Please supply a different site hostname.'))

        return attrs

    def validate_access(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object.pk and self.object.is_default() and int(value) != Dc.PUBLIC:
                raise s.ValidationError(_('Default datacenter must be public.'))

        return attrs

    def validate_owner(self, attrs, source):
        try:
            user = attrs[source]
        except KeyError:
            pass
        else:
            if user is None:
                if self.object.pk:
                    del attrs['owner']
                else:
                    attrs['owner'] = self.request.user

            elif self.object.pk:
                if self.object.is_default() and not user.is_staff:
                    raise s.ValidationError(_('Default datacenter must be owned by user with SuperAdmin rights.'))
                if user != self.object.owner:
                    self.owner_changed = user
                    # Cannot change owner while pending tasks exist
                    validate_owner(self.object, user, _('Datacenter'))

        return attrs

    def validate_groups(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object.pk:
                current_roles = set(self.object.roles.all())
                new_roles = set(value)

                if current_roles != new_roles:
                    self.groups_added = new_roles - current_roles
                    self.groups_removed = current_roles - new_roles
                    self.groups_changed = current_roles.symmetric_difference(new_roles)
                    self.removed_users = User.objects.distinct().filter(roles__in=self.groups_removed)

        return attrs


class SuperDcSerializer(DcSerializer):
    """
    Include groups field (only visible by staff).
    """
    groups = s.RelatedArrayField(queryset=Role.objects, source='roles', slug_field='name', required=False)


class ExtendedDcSerializer(SuperDcSerializer):
    """
    Include extended datacenter statistics (only available for staff).
    """
    extra_select = frozendict({
        'nodes': '''SELECT COUNT(*) FROM "vms_dcnode" WHERE "vms_dc"."id" = "vms_dcnode"."dc_id"''',
        'vms': '''SELECT COUNT(*) FROM "vms_vm" WHERE "vms_dc"."id" = "vms_vm"."dc_id"''',
        'real_vms': '''SELECT COUNT(*) FROM "vms_vm" LEFT OUTER JOIN "vms_slavevm" ON
    ( "vms_vm"."uuid" = "vms_slavevm"."vm_id" ) WHERE "vms_dc"."id" = "vms_vm"."dc_id" AND
    "vms_slavevm"."vm_id" IS NULL''',
        'snapshots': '''SELECT COUNT(*) FROM "vms_snapshot" LEFT OUTER JOIN "vms_vm" ON
    ( "vms_vm"."uuid" = "vms_snapshot"."vm_id" ) WHERE "vms_dc"."id" = "vms_vm"."dc_id"''',
        'backups': '''SELECT COUNT(*) FROM "vms_backup" WHERE "vms_dc"."id" = "vms_backup"."dc_id"''',
    })

    vms = s.IntegerField(read_only=True)
    nodes = s.IntegerField(read_only=True)
    snapshots = s.IntegerField(read_only=True)
    backups = s.IntegerField(read_only=True)
    real_vms = s.IntegerField(read_only=True)
    size_vms = s.IntegerField(read_only=True, source='size_vms')
    size_snapshots = s.IntegerField(read_only=True, source='size_snapshots')
    size_backups = s.IntegerField(read_only=True, source='size_backups')


@third_party_apps_dc_modules_and_settings
class DcSettingsSerializer(s.InstanceSerializer):
    """
    vms.models.Dc.settings
    """
    _global_settings = None
    _model_ = Dc
    modules = settings.MODULES  # Used in gui forms
    third_party_modules = []  # Class level storage, updated only with the decorator function
    third_party_settings = []  # Class level storage, updated only with the decorator function
    # List of settings which cannot be changed when set to False in (local_)settings.py (booleans only)
    _override_disabled_ = settings.MODULES
    _blank_fields_ = frozenset({
        'SITE_LOGO',
        'SITE_ICON',
        'SHADOW_EMAIL',
        'SUPPORT_PHONE',
        'VMS_DISK_IMAGE_DEFAULT',
        'VMS_DISK_IMAGE_ZONE_DEFAULT',
        'VMS_NET_DEFAULT',
        'VMS_STORAGE_DEFAULT',
        'MON_ZABBIX_HTTP_USERNAME',
        'MON_ZABBIX_HTTP_PASSWORD',
        'MON_ZABBIX_HOST_VM_PROXY',
        'DNS_SOA_DEFAULT',
        'EMAIL_HOST_USER',
        'EMAIL_HOST_PASSWORD',
        'SMS_SMSAPI_USERNAME',
        'SMS_SMSAPI_PASSWORD',
    })
    _null_fields_ = frozenset({
        'VMS_VM_SNAPSHOT_DEFINE_LIMIT',
        'VMS_VM_SNAPSHOT_LIMIT_AUTO',
        'VMS_VM_SNAPSHOT_LIMIT_MANUAL',
        'VMS_VM_SNAPSHOT_LIMIT_MANUAL_DEFAULT',
        'VMS_VM_SNAPSHOT_SIZE_LIMIT',
        'VMS_VM_SNAPSHOT_SIZE_LIMIT_DEFAULT',
        'VMS_VM_SNAPSHOT_DC_SIZE_LIMIT',
        'VMS_VM_BACKUP_DEFINE_LIMIT',
        'VMS_VM_BACKUP_LIMIT',
        'VMS_VM_BACKUP_DC_SIZE_LIMIT',
        'VMS_NET_LIMIT',
        'VMS_IMAGE_LIMIT',
        'VMS_ISO_LIMIT'
    })

    dc = s.CharField(label=_('Datacenter'), read_only=True)

    # Modules
    VMS_VM_SNAPSHOT_ENABLED = s.BooleanField(label=_('Snapshots'))
    VMS_VM_BACKUP_ENABLED = s.BooleanField(label=_('Backups'))
    MON_ZABBIX_ENABLED = s.BooleanField(label=_('Monitoring'))
    SUPPORT_ENABLED = s.BooleanField(label=_('Support'))
    REGISTRATION_ENABLED = s.BooleanField(label=_('Registration'))
    FAQ_ENABLED = s.BooleanField(label=_('FAQ'))  # Not part of MODULES (can be overridden even if disabled in settings)

    # Advanced settings
    VMS_VM_DOMAIN_DEFAULT = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._/-]*$', label='VMS_VM_DOMAIN_DEFAULT',
                                         max_length=255, min_length=3,
                                         help_text=_('Default domain part of the hostname of a newly '
                                                     'created virtual server.'))

    COMPANY_NAME = s.CharField(label='COMPANY_NAME', max_length=255,
                               help_text=_('Name of the company using this virtual datacenter.'))
    SITE_NAME = s.CharField(label='SITE_NAME', max_length=255,
                            help_text=_('Name of this site used mostly in email and text message templates.'))
    SITE_LINK = s.CharField(label='SITE_LINK', max_length=255,
                            help_text=_('Link to this site used mostly in email and text message templates.'))
    SITE_SIGNATURE = s.CharField(label='SITE_SIGNATURE', max_length=255,
                                 help_text=_('Signature attached to outgoing emails related '
                                             'to this virtual datacenter.'))
    SITE_LOGO = s.URLField(label='SITE_LOGO', max_length=2048, required=False,
                           help_text=_('URL pointing to an image, which will be displayed as a logo on the main page. '
                                       'If empty the default Danube Cloud logo will be used.'))
    SITE_ICON = s.URLField(label='SITE_ICON', max_length=2048, required=False,
                           help_text=_('URL pointing to an image, which will be displayed as an icon in the navigation '
                                       'bar. If empty the default Danube Cloud icon will be used.'))
    SUPPORT_EMAIL = s.EmailField(label='SUPPORT_EMAIL', max_length=255,
                                 help_text=_('Destination email address used for all support tickets '
                                             'related to this virtual datacenter.'))
    SUPPORT_PHONE = s.CharField(label='SUPPORT_PHONE', max_length=255, required=False,
                                help_text=_('Phone number displayed in the support contact details.'))
    SUPPORT_USER_CONFIRMATION = s.BooleanField(label='SUPPORT_USER_CONFIRMATION',
                                               help_text=_('Whether to send a confirmation email to the user after '
                                                           'a support ticket has been sent to SUPPORT_EMAIL.'))
    DEFAULT_FROM_EMAIL = s.EmailField(label='DEFAULT_FROM_EMAIL', max_length=255,
                                      help_text=_('Email address used as the "From" address for all outgoing emails '
                                                  'related to this virtual datacenter.'))
    EMAIL_ENABLED = s.BooleanField(label='EMAIL_ENABLED',
                                   help_text=_('Whether to completely disable sending of emails '
                                               'related to this virtual datacenter.'))
    API_LOG_USER_CALLBACK = s.BooleanField(label='API_LOG_USER_CALLBACK',
                                           help_text=_('Whether to log API user callback requests into the tasklog.'))

    VMS_ZONE_ENABLED = s.BooleanField(label='VMS_ZONE_ENABLED',  # Module
                                      help_text=_('Whether to enable support for SunOS zones in '
                                                  'this virtual datacenter.'))
    VMS_VM_OSTYPE_DEFAULT = s.IntegerChoiceField(label='VMS_VM_OSTYPE_DEFAULT', choices=Vm.OSTYPE,
                                                 help_text=_('Default operating system type. One of: 1 - Linux VM, '
                                                             '2 - SunOS VM, 3 - BSD VM, 4 - Windows VM, '
                                                             '5 - SunOS Zone, 6 - Linux Zone.'))
    VMS_VM_MONITORED_DEFAULT = s.BooleanField(label='VMS_VM_MONITORED_DEFAULT',
                                              help_text=_('Controls whether server synchronization with the monitoring '
                                                          'system is enabled by default.'))
    VMS_VM_CPU_SHARES_DEFAULT = s.IntegerField(label='VMS_VM_CPU_SHARES_DEFAULT', min_value=0, max_value=1048576,
                                               help_text=_("Default value of the server's CPU shares, "
                                                           "relative to other servers."))
    VMS_VM_ZFS_IO_PRIORITY_DEFAULT = s.IntegerField(label='VMS_VM_ZFS_IO_PRIORITY_DEFAULT', min_value=0, max_value=1024,
                                                    help_text=_("Default value of the server's IO throttling "
                                                                "priority, relative to other servers."))
    VMS_VM_RESOLVERS_DEFAULT = s.IPAddressArrayField(label='VMS_VM_RESOLVERS_DEFAULT', max_items=8,
                                                     help_text=_('Default DNS resolvers used for newly '
                                                                 'created servers.'))
    VMS_VM_SSH_KEYS_DEFAULT = s.ArrayField(label='VMS_VM_SSH_KEYS_DEFAULT', max_items=32, required=False,
                                           help_text=_('List of public SSH keys added to every virtual machine '
                                                       'in this virtual datacenter.'))
    VMS_VM_MDATA_DEFAULT = s.MetadataField(label='VMS_VM_MDATA_DEFAULT', max_items=32, required=False,
                                           validators=(validate_mdata(Vm.RESERVED_MDATA_KEYS),),
                                           help_text=_('Default VM metadata (key=value string pairs).'))
    VMS_DISK_MODEL_DEFAULT = s.ChoiceField(label='VMS_DISK_MODEL_DEFAULT', choices=Vm.DISK_MODEL,
                                           help_text=_('Default disk model of newly created server disks. One of: '
                                                       'virtio, ide, scsi.'))
    VMS_DISK_COMPRESSION_DEFAULT = s.ChoiceField(label='VMS_DISK_COMPRESSION_DEFAULT', choices=Vm.DISK_COMPRESSION,
                                                 help_text=_('Default disk compression algorithm. '
                                                             'One of: off, lzjb, gzip, gzip-N, zle, lz4.'))
    VMS_DISK_IMAGE_DEFAULT = s.CharField(label='VMS_DISK_IMAGE_DEFAULT', max_length=64, required=False,
                                         help_text=_('Name of the default disk image used for '
                                                     'newly created server disks.'))
    VMS_DISK_IMAGE_ZONE_DEFAULT = s.CharField(label='VMS_DISK_IMAGE_ZONE_DEFAULT', max_length=64, required=False,
                                              help_text=_('Name of the default disk image used for '
                                                          'newly created SunOS zone servers.'))
    VMS_NIC_MODEL_DEFAULT = s.ChoiceField(label='VMS_NIC_MODEL_DEFAULT', choices=Vm.NIC_MODEL,
                                          help_text=_('Default virtual NIC model of newly created server NICs. '
                                                      'One of: virtio, e1000, rtl8139.'))
    VMS_NIC_MONITORING_DEFAULT = s.IntegerField(label='VMS_NIC_MONITORING_DEFAULT', min_value=1, max_value=8,
                                                help_text=_('Default NIC ID, which will be used for '
                                                            'external monitoring.'))
    VMS_NET_DEFAULT = s.CharField(label='VMS_NET_DEFAULT', max_length=64, required=False,
                                  help_text=_('Name of the default network used for newly created server NICs.'))
    VMS_NET_LIMIT = s.IntegerField(label='VMS_NET_LIMIT', required=False,
                                   help_text=_('Maximum number of DC-bound networks that can be created in '
                                               'this virtual datacenter.'))
    VMS_NET_VLAN_RESTRICT = s.BooleanField(label='VMS_NET_VLAN_RESTRICT',
                                           help_text=_('Whether to restrict VLAN IDs to the '
                                                       'VMS_NET_VLAN_ALLOWED list.'))
    VMS_NET_VLAN_ALLOWED = s.IntegerArrayField(label='VMS_NET_VLAN_ALLOWED', required=False,
                                               help_text=_('List of VLAN IDs available for newly created DC-bound '
                                                           'networks in this virtual datacenter.'))
    VMS_IMAGE_LIMIT = s.IntegerField(label='VMS_IMAGE_LIMIT', required=False,
                                     help_text=_('Maximum number of DC-bound server images that can be created in '
                                                 'this virtual datacenter.'))
    VMS_ISO_LIMIT = s.IntegerField(label='VMS_ISO_LIMIT', required=False,
                                   help_text=_('Maximum number of DC-bound ISO images that can be created in '
                                               'this virtual datacenter.'))
    VMS_STORAGE_DEFAULT = s.CharField(label='VMS_STORAGE_DEFAULT', max_length=64, required=False,
                                      help_text=_('Name of the default storage used for newly created servers '
                                                  'and server disks.'))
    VMS_VGA_MODEL_DEFAULT = s.ChoiceField(label='VMS_VGA_MODEL_DEFAULT', choices=Vm.VGA_MODEL,
                                          help_text=_('Default VGA emulation driver of newly created servers. '
                                                      'One of: std, cirrus, vmware.'))

    VMS_VM_SNAPSHOT_DEFINE_LIMIT = s.IntegerField(label='VMS_VM_SNAPSHOT_DEFINE_LIMIT', required=False,
                                                  help_text=_('Maximum number of snapshot definitions per server.'))
    VMS_VM_SNAPSHOT_LIMIT_AUTO = s.IntegerField(label='VMS_VM_SNAPSHOT_LIMIT_AUTO', required=False,
                                                help_text=_('Maximum number of automatic snapshots per server.'))
    VMS_VM_SNAPSHOT_LIMIT_MANUAL = s.IntegerField(label='VMS_VM_SNAPSHOT_LIMIT_MANUAL', required=False,
                                                  help_text=_('Maximum number of manual snapshots per server.'))
    VMS_VM_SNAPSHOT_LIMIT_MANUAL_DEFAULT = s.IntegerField(label='VMS_VM_SNAPSHOT_LIMIT_MANUAL_DEFAULT', required=False,
                                                          help_text=_('Predefined manual snapshot limit '
                                                                      'for new servers.'))
    VMS_VM_SNAPSHOT_SIZE_LIMIT = s.IntegerField(label='VMS_VM_SNAPSHOT_SIZE_LIMIT', required=False,
                                                help_text=_('Maximum size of all snapshots per server.'))
    VMS_VM_SNAPSHOT_SIZE_LIMIT_DEFAULT = s.IntegerField(label='VMS_VM_SNAPSHOT_SIZE_LIMIT_DEFAULT', required=False,
                                                        help_text=_('Predefined snapshot size limit for new servers.'))
    VMS_VM_SNAPSHOT_DC_SIZE_LIMIT = s.IntegerField(label='VMS_VM_SNAPSHOT_DC_SIZE_LIMIT', required=False,
                                                   help_text=_('Maximum size of all snapshots in this '
                                                               'virtual datacenter.'))
    VMS_VM_BACKUP_DEFINE_LIMIT = s.IntegerField(label='VMS_VM_BACKUP_DEFINE_LIMIT', required=False,
                                                help_text=_('Maximum number of backup definitions per server.'))
    VMS_VM_BACKUP_LIMIT = s.IntegerField(label='VMS_VM_BACKUP_LIMIT', required=False,
                                         help_text=_('Upper retention limit used for new backup definitions.'))
    VMS_VM_BACKUP_DC_SIZE_LIMIT = s.IntegerField(label='VMS_VM_BACKUP_DC_SIZE_LIMIT', required=False,
                                                 help_text=_('Maximum size of all backups in this virtual datacenter.'))
    VMS_VM_BACKUP_COMPRESSION_DEFAULT = s.ChoiceField(label='VMS_VM_BACKUP_COMPRESSION_DEFAULT',
                                                      choices=BackupDefine.COMPRESSION,
                                                      help_text=_('Predefined compression algorithm for '
                                                                  'new file backups.'))

    DNS_PTR_DEFAULT = s.CharField(label='DNS_PTR_DEFAULT', max_length=255, min_length=4,
                                  help_text=_("Default value used for reverse DNS records of virtual server "
                                              "NIC's IP addresses. Available placeholders are: "
                                              "{ipaddr}, {hostname}, {alias}."))

    MON_ZABBIX_SERVER = s.RegexField(r'^https?://.*$', label='MON_ZABBIX_SERVER', max_length=1024,
                                     help_text=_('URL address of Zabbix server used for external monitoring of servers '
                                                 'in this virtual datacenter. WARNING: Changing this and other '
                                                 'MON_ZABBIX_* values in default virtual datacenter will '
                                                 'affect the built-in internal monitoring of servers and '
                                                 'compute nodes.'))
    MON_ZABBIX_SERVER_SSL_VERIFY = s.BooleanField(label='MON_ZABBIX_SERVER_SSL_VERIFY',
                                                  help_text=_('Whether to perform HTTPS certificate verification when '
                                                              'connecting to the Zabbix API.'))
    MON_ZABBIX_TIMEOUT = s.IntegerField(label='MON_ZABBIX_TIMEOUT', min_value=1, max_value=180,
                                        help_text=_('Timeout in seconds used for connections to the Zabbix API.'))
    MON_ZABBIX_USERNAME = s.CharField(label='MON_ZABBIX_USERNAME', max_length=255,
                                      help_text=_('Username used for connecting to the Zabbix API.'))
    MON_ZABBIX_PASSWORD = s.CharField(label='MON_ZABBIX_PASSWORD', max_length=255,
                                      help_text=_('Password used for connecting to the Zabbix API.'))
    MON_ZABBIX_HTTP_USERNAME = s.CharField(label='MON_ZABBIX_HTTP_USERNAME', max_length=255, required=False,
                                           help_text=_('Username used for the HTTP basic authentication required for '
                                                       'connections to the Zabbix API.'))
    MON_ZABBIX_HTTP_PASSWORD = s.CharField(label='MON_ZABBIX_HTTP_PASSWORD', max_length=255, required=False,
                                           help_text=_('Password used for the HTTP basic authentication required for '
                                                       'connections to the Zabbix API.'))

    MON_ZABBIX_VM_SLA = s.BooleanField(label='MON_ZABBIX_VM_SLA',
                                       help_text=_('Whether to fetch and display the SLA value of virtual servers.'))
    MON_ZABBIX_VM_SYNC = s.BooleanField(label='MON_ZABBIX_VM_SYNC',
                                        help_text=_('Whether newly created virtual servers can be automatically '
                                                    'synchronized with the monitoring server.'))
    MON_ZABBIX_HOSTGROUP_VM = s.SafeCharField(label='MON_ZABBIX_HOSTGROUP_VM', max_length=255,
                                              help_text=_('Existing Zabbix host group, which will be used for all '
                                                          'monitored servers in this virtual datacenter.'))
    MON_ZABBIX_HOSTGROUPS_VM = s.ArrayField(label='MON_ZABBIX_HOSTGROUPS_VM', max_items=32, required=False,
                                            help_text=_('List of other existing Zabbix host groups, which will be used '
                                                        'for all monitored servers in this virtual datacenter. '
                                                        'Available placeholders are: {ostype}, {ostype_text}, '
                                                        '{disk_image}, {disk_image_abbr}, {dc_name}.'))
    MON_ZABBIX_HOSTGROUPS_VM_RESTRICT = s.BooleanField(label='MON_ZABBIX_HOSTGROUPS_VM_RESTRICT',
                                                       help_text=_('Whether to restrict Zabbix host group names to the '
                                                                   'MON_ZABBIX_HOSTGROUPS_VM_ALLOWED list.'))
    MON_ZABBIX_HOSTGROUPS_VM_ALLOWED = s.ArrayField(label='MON_ZABBIX_HOSTGROUPS_VM_ALLOWED', max_items=32,
                                                    required=False,
                                                    help_text=_('List of Zabbix host groups that can be used by servers'
                                                                ' in this virtual datacenter. Available placeholders'
                                                                ' are: {ostype}, {ostype_text}, {disk_image},'
                                                                ' {disk_image_abbr}, {dc_name}.'))
    MON_ZABBIX_TEMPLATES_VM = s.ArrayField(label='MON_ZABBIX_TEMPLATES_VM', max_items=128, required=False,
                                           help_text=_('List of existing Zabbix templates, which will be used for all '
                                                       'monitored servers in this virtual datacenter. '
                                                       'Available placeholders are: {ostype}, {ostype_text}, '
                                                       '{disk_image}, {disk_image_abbr}, {dc_name}.'))
    MON_ZABBIX_TEMPLATES_VM_MAP_TO_TAGS = s.BooleanField(label='MON_ZABBIX_TEMPLATES_VM_MAP_TO_TAGS',
                                                         help_text=_('Whether to find and use existing Zabbix templates'
                                                                     ' according to tags of a monitored '
                                                                     'virtual server.'))
    MON_ZABBIX_TEMPLATES_VM_RESTRICT = s.BooleanField(label='MON_ZABBIX_TEMPLATES_VM_RESTRICT',
                                                      help_text=_('Whether to restrict Zabbix template names to the '
                                                                  'MON_ZABBIX_TEMPLATES_VM_ALLOWED list.'))
    MON_ZABBIX_TEMPLATES_VM_ALLOWED = s.ArrayField(label='MON_ZABBIX_TEMPLATES_VM_ALLOWED', max_items=128,
                                                   required=False,
                                                   help_text=_('List of Zabbix templates that can be used by servers '
                                                               'in this virtual datacenter. Available placeholders are:'
                                                               ' {ostype}, {ostype_text}, {disk_image},'
                                                               ' {disk_image_abbr}, {dc_name}.'))
    MON_ZABBIX_TEMPLATES_VM_NIC = s.ArrayField(label='MON_ZABBIX_TEMPLATES_VM_NIC', max_items=16, required=False,
                                               help_text=_('List of Zabbix templates that will be used for all '
                                                           'monitored servers, for every virtual NIC of a server. '
                                                           'Available placeholders are: {net}, {nic_id} + '
                                                           'MON_ZABBIX_TEMPLATES_VM placeholders.'))
    MON_ZABBIX_TEMPLATES_VM_DISK = s.ArrayField(label='MON_ZABBIX_TEMPLATES_VM_DISK', max_items=16, required=False,
                                                help_text=_('List of Zabbix templates that will be used for all '
                                                            'monitored servers, for every virtual disk of a server. '
                                                            'Available placeholders: {disk}, {disk_id} + '
                                                            'MON_ZABBIX_TEMPLATES_VM placeholders.'))
    MON_ZABBIX_HOST_VM_PROXY = s.CharField(label='MON_ZABBIX_HOST_VM_PROXY', min_length=1, max_length=128,
                                           required=False,
                                           help_text=_('Name or ID of the monitoring proxy, which will be used to '
                                                       'monitor all monitored virtual servers.'))

    def __init__(self, request, dc, *args, **kwargs):
        global_settings = self.get_global_settings()

        if global_settings and not dc.is_default():  # Displaying global settings for non default DC
            dc1_settings = DefaultDc().settings      # These setting should be read-only and read from default DC
            dc_settings = DefAttrDict(dc.custom_settings, defaults=dc1_settings)  # instance
        else:
            dc1_settings = None
            dc_settings = dc.settings  # instance

        self.dc_settings = dc_settings
        dc_settings['dc'] = dc.name
        super(DcSettingsSerializer, self).__init__(request, dc_settings, *args, **kwargs)
        self._update_fields_ = self.fields.keys()
        self._update_fields_.remove('dc')
        self.settings = {}
        self.dc = dc

        if dc1_settings is not None:
            for i in global_settings:
                self.fields[i].read_only = True

    @classmethod
    def get_global_settings(cls):
        if cls._global_settings is None:
            # noinspection PyUnresolvedReferences
            cls._global_settings = frozenset(set(cls.base_fields.keys()) - set(DcSettingsSerializer.base_fields.keys()))
        return cls._global_settings

    @staticmethod
    def _filter_sensitive_data(dictionary):
        """Replace sensitive data in input dict with ***"""
        for key in dictionary.keys():
            if any([i in key for i in SENSITIVE_FIELD_NAMES]):
                dictionary[key] = SENSITIVE_FIELD_VALUE
        return dictionary

    def _setattr(self, instance, source, value):
        # noinspection PyProtectedMember
        super(DcSettingsSerializer, self)._setattr(instance, source, value)
        self.settings[source] = value

    def detail_dict(self, **kwargs):
        # Remove sensitive data from detail dict
        return self._filter_sensitive_data(super(DcSettingsSerializer, self).detail_dict(**kwargs))

    @property
    def data(self):
        if self._data is None:
            # Remove sensitive data from output
            self._data = self._filter_sensitive_data(super(DcSettingsSerializer, self).data)
        return self._data

    # noinspection PyPep8Naming
    def validate_VMS_VM_DOMAIN_DEFAULT(self, attrs, source):
        if self.dc_settings.DNS_ENABLED:
            try:
                value = attrs[source]
            except KeyError:
                pass
            else:
                try:
                    domain = Domain.objects.get(name=value)
                except Domain.DoesNotExist:
                    raise s.ValidationError(_('Object with name=%s does not exist.') % value)
                else:
                    if not self.dc.domaindc_set.filter(domain_id=domain.id).exists():
                        raise s.ValidationError(_('Domain is not available in this datacenter.'))

        return attrs

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_VMS_VM_SSH_KEYS_DEFAULT(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            for key in value:
                validate_ssh_key(key)

        return attrs

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_DNS_PTR_DEFAULT(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            testvalue = placeholder_validator(value, ipaddr='test', hostname='test', alias='test')
            RegexValidator(r'^[a-z0-9][a-z0-9\.-]+[a-z0-9]$')(testvalue)

        return attrs

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_MON_ZABBIX_HOSTGROUPS_VM(self, attrs, source):
        return validate_array_placeholders(attrs, source, VM_KWARGS)

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_MON_ZABBIX_HOSTGROUPS_VM_ALLOWED(self, attrs, source):
        return validate_array_placeholders(attrs, source, VM_KWARGS)

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_MON_ZABBIX_TEMPLATES_VM(self, attrs, source):
        return validate_array_placeholders(attrs, source, VM_KWARGS)

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_MON_ZABBIX_TEMPLATES_VM_ALLOWED(self, attrs, source):
        return validate_array_placeholders(attrs, source, VM_KWARGS)

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_MON_ZABBIX_TEMPLATES_VM_NIC(self, attrs, source):
        return validate_array_placeholders(attrs, source, VM_KWARGS.copy().update({'net': 1, 'nic_id': 2}))

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_MON_ZABBIX_TEMPLATES_VM_DISK(self, attrs, source):
        return validate_array_placeholders(attrs, source, VM_KWARGS.copy().update({'disk': 1, 'disk_id': 2}))

    def validate(self, attrs):
        # Check if it is possible to override a boolean setting
        for source, value in attrs.items():
            if source in self._override_disabled_ and not getattr(settings, source, False) and value:
                self._errors[source] = s.ErrorList([_('Cannot override global setting.')])
                del attrs[source]

        return attrs


@third_party_apps_default_dc_modules_and_settings
class DefaultDcSettingsSerializer(DcSettingsSerializer):
    """
    vms.models.DefaultDc.settings
    """
    _global_settings = None
    default_dc_third_party_modules = []  # Class level storage, updated only with the decorator function
    default_dc_third_party_settings = []  # Class level storage, updated only with the decorator function

    ACL_ENABLED = s.BooleanField(label=_('Advanced User Management'))  # Global Module
    API_ENABLED = s.BooleanField(label=_('API access'))  # Global Module
    VMS_DC_ENABLED = s.BooleanField(label=_('Virtual Datacenters'))  # Global Module
    SMS_ENABLED = s.BooleanField(label=_('SMS'))  # Global Module

    VMS_NODE_SSH_KEYS_SYNC = s.BooleanField(label='VMS_NODE_SSH_KEYS_SYNC',
                                            help_text=_('WARNING: Do not disable this unless '
                                                        'you know what you are doing!'))
    VMS_NODE_SSH_KEYS_DEFAULT = s.ArrayField(label='VMS_NODE_SSH_KEYS_DEFAULT',
                                             help_text=_('List of SSH keys to be added to compute nodes by default'))

    VMS_NET_NIC_TAGS = s.ArrayField(label='VMS_NET_NIC_TAGS', min_items=1, max_items=24,
                                    help_text=_('List of aliases of network devices configured on compute nodes.'))

    VMS_IMAGE_REPOSITORIES = s.URLDictField(label='VMS_IMAGE_REPOSITORIES', required=False, max_items=16,
                                            help_text=_('Object (key=name, value=URL) with remote disk image '
                                                        'repositories available in every virtual datacenter.'))

    DNS_HOSTMASTER = s.EmailField(label='DNS_HOSTMASTER', max_length=255,
                                  help_text=_('Default hostmaster email address used for SOA records '
                                              'of newly created domains.'))
    DNS_NAMESERVERS = s.ArrayField(label='DNS_NAMESERVERS', max_items=8,
                                   help_text=_('List of DNS servers used for NS records of newly created domains.'
                                               ' Set to an empty list to disable automatic creation of NS records.'))
    DNS_SOA_DEFAULT = s.CharField(label='DNS_SOA_DEFAULT', max_length=255, min_length=0, required=False,
                                  help_text=_('Default value for the SOA record of newly created domains. '
                                              'Available placeholders are: '
                                              '{nameserver} (replaced by first nameserver in DNS_NAMESERVERS) and '
                                              '{hostmaster} (replaced by DNS_HOSTMASTER). '
                                              'Set to an empty value to disable automatic creation of SOA records.'))

    EMAIL_HOST = s.SafeCharField(label='EMAIL_HOST',
                                 help_text=_('Hostname or IP address of the SMTP server used for all outgoing emails.'))
    EMAIL_PORT = s.IntegerField(label='EMAIL_PORT', min_value=1, max_value=65535,
                                help_text=_('Port of the SMTP server.'))
    EMAIL_USE_TLS = s.BooleanField(label='EMAIL_USE_TLS',
                                   help_text=_('Whether to use an explicit TLS (secure) SMTP connection (STARTTLS).'))
    EMAIL_USE_SSL = s.BooleanField(label='EMAIL_USE_SSL',
                                   help_text=_('Whether to use an implicit TLS (secure) SMTP connection.'))
    EMAIL_HOST_USER = s.CharField(label='EMAIL_HOST_USER', max_length=255, required=False,
                                  help_text=_('Username for SMTP authentication.'))
    EMAIL_HOST_PASSWORD = s.CharField(label='EMAIL_HOST_PASSWORD', max_length=255, required=False,
                                      help_text=_('Password for SMTP authentication.'))
    SHADOW_EMAIL = s.EmailField(label='SHADOW_EMAIL', required=False,
                                help_text=_('Email address to which hidden copies of all outgoing emails are sent.'))

    PROFILE_SSH_KEY_LIMIT = s.IntegerField(label='PROFILE_SSH_KEY_LIMIT', max_value=64,
                                           help_text=_('Maximum number of public SSH keys '
                                                       'that can be stored in one user profile.'))
    PROFILE_COUNTRY_CODE_DEFAULT = s.ChoiceField(label='PROFILE_COUNTRY_CODE_DEFAULT', choices=UserProfile.COUNTRIES,
                                                 help_text=_("Default country in user's profile."))
    PROFILE_PHONE_PREFIX_DEFAULT = s.ChoiceField(label='PROFILE_PHONE_PREFIX_DEFAULT',
                                                 choices=UserProfile.PHONE_PREFIXES,
                                                 help_text=_("Default country phone prefix in user's profile."))
    PROFILE_TIME_ZONE_DEFAULT = s.ChoiceField(label='PROFILE_TIME_ZONE_DEFAULT', choices=UserProfile.TIMEZONES,
                                              help_text=_("Default time zone in user's profile."))

    MON_ZABBIX_NODE_SYNC = s.BooleanField(label='MON_ZABBIX_NODE_SYNC',
                                          help_text=_('Whether compute nodes should be automatically '
                                                      'synchronized with the monitoring server.'))
    MON_ZABBIX_NODE_SLA = s.BooleanField(label='MON_ZABBIX_NODE_SLA',
                                         help_text=_('Whether to fetch and display the SLA value of compute nodes.'))
    MON_ZABBIX_HOSTGROUP_NODE = s.SafeCharField(label='MON_ZABBIX_HOSTGROUP_NODE', max_length=255,
                                                help_text=_('Existing Zabbix host group, which will be used for all '
                                                            'monitored compute nodes.'))
    MON_ZABBIX_HOSTGROUPS_NODE = s.ArrayField(label='MON_ZABBIX_HOSTGROUPS_NODE', max_items=32, required=False,
                                              help_text=_('List of other existing Zabbix host groups, which will be '
                                                          'used for all monitored compute nodes.'))
    MON_ZABBIX_TEMPLATES_NODE = s.ArrayField(label='MON_ZABBIX_TEMPLATES_NODE', max_items=128, required=False,
                                             help_text=_('List of existing Zabbix templates, which will be used for all'
                                                         ' monitored compute nodes.'))

    SMS_PREFERRED_SERVICE = s.ChoiceField(label='SMS_PREFERRED_SERVICE', choices=get_services(),
                                          help_text=_('Currently used SMS provider.'))
    SMS_PRIVATE_KEY = s.CharField(label='SMS_PRIVATE_KEY', max_length=255,
                                  help_text=_('Secure key required for sending text messages via the API.'))
    SMS_SMSAPI_USERNAME = s.CharField(label='SMS_SMSAPI_USERNAME', max_length=255, required=False,
                                      help_text=_('Username required for the SMSAPI service (former HQSMS).'))
    SMS_SMSAPI_PASSWORD = s.CharField(label='SMS_SMSAPI_PASSWORD', max_length=255, required=False,
                                      help_text=_('Password required for the SMSAPI service (former HQSMS).'))
    SMS_SMSAPI_FROM = s.SafeCharField(label='SMS_SMSAPI_FROM', max_length=64,
                                      help_text=_('Phone number used for outgoing text messages sent via the '
                                                  'SMSAPI service (former HQSMS).'))

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_VMS_NODE_SSH_KEYS_DEFAULT(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            for key in value:
                validate_ssh_key(key)

        return attrs

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_VMS_NET_NIC_TAGS(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            new_nic_tags = set(value)
            used_nic_tags = set(Subnet.objects.all().values_list('nic_tag', flat=True).distinct())

            if not used_nic_tags.issubset(new_nic_tags):
                raise s.ValidationError(_('Cannot remove used NIC tags.'))

        return attrs

    # noinspection PyMethodMayBeStatic,PyPep8Naming
    def validate_DNS_SOA_DEFAULT(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            return attrs

        if not value:
            attrs[source] = ''
            return attrs

        testvalue = placeholder_validator(value, nameserver='ns01.example.com', hostmaster='hostmaster.example.com')
        # {nameserver} {hostmaster} 2013010100 28800 7200 604800 86400
        RegexValidator(r'^([A-Za-z0-9\._/-]+)\s+([A-Za-z0-9\._-]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$')(testvalue)

        return attrs

    def validate(self, attrs):
        if attrs.get('EMAIL_USE_TLS', None) and attrs.get('EMAIL_USE_SSL', None):
            self._errors['EMAIL_USE_TLS'] = self._errors['EMAIL_USE_SSL'] = s.ErrorList([
                _('Cannot enable EMAIL_USE_TLS and EMAIL_USE_SSL together.')
            ])

        return attrs
