from api.network.messages import LOG_NET_UPDATE
from api.image.messages import LOG_IMAGE_UPDATE
from api.template.messages import LOG_TEMPLATE_UPDATE
from api.iso.messages import LOG_ISO_UPDATE
from api.accounts.messages import LOG_USER_UPDATE, LOG_GROUP_UPDATE
from api.dns.messages import LOG_DOMAIN_UPDATE


# Used to call remove_dc_binding_virt_object() during removal of a whole DC object
LOG_VIRT_OBJECT_UPDATE_MESSAGES = {
    'subnet': LOG_NET_UPDATE,
    'image': LOG_IMAGE_UPDATE,
    'vmtemplate': LOG_TEMPLATE_UPDATE,
    'iso': LOG_ISO_UPDATE,
    'user': LOG_USER_UPDATE,
    'role': LOG_GROUP_UPDATE,
    'domain': LOG_DOMAIN_UPDATE,
}
