from datetime import date, timedelta
from django import forms
from django.utils.translation import ugettext_lazy as _
from frozendict import frozendict

from api.mon.alerting.serializers import AlertSerializer


class BaseAlertFilterForm(forms.Form):
    DEFAULT_DATE_FROM = frozendict({'days': 15})

    _ser = None

    date_from = forms.DateField(label=_('Since'), required=False, input_formats=('%Y-%m-%d',),
                                widget=forms.DateInput(format='%Y-%m-%d',
                                                       attrs={'placeholder': _('Since'),
                                                              'class': 'fill-up input-navigation input-transparent '
                                                                       'input-date'}))
    date_to = forms.DateField(label=_('Until'), required=False, input_formats=('%Y-%m-%d',),
                              widget=forms.DateInput(format='%Y-%m-%d',
                                                     attrs={'placeholder': _('Until'),
                                                            'class': 'fill-up input-navigation input-transparent '
                                                                     'input-date'}))
    last = forms.CharField(label=_('Limit alerts to fetch'), required=False, max_length=2048,
                                   widget=forms.TextInput(attrs={
                                        'placeholder': _('Limit alerts to fetch'),
                                        'class': 'fill-up input-navigation input-transparent'}))

    show_events = forms.BooleanField(label=_('Show Events'), required=False, initial=True,
                                     widget=forms.CheckboxInput(attrs={'class': 'checkbox fill-up input-navigation'}))

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

    def __init__(self, data, **kwargs):
        if 'date_from' not in data:
            data['date_from'] = (date.today() - timedelta(**self.DEFAULT_DATE_FROM)).strftime('%Y-%m-%d')

        super(BaseAlertFilterForm, self).__init__(data, **kwargs)

    def clean(self):
        cleaned_data = super(BaseAlertFilterForm, self).clean()

        if not self.errors:
            self._ser = ser = AlertSerializer(data=cleaned_data)
            if not ser.is_valid():
                self._errors = ser.errors

        return cleaned_data
