from django.db import models
from django.utils.translation import ugettext_lazy as _

import base64
import hashlib

from gui.models.user import User


class UserSSHKey(models.Model):
    """
    User SSH public key.
    """
    user = models.ForeignKey(User)
    title = models.CharField(_('Title'), max_length=32)
    fingerprint = models.CharField(_('Fingerprint'), max_length=64, blank=True)
    key = models.TextField(_('Key'))

    class Meta:
        app_label = 'gui'
        verbose_name = _('SSH key')
        verbose_name_plural = _('SSH keys')
        unique_together = (('user', 'fingerprint'), ('user', 'title'))

    def __unicode__(self):
        return '%s' % (self.pk,)

    @staticmethod
    def get_fingerprint(key):
        _key = base64.b64decode(key.split(' ', 1)[-1].split(' ', 1)[0])
        _fp_plain = hashlib.md5(_key).hexdigest()
        return ':'.join(a + b for a, b in zip(_fp_plain[::2], _fp_plain[1::2]))

    def save(self, *args, **kwargs):
        self.key = self.key.strip()  # this should be done in forms
        if not self.fingerprint:
            self.fingerprint = UserSSHKey.get_fingerprint(self.key)
        super(UserSSHKey, self).save(*args, **kwargs)

    def display_fingerprint(self):
        fp = self.fingerprint.split(':')

        try:
            # noinspection PyAugmentAssignment
            fp[9] = '&#8203;' + fp[9]
            return ':'.join(fp)
        except IndexError:
            return ''

    @property
    def name(self):
        return self.title

    @name.setter
    def name(self, value):
        self.title = value

    @property
    def fingerprint_id(self):
        return self.fingerprint.replace(':', '')
