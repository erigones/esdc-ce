from django import forms
from django.utils.translation import ugettext_lazy as _

from gui.forms import SerializerForm
from gui.widgets import NumberInput
from gui.vm.forms import HostnameForm
from api.vm.utils import get_nodes
from api.vm.replica.views import vm_replica


class ServerReplicaForm(HostnameForm, SerializerForm):
    """
    Server replication settings admin form.
    """
    _api_call = vm_replica

    repname = forms.CharField(label=_('Replica Name'), required=False,
                              widget=forms.TextInput(attrs={'class': 'input-transparent narrow disable_created',
                                                            'required': 'required'}))
    node = forms.TypedChoiceField(label=_('Target Node'), required=True, coerce=str, empty_value=None,
                                  widget=forms.Select(attrs={'class': 'input-select2 narrow disable_created2'}))
    sleep_time = forms.IntegerField(label=_('Sleep Time'), max_value=86400, min_value=0, required=True,
                                    help_text=_('Amount of time to pause between two syncs.'),
                                    widget=NumberInput(attrs={'class': 'input-transparent narrow',
                                                              'required': 'required'}))
    enabled = forms.BooleanField(label=_('Enabled?'), required=False,
                                 widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    reserve_resources = forms.BooleanField(label=_('Reserve Resources?'), required=False,
                                           help_text=_('Whether to reserve resources (vCPU, RAM) on target compute node'
                                                       '. NOTE: When disabled, the resources will be reserved (and must'
                                                       ' be available) before the failover action.'),
                                           widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))

    def __init__(self, request, vm, slave_vm, *args, **kwargs):
        self.slave_vm = slave_vm
        vm_nodes = kwargs.pop('vm_nodes', None)
        super(ServerReplicaForm, self).__init__(request, vm, *args, **kwargs)
        if not vm_nodes:
            vm_nodes = get_nodes(request, is_compute=True)
        self.fields['node'].choices = [(i.hostname, i.hostname) for i in vm_nodes]

    def _initial_data(self, request, obj):
        """Initial data used by 'update'"""
        return self.slave_vm.web_data
