from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from gui.forms import SerializerForm
from gui.fields import ArrayField
from api.system.update.views import system_update
from api.system.node.views import system_node_update


class UpdateForm(SerializerForm):
    """
    Update the system on mgmt to a new version.
    """
    _api_call = system_update
    _update_version = None
    _update_force = None
    _update_cert = None
    _update_key = None

    version = forms.CharField(label=_('Target version'), required=True,
                              widget=forms.TextInput(attrs={'class': 'input-transparent narrow'}),
                              help_text=mark_safe('Version tag or commit hash to which system should be updated. '
                                                  '<br>NOTE: The version tag is usually prefixed with a "v" character.'
                                                  '<br>See <a href="https://github.com/erigones/esdc-ce/blob/master'
                                                  '/doc/changelog.rst" target="_blank">CHANGELOG</a> and <a '
                                                  'href="https://github.com/erigones/esdc-ce/wiki/Release-Notes'
                                                  '" target="_blank">Release notes</a>.'))
    force = forms.BooleanField(label=_('Force update?'), required=False,
                               widget=forms.CheckboxInput(attrs={'class': 'normal-check'}),
                               help_text=_('Force update even though the software is already at selected version.'))
    cert = forms.FileField(label=_('Update certificate'), required=False, allow_empty_file=False, max_length=65536,
                           help_text=_('X509 private certificate file used for authentication against EE git server.'))
    key = forms.FileField(label=_('Update key'), required=False, allow_empty_file=False, max_length=65536,
                          help_text=_('X509 private key file used for authentication against EE git server.'))

    def _final_data(self, data=None):
        if self._update_version is None:
            self._update_version = data['version']

        if self._update_force is None:
            self._update_force = data['force']

        api_data = {'version': self._update_version, 'force': self._update_force}

        if self._update_cert is None:
            if data.get('cert'):
                self._update_cert = data['cert'].read()
            else:
                self._update_cert = ''

        if self._update_cert:
            api_data['cert'] = self._update_cert

        if self._update_key is None:
            if data.get('key'):
                self._update_key = data['key'].read()
            else:
                self._update_key = ''

        if self._update_key:
            api_data['key'] = self._update_key

        return api_data

    def call_system_update(self):
        return self.save(action='update', args=())


class NodeUpdateForm(UpdateForm):
    """
    Update the system on compute nodes to a new version.
    """
    _api_call = system_node_update
    _node_hostname = None

    hostnames = ArrayField(required=True, widget=forms.HiddenInput(attrs={'class': 'hide'}))

    def _add_error(self, field_name, error):
        if self._node_hostname:
            if isinstance(error, (list, tuple)):
                error = ['%s: %s' % (self._node_hostname, err) for err in error]
            else:
                error = '%s: %s' % (self._node_hostname, error)
        return super(NodeUpdateForm, self)._add_error(field_name, error)

    def call_system_node_update(self, hostname):
        # Save current node hostname for __add_error()
        self._node_hostname = hostname
        return self.save(action='update', args=(hostname,))
