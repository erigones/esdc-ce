from django import forms
from django.utils.translation import ugettext_lazy as _

from vms.models import NodeStorage, DcNode
from api.dc.storage.views import dc_storage
from gui.forms import SerializerForm


class StorageForm(SerializerForm):
    """
    Create or update Storage by calling dc_storage.
    """
    _api_call = dc_storage

    node = forms.ChoiceField(label=_('Node'), required=True,
                             widget=forms.Select(attrs={'class': 'input-select2 narrow disable_created2'}))
    zpool = forms.ChoiceField(label=_('Zpool'), required=True,
                              widget=forms.Select(attrs={'class': 'input-select2 narrow disable_created2'}))

    def __init__(self, request, storages, *args, **kwargs):
        super(StorageForm, self).__init__(request, storages, *args, **kwargs)
        dc = request.dc
        nodes_avail = DcNode.objects.filter(dc=dc).values_list('node', flat=True)
        nss_avail = NodeStorage.objects.filter(node__in=nodes_avail).exclude(dc=dc).values('node__hostname', 'zpool',
                                                                                           'storage__alias')
        self.node_zpool = {}
        node_choices = set()
        zpool_choices = set()

        for ns in nss_avail:
            node = ns['node__hostname']
            zpool_alias = (ns['zpool'], ns['storage__alias'])
            node_choices.add((node, node))
            zpool_choices.add(zpool_alias)

            if node not in self.node_zpool:
                self.node_zpool[node] = []

            self.node_zpool[node].append(zpool_alias)

        for ns in storages:
            node_choices.add((ns.node.hostname, ns.node.hostname))
            zpool_choices.add((ns.zpool, ns.storage.alias))

        self.fields['node'].choices = node_choices
        self.fields['zpool'].choices = zpool_choices

    @property
    def zpool_node(self):
        return self.cleaned_data['zpool'] + '@' + self.cleaned_data['node']
