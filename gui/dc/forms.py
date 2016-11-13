from django import forms
from django.utils.translation import ugettext_lazy as _
from django.contrib import messages
from logging import getLogger

from api.dc.utils import get_dc, get_dcs

logger = getLogger(__name__)


class DcSwitch(forms.Form):
    """
    Select current working datacenter.
    """
    name = forms.ChoiceField(label=_('Datacenter'), required=True, choices=[],
                             widget=forms.Select(attrs={'class': 'input-select2 wide'}))

    def __init__(self, request, *args, **kwargs):
        self.request = request
        kwargs['initial'] = {'name': request.dc.name}
        super(DcSwitch, self).__init__(*args, **kwargs)
        self.fields['name'].choices = get_dcs(request).values_list('name', 'alias')

    def save(self):
        dc_name = self.cleaned_data.get('name')

        if dc_name == self.request.dc.name:
            return False

        self.request.user.default_dc = dc = get_dc(self.request, dc_name)
        self.request.user.save(update_fields=('default_dc',))
        messages.success(self.request, _('Datacenter successfully changed to %s') % dc.alias)
        logger.info('User "%s" changed default Datacenter to "%s"', self.request.user, dc)

        return True

    def get_site_link(self):
        return self.request.user.current_dc.settings.SITE_LINK

    def get_referrer(self):
        ref = self.request.POST.get('referrer', None)

        if ref and (ref.startswith('/node') or ref.startswith('/dc') or ref.startswith('/tasklog')):
            if self.request.user.is_admin(self.request, dc=self.request.user.current_dc):
                return ref

        return None
