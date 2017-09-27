from django.db import models, connections
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth import get_user_model


class EmptyDomainOwner(object):
    """
    Dummy model used as the owner attribute in case the domain.id is NULL.
    """
    def __getattr__(self, item):
        return None

    def __str__(self):
        return ''

    def __nonzero__(self):
        return False
    __bool__ = __nonzero__


class Domain(models.Model):
    """
    This table contains all the domain names that your pdns-server is handling
    if you have enabled the SQL-backend. With it comes some settings that I
    don't know what they do, so hopefully the knowledge of you programmers
    will fill in the gaps.

    CREATE TABLE domains (
        id              SERIAL PRIMARY KEY,
        name            VARCHAR(255) NOT NULL,
        master          VARCHAR(128) DEFAULT NULL,
        last_check      INT DEFAULT NULL,
        type            VARCHAR(6) NOT NULL,
        notified_serial INT DEFAULT NULL,
        account         VARCHAR(40) DEFAULT NULL

        CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT))) -- (custom SQL)
    );
    CREATE UNIQUE INDEX name_index ON domains(name); -- (by django)
    + index on type
    + user integer field (relation to User model) (default value set in SQL)
    + desc field (default value set in SQL)
    + access field (default value set in SQL)
    + created field (null=True)
    + changed field (null=True)
    """
    NoOwner = EmptyDomainOwner
    QServerExclude = Q(name__iendswith='in-addr.arpa')
    _user_model = None  # Cache the User model
    _owner = models.Empty  # Owner (user) object cache

    MASTER = 'MASTER'
    SLAVE = 'SLAVE'
    NATIVE = 'NATIVE'
    SUPERSLAVE = 'SUPERSLAVE'
    TYPE = (
        (MASTER, 'MASTER'),
        (SLAVE, 'SLAVE'),
        (NATIVE, 'NATIVE'),
        (SUPERSLAVE, 'SUPERSLAVE'),
    )
    TYPE_MASTER = (
        (MASTER, 'MASTER'),
        (NATIVE, 'NATIVE'),
    )

    PUBLIC = 1
    DISABLED = 2
    PRIVATE = 3
    DELETED = 4
    INTERNAL = 9
    ACCESS = (
        (PUBLIC, _('Public')),
        (PRIVATE, _('Private')),
    )
    INVISIBLE = (DELETED, INTERNAL)
    UNUSABLE = (DISABLED, DELETED, INTERNAL)

    id = models.AutoField(primary_key=True, help_text='This field is used to easily manage the domains '
                                                      'with this number as an unique handle.')
    name = models.CharField(_('Name'), max_length=255, unique=True,
                            help_text='This field is the actual domain name. This is the field that powerDNS matches '
                                      'to when it gets a request. The domain name should be in the '
                                      'format of: domainname.TLD.')
    master = models.CharField(_('Master'), max_length=128, null=True, default=None,
                              help_text='This describes the master nameserver from which this domain should be slaved.')
    last_check = models.IntegerField(_('Last check'), null=True, default=None,
                                     help_text='Last time this domain was checked for freshness.')
    type = models.CharField(_('Type'), max_length=6, db_index=True, choices=TYPE, help_text='Type of the domain.')
    notified_serial = models.IntegerField(_('Notified serial'), null=True, default=None,
                                          help_text='The last notified serial of a master domain. '
                                                    'This is updated from the SOA record of the domain.')
    account = models.CharField(_('Account'), max_length=40, null=True, default=None,
                               help_text='Determine if a certain host is a supermaster for a certain domain name.')
    user = models.IntegerField(_('User'), null=True, default=None, db_index=True,
                               help_text='Field representing the user ID responsible for the domain. '
                                         'Added by Erigones.')
    desc = models.CharField(_('Description'), max_length=128, blank=True, help_text='Added by Erigones.')
    access = models.SmallIntegerField(_('Access'), choices=ACCESS, default=PRIVATE, help_text='Added by Erigones.')
    created = models.DateTimeField(_('Created'), auto_now_add=True, editable=False, null=True,
                                   help_text='Added by Erigones.')
    changed = models.DateTimeField(_('Last changed'), auto_now=True, editable=False, null=True,
                                   help_text='Added by Erigones.')
    dc_bound = models.IntegerField(_('Datacenter'), null=True, default=None,
                                   help_text='Datacenter ID used for DC-bound DNS records. Added by Erigones.')

    class Meta:
        app_label = 'pdns'
        verbose_name = _('Domain')
        verbose_name_plural = _('Domains')
        db_table = 'domains'

    def __unicode__(self):
        return '%s' % self.name

    @classmethod
    def get_domain_id(cls, domain):
        try:
            return int(domain)
        except (TypeError, ValueError):
            return cls.objects.only('id').get(name=domain).id

    @classmethod
    def get_user_model(cls):
        if cls._user_model is None:
            cls._user_model = get_user_model()
        return cls._user_model

    @property
    def dc_bound_bool(self):
        return bool(self.dc_bound)

    @dc_bound_bool.setter
    def dc_bound_bool(self, dc_id):
        # This looks weird, but is used by some serializers
        self.dc_bound = dc_id

    @property
    def new(self):
        return not bool(self.id)

    @property
    def user_model(self):
        return self.get_user_model()

    @property
    def owner(self):
        if self._owner is models.Empty:
            if self.user:
                user_model = self.user_model
                try:
                    self._owner = user_model.objects.get(pk=self.user)
                except user_model.DoesNotExist:
                    self._owner = self.NoOwner()
            else:
                self._owner = self.NoOwner()
        return self._owner

    @owner.setter
    def owner(self, value):
        self._owner = value
        if value:
            self.user = value.pk
        else:
            self.user = None

    @property
    def web_data(self):
        """Return dict used in web templates"""
        return {
            'name': self.name,
            'type': self.type,
            'access': self.access,
            'owner': self.owner.username,
            'desc': self.desc,
            'dc_bound': self.dc_bound_bool,
        }

    #
    # Properties required for task log
    #

    @property
    def alias(self):
        return self.name

    @property
    def log_name(self):
        return self.name

    @property
    def log_alias(self):
        return self.name

    @property
    def log_list(self):
        return self.name, self.name, self.pk, self.__class__

    @staticmethod
    def get_log_name_lookup_kwargs(log_name_value):
        """Return lookup_key=value DB pairs which can be used for retrieving objects by log_name value"""
        return {'name': log_name_value}

    # noinspection PyUnusedLocal
    @staticmethod
    def post_save_domain(sender, instance, created, **kwargs):
        """Called via signal after domain has been saved to database"""
        if created:
            with connections['pdns'].cursor() as cursor:
                cursor.execute("INSERT INTO domainmetadata (domain_id, kind, content) VALUES "
                               "(%s, 'ALLOW-AXFR-FROM', 'AUTO-NS')", [instance.id])

    def get_related_datacenters(self):
        from vms.models import Dc
        return Dc.objects.filter(domaindc__domain_id=self.id)
