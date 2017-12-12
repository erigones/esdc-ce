import time

from django import forms
from django.utils.translation import ugettext_lazy as _

from api.mon.alerting.serializers import AlertSerializer


class BaseAlertFilterForm(forms.Form):
    _ser = None

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

    show_events = forms.BooleanField(label=_('Show Events'), required=False,
                                        widget=forms.CheckboxInput(
                                            attrs={'class': 'checkbox fill-up input-navigation'}))

    vm_hostnames = forms.CharField(label=_('Hostnames'), required=False, max_length=2048,
                                   widget=forms.TextInput(attrs={
                                       'placeholder': _('Hostnames'),
                                       'class': 'fill-up input-navigation input-transparent'}))

    node_hostnames = forms.CharField(label=_('Node hostnames'), required=False, max_length=2048,
                                     widget=forms.TextInput(attrs={
                                         'placeholder': _('Node hostname'),
                                         'class': 'fill-up input-navigation input-transparent'}))

    dc_bound = forms.BooleanField(label=_('Filter as DC unbound'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'checkbox fill-up input-navigation'}))

    def __init__(self, request, data, **kwargs):
        self.request = request
        super(BaseAlertFilterForm, self).__init__(data, **kwargs)

        if not self.request.user.is_staff:  # SuperAdmin only fields
            self.fields.pop('node_hostnames')
            self.fields.pop('dc_bound')

    @staticmethod
    def convert_to_timestamp(s):
        try:
            time_struct = time.strptime(str(s), '%Y-%m-%d')
        except ValueError:
            return s

        return int(time.mktime(time_struct))

    def clean(self):
        if not self.errors:

            if self.cleaned_data['since']:
                self.cleaned_data['since'] = self.convert_to_timestamp(self.cleaned_data['since'])

            if self.cleaned_data['until']:
                self.cleaned_data['until'] = self.convert_to_timestamp(self.cleaned_data['until'])

            self._ser = ser = AlertSerializer(self.request, data=self.cleaned_data)
            if not ser.is_valid():
                self._errors = ser.errors

                return ser.data

        return super(BaseAlertFilterForm, self).clean()
