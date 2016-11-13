from django import forms
from django.utils.translation import ugettext_lazy as _

from vms.utils import PickleDict
from vms.models import Dc, Vm, VmTemplate, Image, Node

__all__ = ('JsonAdminForm', 'DcAdminForm', 'VmTemplateAdminForm', 'ImageAdminForm', 'NodeAdminForm', 'VmAdminForm')


class JsonAdminForm(forms.ModelForm):
    json = forms.CharField(label=_('JSON'), help_text=_('JSON configuration.'), required=True,
                           widget=forms.Textarea(attrs={'cols': 80, 'rows': 50, 'class': 'jsoneditor'}))

    # noinspection PyClassHasNoInit
    class Media:
        css = {'all': ('jsoneditor/jsoneditor-min.css',)}
        js = ('jsoneditor/jsoneditor-min.js', 'vms/js/json-admin.js')

    def __init__(self, *args, **kwargs):
        super(JsonAdminForm, self).__init__(*args, **kwargs)
        self.initial['json'] = self.instance.json.dump()

    def clean_json(self):
        try:
            data = PickleDict.load(self.cleaned_data['json'])
        except:
            raise forms.ValidationError(_('Invalid JSON format.'))

        return data


class DcAdminForm(JsonAdminForm):
    class Meta:
        model = Dc
        exclude = ()


class VmTemplateAdminForm(JsonAdminForm):
    class Meta:
        model = VmTemplate
        exclude = ()


class ImageAdminForm(JsonAdminForm):
    class Meta:
        model = Image
        exclude = ()


class NodeAdminForm(JsonAdminForm):
    class Meta:
        model = Node
        exclude = ()


class VmAdminForm(JsonAdminForm):
    json_active = forms.CharField(label=_('Active JSON'), help_text=_('Active JSON configuration.'), required=False,
                                  widget=forms.Textarea(attrs={'cols': 80, 'rows': 50, 'readonly': True,
                                                               'disabled': 'disabled', 'class': 'jsoneditor'}))
    info = forms.CharField(label=_('VM information'), help_text=_('Running VM information.'), required=False,
                           widget=forms.Textarea(attrs={'cols': 80, 'rows': 10, 'readonly': True,
                                                        'disabled': 'disabled', 'class': 'jsoneditor'}))

    class Meta:
        model = Vm
        exclude = ()

    def __init__(self, *args, **kwargs):
        super(VmAdminForm, self).__init__(*args, **kwargs)
        # Hack POST request (fields are disabled and not passed in POSTs)
        self.data['json_active'] = self.instance.json_active
        self.data['info'] = self.instance.info
        # Initial data
        self.initial['json_active'] = self.instance.json_active.dump()
        self.initial['info'] = self.instance.info.dump()
