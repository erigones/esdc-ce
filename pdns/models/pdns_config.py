import time
from datetime import datetime
from logging import getLogger
from django.db import models, connections
from django.utils.translation import ugettext_lazy as _
from django.utils.six import text_type

logger = getLogger(__name__)


def epoch():
    return int(time.mktime(time.gmtime()))

class DummyPdnsCfg(models.Model):
    key = NotImplemented
    val = NotImplemented
    change_date = NotImplemented
    log_object_name = NotImplemented
    pg_notify_channel = 'pdns_notify'

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
        return cls.objects.create(key=key, val=val, change_date = epoch())

    # noinspection PyShadowingBuiltins
    @classmethod
    def delete_entry(cls, key):
        logger.info('Deleting %s entry "%s"', log_object_name, elf.key)
        rec = cls.objects.get(key=key)
        return rec.delete()

    # noinspection PyShadowingBuiltins
    @classmethod
    def update_entry(cls, key, val):
        rec = cls.objects.get(key=key)
        logger.info('Updating %s entry "%s" with content "%s" (old content: "%s")',
                    log_object_name, self.key, val, self.val)
        rec.val = val
        return rec.save()

    # noinspection PyShadowingBuiltins
    @classmethod
    def add_or_update_entry(cls, key, val):
        try:
            rec = cls.objects.get(type=type, name=name, domain_id=domain_id)
        except cls.DoesNotExist:
            add_entry(cls, key, val)
        else:
            update_entry(cls, key, val)

        return rec.save()


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
    trigger that executes pg_notify(). After the trigger, PDNS recursor config is updated
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
                                      help_text='Timestamp for the last update.')

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
                                      help_text='Timestamp for the last update.')

    class Meta:
        app_label = 'pdns'
        verbose_name = _('PowerDNS config entry')
        verbose_name_plural = _('PowerDNS config entries')
        db_table = 'cfg_pdns'

