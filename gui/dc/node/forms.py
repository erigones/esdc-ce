from django import forms
from django.utils.translation import ugettext_lazy as _

from vms.models import Node, DcNode, Storage
from api.dc.node.views import dc_node
from gui.forms import SerializerForm
from gui.widgets import NumberInput

add_storage_choices = Storage.ACCESS + ((9, _('(all)')), (0, _('(none)')))


class DcNodeForm(SerializerForm):
    """
    Create or update Dc<->Node association by calling dc_node.
    """
    _api_call = dc_node

    hostname = forms.ChoiceField(label=_('Hostname'), required=True,
                                 widget=forms.Select(attrs={'class': 'narrow input-select2 disable_created2'}))
    strategy = forms.TypedChoiceField(label=_('Resource strategy'), required=True, coerce=int, choices=DcNode.STRATEGY,
                                      widget=forms.Select(attrs={'class': 'input-select2 narrow'}))
    priority = forms.IntegerField(label=_('Priority'), required=True,
                                  help_text=_('Higher priority means that the automatic node chooser '
                                              'will more likely choose this node.'),
                                  widget=NumberInput(attrs={'class': 'input-transparent narrow',
                                                            'required': 'required'}))
    cpu = forms.IntegerField(label=_('CPUs'), required=False,
                             help_text=_('Total number of CPUs (cores).'),
                             widget=NumberInput(attrs={'class': 'input-transparent narrow', 'required': 'required'}))
    # noinspection SpellCheckingInspection
    ram = forms.IntegerField(label=_('RAM'), required=False,
                             help_text=_('Total RAM size in MB.'),
                             widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                           'required': 'required',
                                                           'pattern': '[0-9\.]+[BKMGTPEbkmgtpe]?'}))
    # noinspection SpellCheckingInspection
    disk = forms.IntegerField(label=_('Disk pool size'), required=False,
                              help_text=_('Size of the local disk pool.'),
                              widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                            'required': 'required',
                                                            'pattern': '[0-9\.]+[BKMGTPEbkmgtpe]?'}))
    add_storage = forms.TypedChoiceField(label=_('Attach node Storages'), required=False, coerce=int, empty_value=0,
                                         choices=add_storage_choices,
                                         widget=forms.Select(attrs={'class': 'narrow input-select2 disable_created2'}))

    def __init__(self, request, instance, *args, **kwargs):
        super(DcNodeForm, self).__init__(request, instance, *args, **kwargs)
        self.fields['hostname'].choices = Node.objects.all().values_list('hostname', 'hostname')

    def _initial_data(self, request, obj):
        return obj.web_data

    def _has_changed(self):
        try:
            del self.cleaned_data['add_storage']
        except KeyError:
            pass
        return super(DcNodeForm, self)._has_changed()
