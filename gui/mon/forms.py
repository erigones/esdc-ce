from django import forms
from django.utils.six import iteritems
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from pytz import utc

from gui.forms import SerializerForm
from gui.fields import ArrayField
from gui.widgets import ArrayWidget
from api.mon.alerting.serializers import AlertSerializer
from vms.models import DefaultDc


class BaseAlertFilterForm(SerializerForm):
    since = forms.DateTimeField(label=_('Since'), required=False, input_formats=('%Y-%m-%d', ''),
                                widget=forms.DateInput(format='%Y-%m-%d',
                                                       attrs={'placeholder': _('Since'),
                                                              'class': 'fill-up input-navigation input-transparent '
                                                              'input-date'}))

    until = forms.DateTimeField(label=_('Until'), required=False, input_formats=('%Y-%m-%d',),
                                widget=forms.DateInput(format='%Y-%m-%d',
                                                       attrs={'placeholder': _('Until'),
                                                              'class': 'fill-up input-navigation input-transparent '
                                                                       'input-date'}))

    vm_hostnames = ArrayField(label=_('Server hostnames'), required=False,
                              widget=ArrayWidget(attrs={'placeholder': _('Server hostnames'),
                                                        'class': 'fill-up input-navigation input-transparent'}))

    node_hostnames = ArrayField(label=_('Node hostnames'), required=False,
                                widget=ArrayWidget(attrs={'placeholder': _('Node hostnames'),
                                                          'class': 'fill-up input-navigation input-transparent'}))

    show_events = forms.BooleanField(label=_('Show events?'), required=False,
                                     widget=forms.CheckboxInput(attrs={'class': 'checkbox fill-up input-navigation'}))

    show_nodes = forms.BooleanField(label=_('Include compute nodes?'), required=False,
                                    widget=forms.CheckboxInput(attrs={'class': 'checkbox fill-up input-navigation'}))

    show_all = forms.BooleanField(label=_('Show all?'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'checkbox fill-up input-navigation'}))

    def __init__(self, request, *args, **kwargs):
        super(BaseAlertFilterForm, self).__init__(request, None, *args, **kwargs)
        self.api_data = None

        if request.user.is_staff:
            dc = request.dc
            if not dc.is_default() and dc.settings.MON_ZABBIX_SERVER != DefaultDc().settings.MON_ZABBIX_SERVER:
                self.fields['show_nodes'].widget.attrs['disabled'] = 'disabled'
        else:  # SuperAdmin only fields
            self.fields.pop('node_hostnames')
            self.fields.pop('show_nodes')
            self.fields.pop('show_all')

    @staticmethod
    def _remove_empty_fields(data):
        for key, value in list(iteritems(data)):
            if value in (None, [], ''):
                del data[key]

        return data

    def clean(self):
        cleaned_data = super(BaseAlertFilterForm, self).clean()

        if self._errors:
            return cleaned_data

        data = cleaned_data.copy()
        tz = timezone.get_current_timezone()

        if data['since']:
            data['since'] = data['since'].replace(tzinfo=tz).astimezone(utc).strftime('%s')

        if data['until']:
            data['until'] = data['until'].replace(tzinfo=tz).astimezone(utc).strftime('%s')

        show_nodes = data.pop('show_nodes', False)

        if data.get('show_all', False):
            data['dc_bound'] = False
        else:
            data['dc_bound'] = not show_nodes

        self._remove_empty_fields(data)
        ser = AlertSerializer(self._request, data=data)

        if ser.is_valid():
            api_data = ser.data
            # Not used filters
            del api_data['last']
            del api_data['node_uuids']
            del api_data['vm_uuids']

            if not self._request.user.is_staff:  # SuperAdmin only fields
                del api_data['node_hostnames']
                del api_data['show_all']
                api_data['dc_bound'] = True

            self.api_data = self._remove_empty_fields(api_data)
        else:
            self.api_data = None
            self._set_api_errors(ser.errors)

        return cleaned_data
