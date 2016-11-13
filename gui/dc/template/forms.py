from django import forms
from django.utils.translation import ugettext_lazy as _

from api.dc.template.views import dc_template
from gui.forms import SerializerForm


class TemplateForm(SerializerForm):
    """
    Create or remove DC<->VmTemplate link by calling dc_template.
    """
    _api_call = dc_template

    name = forms.ChoiceField(label=_('Template'), required=True,
                             widget=forms.Select(attrs={'class': 'input-select2 narrow disable_created2'}))

    def __init__(self, request, templates, *args, **kwargs):
        super(TemplateForm, self).__init__(request, None, *args, **kwargs)
        self.fields['name'].choices = templates.values_list('name', 'alias')

    def _final_data(self, data=None):
        return {}
