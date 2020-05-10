import time
from datetime import datetime
from logging import getLogger
from django.db import models, connections
from django.utils.translation import ugettext_lazy as _
from django.utils.six import text_type

logger = getLogger(__name__)


def epoch():
    return int(time.mktime(time.gmtime()))


class DummyPdnsCfg(object):
    key = NotImplemented
    val = NotImplemented
    change_date = NotImplemented
    log_object_name = NotImplemented
    pg_notify_channel = 'pdns_notify'
    pg_notify_payload = NotImplemented

    class Meta:
        abstract = True

    def __unicode__(self):
        return '(%s: %s)' % (self.key, self.val)

    def save(self, *args, **kwargs):
        logger.info('Saving %s entry "%s" with content "%s"',
                    self.my_name, self.key, self.val)
        self.change_date = epoch()
        return super(DummyPdnsCfg, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        logger.info('Deleting %s entry "%s" with content "%s"',
                    self.my_name, self.key, self.val)
        return super(DummyPdnsCfg, self).delete(*args, **kwargs)

    # noinspection PyShadowingBuiltins
    @classmethod
    def add_entry(cls, key, val):
        logger.info('Adding %s entry "%s" with content "%s"',
                    cls.my_name, cls.key, cls.val)
        return cls.objects.create(key=key, val=val, change_date=epoch())

    # noinspection PyShadowingBuiltins
    @classmethod
    def delete_entry(cls, key):
        logger.info('Deleting %s entry "%s"', cls.log_object_name, cls.key)
        rec = cls.objects.get(key=key)
        return rec.delete()

    # noinspection PyShadowingBuiltins
    @classmethod
    def update_entry(cls, key, val):
        rec = cls.objects.get(key=key)
        logger.info('Updating %s entry "%s" with content "%s" (old content: "%s")',
                    cls.log_object_name, cls.key, val, cls.val)
        rec.val = val
        return rec.save()

    # noinspection PyShadowingBuiltins
    @classmethod
    def add_or_update_entry(cls, key, val):
        try:
            cls.objects.get(key=key, val=val)
        except cls.DoesNotExist:
            cls.add_entry(key, val)
        else:
            cls.update_entry(key, val)

    @property
    def web_data(self):
        """Return dict used in web templates"""
        return {
            'key': self.key,
            'val': self.val,
            'change_date': self.change_date,
        }

    @property
    def my_name(self):
        """Return pretty name of this object"""
        return str(self.log_object_name)

    @property
    def desc(self):
        """Return entry description used in web templates"""
        return text_type(self)

    @property
    def web_desc(self):
        return '%s: %s' % (self.key, self.val)

    @property
    def changed(self):
        if self.change_date:
            return datetime.utcfromtimestamp(self.change_date)
        else:
            return None

    @classmethod
    def send_pg_notify(cls):
        with connections['pdns'].cursor() as cursor:
            logger.info('Sending pg_notify() with channel "%s" and payload "%s"' %
                        (cls.pg_notify_channel, cls.pg_notify_payload))
            # noinspection SqlDialectInspection,SqlNoDataSourceInspection
            cursor.execute("select pg_notify('%s', '%s')" % (cls.pg_notify_channel, cls.pg_notify_payload))

    # noinspection PyUnusedLocal
    @classmethod
    def post_save_entry(cls, sender, instance, **kwargs):
        """Called via signal after entry has been saved to database"""
        cls.send_pg_notify()

    # noinspection PyUnusedLocal
    @classmethod
    def post_delete_entry(cls, sender, instance, **kwargs):
        """Called via signal after entry has been deleted from database"""
        cls.send_pg_notify()


class PdnsRecursorCfg(DummyPdnsCfg, models.Model):
    """
    This table contains the config values that will be pushed into PowerDNS recursor
    configuration files by pdns-configd daemon. The daemon relies on table change
    trigger that pg_notify_payload executes pg_notify(). After the trigger, PDNS recursor config is updated
    and reloaded.

    CREATE TABLE cfg_recursor (
        key             VARCHAR(32) NOT NULL PRIMARY KEY,
        val             TEXT DEFAULT NULL,
        change_date     INT DEFAULT NULL,

    );
    CREATE UNIQUE INDEX cfg_recursor_index ON cfg_recursor(key);
    """

    pg_notify_payload = 'recursor_cfg_modified'
    log_object_name = 'PowerDNS recursor config'

    key = models.CharField(_('Key'), primary_key=True, max_length=32, null=False, unique=True, db_index=True,
                           help_text='PowerDNS Recursor configuration parameter keys')
    val = models.TextField(_('Value'), null=True, default=None,
                           help_text='PowerDNS Recursor configuration parameter values')
    change_date = models.IntegerField(_('Changed'), null=True, default=None,
                                      help_text='Timestamp of the last update.')

    class Meta:
        app_label = 'pdns'
        verbose_name = _('PowerDNS recursor cfg entry')
        verbose_name_plural = _('PowerDNS recursor config entries')
        db_table = 'cfg_recursor'


class PdnsCfg(DummyPdnsCfg, models.Model):
    """
    This table contains the config values that will be pushed into PowerDNS
    configuration files by pdns-configd daemon. The daemon relies on table change
    trigger that executes pg_notify(). After the trigger, PDNS config is updated
    and reloaded.

    CREATE TABLE cfg_pdns (
        key             VARCHAR(32) NOT NULL PRIMARY KEY,
        val             TEXT DEFAULT NULL,
        change_date     INT DEFAULT NULL,

    );
    CREATE UNIQUE INDEX cfg_pdns_index ON cfg_pdns(key);
    """

    pg_notify_payload = 'pdns_cfg_modified'
    log_object_name = 'PowerDNS config'

    key = models.CharField(_('Key'), primary_key=True, max_length=32, null=False, unique=True, db_index=True,
                           help_text='PowerDNS configuration parameter keys')
    val = models.TextField(_('Value'), null=True, default=None,
                           help_text='PowerDNS configuration parameter values')
    change_date = models.IntegerField(_('Changed'), null=True, default=None,
                                      help_text='Timestamp of the last update.')

    class Meta:
        app_label = 'pdns'
        verbose_name = _('PowerDNS config entry')
        verbose_name_plural = _('PowerDNS config entries')
        db_table = 'cfg_pdns'


class RecurseNetworks(models.Model):
    """
    This table contains a list of subnets that are allowed to do recursive queries to pdns server.
    These entries will be picked up and processed by dnsdist server.

    CREATE TABLE recurse_networks (
        id              SERIAL PRIMARY KEY,
        net_name        VARCHAR(50),
        subnet          VARCHAR(50) NOT NULL,
        change_date     INT DEFAULT NULL,

    );
    CREATE UNIQUE INDEX recurse_networks_name_index ON recurse_networks(net_name);
    CREATE UNIQUE INDEX recurse_networks_subnet_index ON recurse_networks(subnet);
    """

    pg_notify_channel = 'pdns_notify'
    pg_notify_payload = 'pdns_recurse_modified'
    log_object_name = 'dnsdist recurse networks'

    id = models.AutoField(primary_key=True, help_text='Unique handle for network entries')
    subnet = models.CharField(_('Subnet'), max_length=50, null=False, db_index=True,
                              help_text='Network subnet to allow recursion from (format: x.x.x.x/yy)')
    net_name = models.CharField(_('Network name'), max_length=50, db_index=True,
                                help_text='Network name in the danube networks list')
    change_date = models.IntegerField(_('Changed'), null=True, default=None,
                                      help_text='Timestamp of the last update.')

    class Meta:
        app_label = 'pdns'
        verbose_name = _('Recursion subnet')
        verbose_name_plural = _('Recursion subnets')
        db_table = 'recurse_networks'

    def __unicode__(self):
        return '(%s: %s)' % (self.net_name, self.subnet)

    def save(self, *args, **kwargs):
        logger.info('Saving allowed recurse network "%s" (id=%s) with content "%s"',
                    self.net_name, self.id, self.subnet)
        self.change_date = epoch()
        return super(RecurseNetworks, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        logger.info('Deleting allowed recurse network "%s" (id=%s) with content "%s"',
                    self.net_name, self.id, self.subnet)
        return super(RecurseNetworks, self).delete(*args, **kwargs)

    # noinspection PyShadowingBuiltins
    @classmethod
    def add_entry(cls, subnet, net_name):
        logger.info('Adding allowed recurse network "%s" with content "%s"',
                    net_name, subnet)
        return cls.objects.create(net_name=net_name, subnet=subnet, change_date=epoch())
        # return self.objects.create(net_name=net_name, subnet=subnet)

    # noinspection PyShadowingBuiltins
    @classmethod
    def get_entries(cls, id=None, subnet=None, net_name=None):
        kwargs = {}
        if id:
            kwargs.update({'id': id})
        if subnet:
            kwargs.update({'subnet': subnet})
        if net_name:
            kwargs.update({'net_name': net_name})

        return cls.objects.filter(**kwargs)

    # noinspection PyShadowingBuiltins
    @classmethod
    def delete_entries(cls, id=None, subnet=None, net_name=None):
        """ Deletes all entries that are matched by provided parameters (uses object.filter()) """
        # forward all search arguments
        nets = cls.get_entries(id=id, subnet=subnet, net_name=net_name)
        for net in nets:
            net.delete()

        return True

    # noinspection PyShadowingBuiltins
    @classmethod
    def update_entry(cls, id, new_subnet, new_net_name):
        net = cls.objects.get(id=id)
        logger.info('Updating %s entry with content subnet="%s", net_name="%s" (old content: "%s", "%s")',
                    cls.log_object_name, new_subnet, new_net_name, net.subnet, net.net_name)
        net.subnet = new_subnet
        net.net_name = new_net_name
        return net.save()

    # noinspection PyShadowingBuiltins
    @classmethod
    def add_or_update_entry(cls, subnet, net_name):
        try:
            net = cls.objects.get(subnet=subnet, net_name=net_name)
        except cls.DoesNotExist:
            return cls.add_entry(subnet, net_name)
        else:
            return cls.update_entry(net.id, subnet, net_name)

    @property
    def web_data(self):
        """Return dict used in web templates"""
        return {
            'subnet': self.subnet,
            'net_name': self.net_name,
            'change_date': self.change_date,
        }

    @property
    def my_name(self):
        """Return pretty name of this object"""
        return str(self.log_object_name)

    @property
    def desc(self):
        """Return entry description used in web templates"""
        return text_type(self)

    @property
    def web_desc(self):
        return '%s: %s' % (self.subnet, self.net_name)

    @property
    def changed(self):
        if self.change_date:
            return datetime.utcfromtimestamp(self.change_date)
        else:
            return None

    @classmethod
    def send_pg_notify(cls):
        with connections['pdns'].cursor() as cursor:
            logger.info('Sending pg_notify() with channel "%s" and payload "%s"' %
                        (cls.pg_notify_channel, cls.pg_notify_payload))
            # noinspection SqlDialectInspection,SqlNoDataSourceInspection
            cursor.execute("select pg_notify('%s', '%s')" % (cls.pg_notify_channel, cls.pg_notify_payload))

    # noinspection PyUnusedLocal
    @classmethod
    def post_save_entry(cls, sender, instance, **kwargs):
        """Called via signal after entry has been saved to database"""
        cls.send_pg_notify()

    # noinspection PyUnusedLocal
    @classmethod
    def post_delete_entry(cls, sender, instance, **kwargs):
        """Called via signal after entry has been deleted from database"""
        cls.send_pg_notify()
