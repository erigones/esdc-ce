from django import forms
from django.utils.translation import ugettext_lazy as _

from gui.forms import SerializerForm
from api.mon.alerting.serializers import AlertSerializer


class BaseAlertFilterForm(SerializerForm):
    since = forms.DateField(label=_('Since'), required=False, input_formats=('%Y-%m-%d', ''),
                                widget=forms.DateInput(format='%Y-%m-%d',
                                                       attrs={'placeholder': _('Since'),
                                                              'class': 'fill-up input-navigation input-transparent '
                                                                       'input-date'}))
    until = forms.DateField(label=_('Until'), required=False, input_formats=('%Y-%m-%d',),
                              widget=forms.DateInput(format='%Y-%m-%d',
                                                     attrs={'placeholder': _('Until'),
                                                            'class': 'fill-up input-navigation input-transparent '
                                                                     'input-date'}))
    last = forms.CharField(label=_('Limit alerts to fetch'), required=False, max_length=2048,
                                   widget=forms.TextInput(attrs={
                                        'placeholder': _('Limit alerts to fetch'),
                                        'class': 'fill-up input-navigation input-transparent'}))

    vm_hostnames = forms.CharField(label=_('Hostnames'), required=False, max_length=2048,
                                   widget=forms.TextInput(attrs={
                                       'placeholder': _('Hostnames'),
                                       'class': 'fill-up input-navigation input-transparent'}))

    node_hostnames = forms.CharField(label=_('Node hostnames'), required=False, max_length=2048,
                                     widget=forms.TextInput(attrs={
                                         'placeholder': _('Node hostname'),
                                         'class': 'fill-up input-navigation input-transparent'}))

    dc_bound = forms.BooleanField(label=_('Filter as DC bound'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'checkbox fill-up input-navigation'}))

    show_events = forms.BooleanField(label=_('Show Events'), required=False,
                                        widget=forms.CheckboxInput(
                                            attrs={'class': 'checkbox fill-up input-navigation'}))

    def __init__(self, request, *args, **kwargs):
        super(BaseAlertFilterForm, self).__init__(request, None, *args, **kwargs)
        self.api_data = {}

        if not request.user.is_staff:  # SuperAdmin only fields
            self.fields.pop('node_hostnames')
            self.fields.pop('dc_bound')

    def clean(self):
        if not self._errors:
            data = self.cleaned_data.copy()

            if data['since']:
                data['since'] = data['since'].strftime('%s')

            if data['until']:
                data['until'] = data['until'].strftime('%s')

            data = self.remove_empty_fields(data)
            ser = AlertSerializer(self._request, data=data)

            if ser.is_valid():
                self.api_data = ser.data

                if not self._request.user.is_staff:  # SuperAdmin only fields
                    self.api_data.pop('node_hostnames')
                    self.api_data.pop('node_uuids')
                    self.api_data.pop('dc_bound')

                self.api_data = self.remove_empty_fields(self.api_data)
            else:
                self._set_api_errors(ser.errors)

        return super(BaseAlertFilterForm, self).clean()

    @staticmethod
    def remove_empty_fields(data):
        cleaned_data = {}

        for attribute in data:
            if data[attribute] not in (None, [], ''):
                cleaned_data[attribute] = data[attribute]

        return cleaned_data

    @classmethod
    def format_data(cls, data):
        formated_data = data.dict()
        formated_data = cls.remove_empty_fields(formated_data)

        if 'vm_hostnames[]' in formated_data:
            formated_data['vm_hostnames'] = data.getlist('vm_hostnames[]')
            formated_data.pop('vm_hostnames[]')

        if 'node_hostnames[]' in formated_data:
            formated_data['node_hostnames'] = data.getlist('node_hostnames[]')
            formated_data.pop('node_hostnames[]')

        return formated_data
