from django.utils.translation import ugettext_noop as _


LOG_DC_CREATE = _('Create datacenter')
LOG_DC_UPDATE = _('Update datacenter')
# DC_DELETE -> this is not logged

LOG_DC_SETTINGS_UPDATE = _('Update datacenter settings')

LOG_NODE_ATTACH = _('Add compute node to datacenter')
LOG_NODE_UPDATE = _('Update compute node in datacenter')
LOG_NODE_DETACH = _('Remove compute node from datacenter')

LOG_STORAGE_ATTACH = _('Add node storage to datacenter')
LOG_STORAGE_DETACH = _('Remove node storage from datacenter')

LOG_NETWORK_ATTACH = _('Add network to datacenter')
LOG_NETWORK_DETACH = _('Remove network from datacenter')

LOG_IMAGE_ATTACH = _('Add server image to datacenter')
LOG_IMAGE_DETACH = _('Remove server image from datacenter')

LOG_TEMPLATE_ATTACH = _('Add server template to datacenter')
LOG_TEMPLATE_DETACH = _('Remove server template from datacenter')

LOG_ISO_ATTACH = _('Add ISO image to datacenter')
LOG_ISO_DETACH = _('Remove ISO image from datacenter')

LOG_DOMAIN_ATTACH = _('Add DNS domain to datacenter')
LOG_DOMAIN_DETACH = _('Remove DNS domain from datacenter')

LOG_GROUP_ATTACH = _('Add user group to datacenter')
LOG_GROUP_DETACH = _('Remove user group from datacenter')
