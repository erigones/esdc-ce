import re
import struct
import base64
# noinspection PyCompatibility
import ipaddress

from django.core import validators
from django.core.exceptions import ValidationError
from django.utils import six
from django.utils.translation import ugettext_lazy as _

from gui.models import UserSSHKey

SSH_KEY_TYPES = (
    'ssh-rsa',
    'ssh-dss',
    'ecdsa-sha2-nistp256',
    'ecdsa-sha2-nistp384',
    'ecdsa-sha2-nistp521',
    'ssh-ed25519'
)
RE_PEM_KEY_BEGIN = re.compile(r'^-----BEGIN( | \w+ )PRIVATE KEY-----', re.MULTILINE)
RE_PEM_KEY_END = re.compile(r'^-----END( | \w+ )PRIVATE KEY-----', re.MULTILINE)
RE_PEM_CRT_BEGIN = re.compile(r'^-----BEGIN CERTIFICATE-----', re.MULTILINE)
RE_PEM_CRT_END = re.compile(r'^-----END CERTIFICATE-----', re.MULTILINE)
RE_PLACEHOLDER = re.compile(r'{(.*?)}+', re.MULTILINE)


def validate_owner(obj, new_owner, model_name):
    if obj and new_owner and obj.pk and obj.owner != new_owner:
        if obj.tasks:
            raise ValidationError(_('%(model)s has pending tasks.') % {'model': model_name})


def validate_alias(obj, value, field_comparison='alias__iexact'):
    qs = obj.__class__.objects

    if obj.pk:
        if obj.alias == value:
            return value
        else:
            qs = qs.exclude(pk=obj.pk)

    if qs.filter(**{field_comparison: value}).exists():
        raise ValidationError(_('This alias is already in use. Please supply a different alias.'))

    return value


def validate_mdata(reserved_keys):
    # Bug #chili-721
    def mdata_validator(value):
        if value:
            invalid_keys = reserved_keys.intersection(value.keys())

            if invalid_keys:
                raise ValidationError(_('Invalid key name(s) (%(invalid_keys)s).') % {'invalid_keys': invalid_keys})

    return mdata_validator


def validate_ssh_key(value):
    key = value.split(' ')

    if not (1 < len(key) and key[0] in SSH_KEY_TYPES):
        raise ValidationError(_('Unknown SSH public key type.'))

    if '\n' in value:
        raise ValidationError(_('Invalid SSH public key format (newlines detected).'))

    try:
        data = base64.decodestring(key[1])
        int_len = 4
        str_len = struct.unpack('>I', data[:int_len])[0]

        if data[int_len:int_len + str_len] != key[0]:
            raise ValueError

        fingerprint = UserSSHKey.get_fingerprint(value)
    except Exception:
        raise ValidationError(_('Invalid SSH public key format.'))

    return fingerprint


def mod2_validator(num):
    if num % 2:
        raise ValidationError(_('Must be power of 2.'))


def mac_address_validator(value):
    mac = six.text_type(value).lower()
    for prefix in ('33:33', '00:00', '00:01', '00:02', '00:52:00', '00:52:01', '00:52:13'):
        if mac.startswith(prefix):
            raise ValidationError(_('Enter a valid MAC address.'))
    if mac == 'ff:ff:ff:ff:ff:ff':
        raise ValidationError(_('Enter a valid MAC address.'))


def cron_validator(value):
    """CRON expression validator"""
    if value.strip() != value:
        raise ValidationError(_('Leading nor trailing spaces are allowed.'))

    columns = value.split()
    if columns != value.split(' '):
        raise ValidationError(_('Use only a single space as a column separator.'))

    if len(columns) != 5:
        raise ValidationError(_('Entry has to consist of exactly 5 columns.'))

    cron_re = re.compile(r'^(\*|\d+(-\d+)?(,\d+(-\d+)?)*)(/\d+)?$')
    for i, c in enumerate(columns):
        if not cron_re.match(c):
            i += 1
            raise ValidationError(_('Incorrect value in %d. column.') % i)


def ip_validator(value):
    """Validate IPv4 address"""
    try:
        ip = ipaddress.ip_address(six.text_type(value))
        if ip.is_reserved:
            raise ValueError
    except ValueError:
        raise ValidationError(_('Enter a valid IPv4 address.'))


def cidr_validator(value, return_ip_interface=False):
    """Validate IPv4 + optional subnet in CIDR notation"""
    try:
        if '/' in value:
            ipaddr, netmask = value.split('/')
            netmask = int(netmask)
        else:
            ipaddr, netmask = value, 32

        if not validators.ipv4_re.match(ipaddr) or not 1 <= netmask <= 32:
            raise ValueError

        ipi = ipaddress.ip_interface(six.text_type(value))

        if ipi.is_reserved:
            raise ValueError

    except ValueError:
        raise ValidationError(_('Enter a valid IPv4 address or IPv4 network.'))

    if return_ip_interface:
        return ipi


def ip_or_nic_validator(value):
    """Validate IPv4 or nic[x]"""
    nic_re = re.compile(r'^nics\[\d+\]$')

    if not (validators.ipv4_re.match(value) or nic_re.match(value)):
        raise ValidationError(_('Enter a valid IPv4 address or NIC.'))


def validate_pem_cert(value):
    """Search for PEM certificate boundaries"""
    if not (RE_PEM_CRT_BEGIN.search(value) and RE_PEM_CRT_END.search(value)):
        raise ValidationError(_('Certificate is missing standard PEM header/footer.'))


def validate_pem_key(value):
    """Search for PEM private key boundaries"""
    if not (RE_PEM_KEY_BEGIN.search(value) and RE_PEM_KEY_END.search(value)):
        raise ValidationError(_('Private key is missing standard PEM header/footer.'))


def placeholder_validator(value, **valid_placeholders):
    """Helper for checking if the value has acceptable placeholders"""

    # findall placeholders in value parameter string and store them as set
    placeholders = set(RE_PLACEHOLDER.findall(value))

    # check if placeholders is non-empty and if elements are subset of keys in valid_placeholders
    if not placeholders.issubset(valid_placeholders.keys()):
        raise ValidationError(_('Invalid placeholders.'))

    try:
        return value.format(**valid_placeholders)
    except (KeyError, ValueError, TypeError, IndexError):
        raise ValidationError(_('Invalid placeholders.'))
