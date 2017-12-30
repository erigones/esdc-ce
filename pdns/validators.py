import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv4_address, validate_ipv6_address, MaxLengthValidator
from django.utils.translation import ugettext_lazy as _

from pdns.models import Record

re_record_name_valid_chars = re.compile(r'^((([a-z\d_])|(\*\.))(-*[a-z\d_/])*)(\.([a-z\d_](-*[a-z\d/])*))*$',
                                        re.IGNORECASE)
re_record_name_valid_labels = re.compile(r'^[^.]{1,63}(\.[^.]{1,63})*$', re.IGNORECASE)
re_fqdn_parts = re.compile(r'^(?![-/])[a-z\d/-]{1,63}(?<![-/])$', re.IGNORECASE)
err_field_required = _('This field is required.')


class RecordValidationError(ValidationError):
    """
    Exception raised for invalid DNS records.
    """
    attr = None

    def __init__(self, message):
        super(RecordValidationError, self).__init__({self.attr: [message]})


class RecordNameValidationError(RecordValidationError):
    attr = 'name'


class RecordContentValidationError(RecordValidationError):
    attr = 'content'


def is_valid_fqdn(value):
    """Validate hostname"""
    if not value or len(value) > 255:
        return False

    if value[-1] == '.':
        value = value[:-1]

    return all(re_fqdn_parts.match(i) for i in value.split('.'))


def validate_dns_name(value):
    """Validate DNS domain/record name"""
    if not re_record_name_valid_chars.match(value):
        raise RecordNameValidationError(_('Invalid characters detected. Enter a valid DNS name.'))

    if not re_record_name_valid_labels.match(value):
        raise RecordNameValidationError(_('Invalid label detected. Enter a valid DNS name.'))


def validate_fqdn(value):
    if not is_valid_fqdn(value):
        raise RecordContentValidationError(_('Invalid fully qualified domain name.'))


class BaseRecordValidator(object):
    """
    DNS record validation base class.
    """
    check_name_suffix_against_domain = True

    def __init__(self, domain, name, content):
        if name:
            validate_dns_name(name)
        else:
            raise RecordNameValidationError(err_field_required)

        if self.check_name_suffix_against_domain:
            if name != domain.name and not name.endswith('.' + domain.name):
                raise RecordNameValidationError(_('Name does not end with domain name. Enter a valid DNS name.'))

        if content is None:
            content = ''

        self.domain = domain
        self.name = name
        self.content = content

    def __call__(self):
        pass


class ARecordValidator(BaseRecordValidator):
    def __call__(self):
        try:
            validate_ipv4_address(self.content)
        except ValidationError as exc:
            raise RecordContentValidationError(exc.message)


class AAAARecordValidator(BaseRecordValidator):
    def __call__(self):
        try:
            validate_ipv6_address(self.content)
        except ValidationError as exc:
            raise RecordContentValidationError(exc.message)


class CNAMERecordValidator(BaseRecordValidator):
    def __call__(self):
        validate_fqdn(self.content)


class MXRecordValidator(BaseRecordValidator):
    def __call__(self):
        validate_fqdn(self.content)


class NSRecordValidator(BaseRecordValidator):
    def __call__(self):
        validate_fqdn(self.content)


class TXTRecordValidator(BaseRecordValidator):
    def __call__(self):
        try:
            MaxLengthValidator(64000)(self.content)
        except ValidationError as exc:
            raise RecordContentValidationError(exc.message)


class PTRRecordValidator(BaseRecordValidator):
    def __call__(self):
        validate_fqdn(self.content)


class SRVRecordValidator(BaseRecordValidator):
    def __call__(self):
        # TODO: name = '_service._protocol.name.'
        # content = 'weight port target'
        content = self.content.strip().split(' ')

        if len(content) != 3:
            raise RecordContentValidationError(_('Invalid number of SRV fields.'))

        try:
            if not (0 < int(content[0]) < 65536):
                raise ValueError
        except ValueError:
            raise RecordContentValidationError(_('Invalid weight field.'))

        try:
            if not (0 < int(content[1]) < 65536):
                raise ValueError
        except ValueError:
            raise RecordContentValidationError(_('Invalid port field.'))

        if not is_valid_fqdn(content[2]):
            raise RecordContentValidationError(_('Invalid target field.'))


class SOARecordValidator(BaseRecordValidator):
    re_email_addr = re.compile(r'^[a-z0-9_][a-z0-9_.-]$', re.IGNORECASE)
    check_name_suffix_against_domain = False

    def __call__(self):
        if self.name != self.domain.name:
            raise RecordContentValidationError(_('Name has to be the same as domain name for a SOA record.'))

        # content = 'example.com. hostmaster.example.com. 1 7200 900 1209600 86400'
        content = self.content.strip().split(' ')

        if len(content) != 7:
            raise RecordContentValidationError(_('Invalid number of SOA fields.'))

        if not is_valid_fqdn(content[0]):
            raise RecordContentValidationError(_('Invalid name server field.'))

        if not is_valid_fqdn(content[1]):
            raise RecordContentValidationError(_('Invalid email address field.'))

        try:
            if not(0 <= int(content[2]) <= 4294967295):
                raise ValueError
        except ValueError:
            raise RecordContentValidationError(_('Invalid serial number field.'))

        interval_fields = content[3:]

        for i, field_name in enumerate(('refresh', 'retry', 'expiry', 'min-ttl')):
            try:
                if not(-2147483647 <= int(interval_fields[i]) <= 2147483647):
                    raise ValueError
            except ValueError:
                raise RecordContentValidationError(_('Invalid %(field_name)s field.') % {'field_name': field_name})


DNS_RECORD_VALIDATORS = {
    Record.A: ARecordValidator,
    Record.AAAA: AAAARecordValidator,
    Record.CNAME: CNAMERecordValidator,
    Record.MX: MXRecordValidator,
    Record.NS: NSRecordValidator,
    Record.TXT: TXTRecordValidator,
    Record.PTR: PTRRecordValidator,
    Record.SRV: SRVRecordValidator,
    Record.SOA: SOARecordValidator,
}


def get_dns_record_validator(record_type):
    return DNS_RECORD_VALIDATORS.get(record_type, BaseRecordValidator)


def run_record_validator(domain, record_type, record_name, record_content):
    validator_class = get_dns_record_validator(record_type)

    return validator_class(domain, record_name, record_content)()
