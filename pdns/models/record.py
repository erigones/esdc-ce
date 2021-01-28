import time
from datetime import datetime
from logging import getLogger
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.six import text_type
from dns import reversename, exception

from pdns.models.domain import Domain

logger = getLogger(__name__)


def epoch():
    return int(time.mktime(time.gmtime()))


class Record(models.Model):
    """
    This table contains the records for all the domains listed in the
    domains-table. The records are small entries for each subdomain, mailserver,
    nameserver or redirection you want to be made.

    CREATE TABLE records (
        id              SERIAL PRIMARY KEY,
        domain_id       INT DEFAULT NULL,
        name            VARCHAR(255) DEFAULT NULL,
        type            VARCHAR(10) DEFAULT NULL,
        content         VARCHAR(65535) DEFAULT NULL,
        ttl             INT DEFAULT NULL,
        prio            INT DEFAULT NULL,
        change_date     INT DEFAULT NULL,
        disabled        BOOL DEFAULT 'f',
        ordername       VARCHAR(255),
        auth            BOOL DEFAULT 't',

        CONSTRAINT domain_exists FOREIGN KEY(domain_id) REFERENCES domains(id) ON DELETE CASCADE, -- (custom SQL)
        CONSTRAINT c_lowercase_name CHECK (((name)::text = lower((name)::text))) -- (custom SQL)
    );
    CREATE INDEX rec_name_index ON records(name);  -- (by django)
    CREATE INDEX nametype_index ON records(name,type);  -- (by django)
    CREATE INDEX domain_id ON records(domain_id);  -- (by django)
    CREATE INDEX recordorder ON records (domain_id, ordername text_pattern_ops); -- (custom SQL)
    """

    # MAX value for SOA serial
    MAX_UINT32 = 4294967295  # 2**38 - 1

    # Defaults
    PRIO = 0
    TTL = 300

    # Record types
    A = 'A'
    AAAA = 'AAAA'
    CERT = 'CERT'
    CNAME = 'CNAME'
    HINFO = 'HINFO'
    KEY = 'KEY'
    LOC = 'LOC'
    MX = 'MX'
    NAPTR = 'NAPTR'
    NS = 'NS'
    PTR = 'PTR'
    RP = 'RP'
    SOA = 'SOA'
    SPF = 'SPF'
    SSHFP = 'SSHFP'
    SRV = 'SRV'
    TLSA = 'TLSA'
    TXT = 'TXT'

    TYPE = (
        (SOA, SOA),
        (NS, NS),
        (MX, MX),
        (A, A),
        (AAAA, AAAA),
        (CNAME, CNAME),
        (TXT, TXT),
        (PTR, PTR),
        (SRV, SRV),
        (SPF, SPF),
        (HINFO, HINFO),
        (NAPTR, NAPTR),
        (SSHFP, SSHFP),
        (RP, RP),
        (LOC, LOC),
        (KEY, KEY),
        (CERT, CERT),
        (TLSA, TLSA),
    )

    TYPE_USED = (
        (SOA, SOA),
        (NS, NS),
        (MX, MX),
        (A, A),
        (AAAA, AAAA),
        (CNAME, CNAME),
        (TXT, TXT),
        (PTR, PTR),
        (SRV, SRV),
    )

    id = models.AutoField(primary_key=True, help_text='This field is used to easily manage the records with this '
                                                      'number as an unique handle.')
    domain = models.ForeignKey(Domain, null=True, default=None, db_column='domain_id', to_field='id',  # Altered in SQL
                               db_constraint=False, on_delete=models.CASCADE,
                               help_text='This field binds the current record to the unique handle(the id-field) in '
                                         'the domains-table.')
    name = models.CharField(_('Name'), max_length=255, null=True, default=None, db_index=True,
                            help_text='What URI the dns-server should pick up on. For example www.test.com.')
    type = models.CharField(_('Type'), max_length=6, null=True, default=None, choices=TYPE,
                            help_text='The ASCII representation of the qtype of this record.')
    content = models.CharField(_('Content'), max_length=65535, null=True, default=None,
                               help_text='Is the answer of the DNS-query and the content depend on the type field.')
    ttl = models.IntegerField(_('TTL'), null=True, default=None,
                              help_text='How long the DNS-client are allowed to remember this record. '
                                        'Also known as Time To Live (TTL) This value is in seconds.')
    prio = models.IntegerField(_('Priority'), null=True, default=None,
                               help_text='This field sets the priority of an MX-field.')
    change_date = models.IntegerField(_('Changed'), null=True, default=None,
                                      help_text='Timestamp for the last update.')
    disabled = models.BooleanField(_('Disabled?'), default=False,
                                   help_text='If set to true, this record is hidden from DNS clients, '
                                             'but can still be modified from the REST API.')
    ordername = models.CharField(_('Ordername'), max_length=255, null=True, default=None)
    auth = models.BooleanField(_('Auth'), default=True)

    class Meta:
        app_label = 'pdns'
        verbose_name = _('Record')
        verbose_name_plural = _('Records')
        db_table = 'records'
        index_together = (('name', 'type'),)

    def __str__(self):
        return '%s (%s: %s)' % (self.id, self.type, self.name)

    def save(self, *args, **kwargs):
        logger.info('Saving %s record "%s" with content "%s" on domain "%s"',
                    self.type, self.name, self.content, self.domain)
        self.change_date = epoch()
        return super(Record, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        logger.info('Deleting %s record "%s" with content "%s" on domain "%s"',
                    self.type, self.name, self.content, self.domain)
        return super(Record, self).delete(*args, **kwargs)

    # noinspection PyShadowingBuiltins
    @classmethod
    def add_record(cls, type, domain, name, content, ttl=TTL, prio=PRIO):
        name = name.lower()  # DB constraint c_lowercase_name
        logger.info('Adding %s record "%s" with content "%s" on domain "%s"',
                    type, name, content, domain)
        return cls.objects.create(domain_id=Domain.get_domain_id(domain),
                                  name=name, type=type, content=content, ttl=ttl, prio=prio)

    # noinspection PyShadowingBuiltins
    @classmethod
    def delete_record(cls, type, domain, name):
        name = name.lower()  # DB constraint c_lowercase_name
        logger.info('Deleting %s record "%s" on domain "%s"',
                    type, name, domain)
        rec = cls.objects.get(name=name, type=type, domain_id=Domain.get_domain_id(domain))
        return rec.delete()

    # noinspection PyShadowingBuiltins
    @classmethod
    def update_record(cls, type, domain, name, content=None, ttl=None, prio=None):
        name = name.lower()  # DB constraint c_lowercase_name
        logger.info('Updating %s record "%s" with content "%s" on domain "%s"',
                    type, name, content, domain)
        rec = cls.objects.get(name=name, type=type, domain_id=Domain.get_domain_id(domain))

        if content is not None:
            rec.content = content
        if ttl is not None:
            rec.ttl = ttl
        if prio is not None:
            rec.prio = prio

        return rec.save()

    # noinspection PyShadowingBuiltins
    @classmethod
    def add_or_update_record(cls, type, domain, name, content, ttl=None, prio=None):
        name = name.lower()  # DB constraint c_lowercase_name
        domain_id = Domain.get_domain_id(domain)

        try:
            rec = cls.objects.get(type=type, name=name, domain_id=domain_id)
        except cls.DoesNotExist:
            logger.info('Adding %s record "%s" with content "%s" on domain "%s"',
                        type, name, content, domain)
            rec = cls(domain_id=domain_id, name=name, type=type, content=content)

            if ttl is None:
                ttl = cls.TTL
            if prio is None:
                prio = cls.PRIO
        else:
            logger.info('Updating %s record "%s" with content "%s" on domain "%s"',
                        type, name, content, domain)
            rec.content = content

        if ttl is not None:
            rec.ttl = ttl
        if prio is not None:
            rec.prio = prio

        return rec.save()

    @staticmethod
    def get_reverse(ipaddr):
        return reversename.from_address(ipaddr).to_text(omit_final_dot=True)

    # noinspection PyPep8Naming
    @classmethod
    def get_record_PTR(cls, ipaddr):
        try:
            return cls.objects.select_related('domain').get(type=cls.PTR, name=cls.get_reverse(ipaddr))
        except cls.DoesNotExist:
            return None
        except exception.SyntaxError:  # ipaddr in wrong format
            return None

    # noinspection PyPep8Naming
    @classmethod
    def add_record_PTR(cls, domain, ipaddr, content):
        return cls.add_record(cls.PTR, domain, cls.get_reverse(ipaddr), content)

    # noinspection PyPep8Naming
    @classmethod
    def get_records_A(cls, name, domain):
        return cls.objects.select_related('domain').filter(type=cls.A, name=name.lower(),
                                                           domain_id=Domain.get_domain_id(domain))

    @property
    def web_data(self):
        """Return dict used in web templates"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'content': self.content or '',
            'ttl': self.ttl,
            'prio': self.prio,
            'disabled': self.disabled,
        }

    @property
    def desc(self):
        """Return record description used in web templates"""
        return text_type(self)

    @property
    def web_desc(self):
        return '%s: %s' % (self.type, self.name)

    @property
    def changed(self):
        if self.change_date:
            return datetime.utcfromtimestamp(self.change_date)
        else:
            return None

    @property
    def enabled(self):
        return not self.disabled

    @property
    def full_content(self):
        """Nicer record content used in web templates"""
        if self.type in (self.MX, self.SRV) and self.content:
            return '%s %s' % (self.prio, self.content)
        else:
            return self.content

    # noinspection PyPep8Naming
    @classmethod
    def increment_SOA_serial(cls, instance):
        """Method called in post_save and post_delete to increment SOA after record updates"""
        if instance.type == cls.SOA:
            return

        try:
            soa_rec = cls.objects.get(type=cls.SOA, domain_id=instance.domain.id)
        except cls.DoesNotExist:
            logger.warning('SOA record does not exist!')
            return

        soa_rec_content = soa_rec.content.split()
        soa_serial = int(soa_rec_content[2])  # get serial from SOA record

        if 0 < soa_serial < cls.MAX_UINT32:
            soa_serial += 1
        elif soa_serial >= cls.MAX_UINT32:
            # start from 1 as we reached end of range for 32 uint
            soa_serial = 1

        soa_rec_content[2] = str(soa_serial)
        soa_rec.content = ' '.join(soa_rec_content)
        soa_rec.save(update_fields=('content', 'change_date'))

    # noinspection PyUnusedLocal
    @classmethod
    def post_save_record(cls, sender, instance, **kwargs):
        """Called via signal after record has been saved to database"""
        cls.increment_SOA_serial(instance)

    # noinspection PyUnusedLocal
    @classmethod
    def post_delete_record(cls, sender, instance, **kwargs):
        """Called via signal after record has been deleted from database"""
        cls.increment_SOA_serial(instance)
