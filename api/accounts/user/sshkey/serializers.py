from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from api import serializers as s
from api.validators import validate_ssh_key
from gui.models import UserSSHKey


class UserSSHKeySerializer(s.InstanceSerializer):
    """
    gui.models.user
    """
    _model_ = UserSSHKey
    _update_fields_ = ('title', 'key',)
    _default_fields_ = ('title', 'key',)

    title = s.SafeCharField(max_length=32)
    fingerprint = s.SafeCharField(max_length=64, read_only=True, required=False)
    key = s.SafeCharField(max_length=65536)

    def validate_key(self, attrs, source):
        try:
            value = attrs[source].strip()
        except KeyError:
            pass
        else:
            fingerprint = validate_ssh_key(value)

            if UserSSHKey.objects.filter(user=self.object.user, fingerprint=fingerprint).exists():
                raise s.ValidationError(_('SSH key already defined'))

        return attrs

    def validate(self, attrs):
        total = UserSSHKey.objects.filter(user=self.object.user).count()

        if total >= settings.PROFILE_SSH_KEY_LIMIT:
            raise s.ValidationError(_('SSH keys limit reached'))

        return attrs
