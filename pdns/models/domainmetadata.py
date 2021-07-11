import re
from django.db import models
from logging import getLogger

from api.exceptions import InvalidInput

logger = getLogger(__name__)


class DomainMetadata(models.Model):
    """
    This table contains metadata for all domains.

    CREATE TABLE public.domainmetadata (
        id integer NOT NULL,
        domain_id integer,
        kind character varying(32),
        content text
    );
    """
    domain = models.ForeignKey('pdns.Domain', blank=True, null=True)
    kind = models.CharField(max_length=32, blank=True, null=True)
    content = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'domainmetadata'

    def __unicode__(self):
        return '(%s: %s=%s)' % (self.domain, self.kind, self.content)

    def save(self, *args, **kwargs):
        logger.info('Saving domainmetadata entry for domain "%s": "%s"="%s"',
                    self.domain, self.kind, self.content)
        return super(DomainMetadata, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        logger.info('Deleting domainmetadata entry for domain "%s": "%s"="%s"',
                    self.domain, self.kind, self.content)
        return super(DomainMetadata, self).delete(*args, **kwargs)

    @property
    def get_content(self):
        return self.content


class TsigKey(models.Model):
    """
    This table stores TSIG DNS keys used for AXFR. It is referenced by DomainMetadata model.

    CREATE TABLE public.tsigkeys (
        id integer NOT NULL,
        name character varying(255),
        algorithm character varying(50),
        secret character varying(255),
        CONSTRAINT c_lowercase_name CHECK (((name)::text = lower((name)::text)))
    );

    """

    # ALGORITHM = (
    #     (MD5, "hmac-md5"),
    #     (SHA1, "hmac-sha1"),
    #     (SHA224, "hmac-sha224"),
    #     (SHA256, "hmac-sha256"),
    #     (SHA384, "hmac-sha384"),
    #     (SHA512, "hmac-sha512"),
    # )
    ALGORITHM = (
        ('hmac-md5', 'hmac-md5'),
        ('hmac-sha1', 'hmac-sha1'),
        ('hmac-sha224', 'hmac-sha224'),
        ('hmac-sha256', 'hmac-sha256'),
        ('hmac-sha384', 'hmac-sha384'),
        ('hmac-sha512', 'hmac-sha512'),
    )
    ALGORITHM_DEFAULT = 'hmac-sha256'
    ALGORITHMS = [x[1] for x in ALGORITHM]

    name = models.CharField(max_length=255, blank=True, null=True)
    algorithm = models.CharField(max_length=50, blank=True, null=True, choices=ALGORITHM, default=ALGORITHM_DEFAULT)
    secret = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tsigkeys'
        unique_together = (('name', 'algorithm'),)

    def validate(self):
        logger.error('Matching name: ', self.name)
        if not re.match('^[A-Za-z0-9\._/-]{1,250}$', self.name):
            logger.error('Matching name 2x: ', self.name)
            raise InvalidInput('Invalid TSIG name: "%s"' % self.name)
        if len(self.secret) > 250:
            raise InvalidInput('TSIG secret too long')
        if self.algorithm not in self.ALGORITHMS:
            raise InvalidInput('Invalid TSIG algorithm: "%s". Must be one of: %s' % (self.algorithm, self.ALGORITHMS))
        return True

    def __str__(self):
        return '(%s:%s:%s)' % (self.algorithm, self.name, self.secret)

    def __unicode__(self):
        return self.__str__()

    def to_str(self):
        return '%s:%s:%s' % (self.algorithm, self.name, self.secret)

    # def save(self, *args, **kwargs):
    #     logger.info('Saving tsigkey entry "%s" with algoritm "%s" and content "%s"',
    #                 self.name, self.algorithm, self.secret)
    #     return super(TsigKey, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        for domain in self.get_linked_axfr_domains():
            self.unlink_axfr_domain(domain)

        logger.info('Deleting tsigkey entry "%s" with algoritm "%s" and content "%s"',
                    self.name, self.algorithm, self.secret)
        return super(TsigKey, self).delete(*args, **kwargs)

    @staticmethod
    def get_linked_axfr_keys(domain):
        """
        Returns list of TSIG keys set for specified domain.
        :param domain: Domain object
        :return: list of TsigKey objects
        """
        return [TsigKey.objects.get(name=key_name.content) for key_name in
                DomainMetadata.objects.filter(kind='TSIG-ALLOW-AXFR', domain_id=domain.id)]

    def get_linked_axfr_domains(self):
        """
        Returns list of domains which use this TSIG key.
        :return: list of Domain objects
        """
        return [entry.domain for entry in DomainMetadata.objects.filter(kind='TSIG-ALLOW-AXFR', content=self.name)]

    def link_to_axfr_domain(self, domain):
        """
        Sets TSIG-ALLOW-AXFR for domain.id to tsigkey.name.
        :param domain: Domain object
        :return: django exception on error, else nothing
        """
        try:
            DomainMetadata.objects.get(kind='TSIG-ALLOW-AXFR', domain_id=domain.id, content=self.name)
            # key already exists, do nothing
            return

        except DomainMetadata.DoesNotExist:
            DomainMetadata(kind='TSIG-ALLOW-AXFR', domain_id=domain.id, content=self.name).save()

    def unlink_axfr_domain(self, domain):
        """
        Removes entry TSIG-ALLOW-AXFR for domain.id pointing to self.name.
        :param domain: Domain object
        :return: django exception on error, else nothing
        """
        try:
            link = DomainMetadata.objects.get(kind='TSIG-ALLOW-AXFR', domain_id=domain.id, content=self.name)
            link.delete()
            if len(self.get_linked_axfr_domains()) == 0:
                # no domains use this key anymore... we can delete it
                logger.info('The TSIG key "%s" is no longer in use. Deleting it.' % self.name)
                self.delete()

        except DomainMetadata.DoesNotExist:
            # nothing to delete
            return

    @staticmethod
    def parse_tsig_string(text):
        """
        Converts string to TsigKey object.
        :param text: "algorithm:name:key" or "name:key" (default algorithm is TsigKey.ALGORITHM_DEFAULT)
        :return: new TsigKey object or None on error
        """
        try:
            key = text.split(':')
            if len(key) == 2:
                return TsigKey(algorithm=TsigKey.ALGORITHM_DEFAULT, name=key[0], secret=key[1])
            elif len(key) == 1:
                # this creates invalid TsigKey but the name can be filled in also later to make the object valid
                return TsigKey(algorithm=TsigKey.ALGORITHM_DEFAULT, name='', secret=key[0])
            else:
                return TsigKey(algorithm=key[0], name=key[1], secret=key[2])
        except IndexError:
            # invalid TSIG string format
            return None