from functools import partial
from logging import getLogger
from time import sleep
import os
# noinspection PyCompatibility
import ipaddress
from django.conf import settings

from api import status
from api.utils.request import get_dummy_request
from api.utils.views import call_api_view
from api.system.utils import get_local_netinfo
from api.dns.domain.utils import reverse_domain_from_network
from api.mon.alerting.tasks import mon_all_groups_sync
from vms.models import Dc, Image, Vm, DcNode

logger = getLogger(__name__)


class APIViewError(Exception):
    pass


def _api_cmd(request, method, view, *args, **kwargs):
    """Call api view and raise exception according to result"""
    res = call_api_view(request, method, view, *args, data=kwargs)
    cod = res.status_code
    out = res.data
    log = '%s %s(%s, data=%s)' % (method, view.__name__, args, kwargs)

    if status.is_success(cod):
        logger.info('%s was successful (%s): %s', log, cod, out)
    else:
        # Do not fail if created object already exists
        if method == 'POST' and cod == status.HTTP_406_NOT_ACCEPTABLE:
            logger.warning('%s failed (%s): %s', log, cod, out)
        else:
            logger.error('%s failed (%s): %s', log, cod, out)
            raise APIViewError(str(out))

    return res


def _es_api_url(site_link):
    """Update API_URL in es"""
    es_src = os.path.join(settings.PROJECT_DIR, 'bin', 'es')
    es_dst = os.path.join(settings.PROJECT_DIR, 'var', 'www', 'static', 'api', 'bin', 'es')
    api_url = "API_URL = '%s'" % (site_link + '/api')
    logger.info('Replacing API_URL in %s with "%s"', es_dst, api_url)

    with open(es_src) as es1:
        # noinspection PyTypeChecker
        with os.fdopen(os.open(es_dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644), 'w') as es2:
            es2.write(es1.read().replace("API_URL = 'http://127.0.0.1:8000/api'", api_url))


def _save_image(manifest, default_dc, admin_dc):
    """Save image from image manifest"""
    # noinspection PyProtectedMember
    image_desc_max_length = Image._meta.get_field('desc').max_length
    # noinspection PyProtectedMember
    image_name_max_length = Image._meta.get_field('name').max_length
    name = manifest['name'][:image_name_max_length]
    i = 0
    i_str = str(i)

    while Image.objects.filter(name=name).exists() and len(i_str) < image_name_max_length:
        i += 1
        i_str = str(i)
        # Create new name by appending a number to the existing name
        # (optionally stripping n-number of characters from end of the name)
        name = name[:(image_name_max_length - len(i_str))] + i_str

    img = Image(uuid=manifest['uuid'])
    img.owner_id = settings.ADMIN_USER
    img.name = img.alias = name
    img.version = manifest['version']
    img.ostype = Image.os_to_ostype(manifest)
    img.size = int(manifest.get('image_size', Image.DEFAULT_SIZE))
    img.desc = manifest.get('description', '')[:image_desc_max_length]
    img.status = Image.OK
    img.manifest = img.manifest_active = manifest
    tags = manifest.pop('tags', {})
    img.tags = tags.get(Image.TAGS_KEY, [])
    img.deploy = tags.get('deploy', False)
    img.resize = tags.get('resize', img.ostype in img.ZONE)
    internal = tags.get('internal', False)

    if internal:
        img.dc_bound = admin_dc
        img.access = Image.INTERNAL
    else:
        img.dc_bound = None
        img.access = Image.PUBLIC

    img.save()

    img.dc.add(admin_dc)

    if not internal:
        img.dc.add(default_dc)

    return img


def _init_images(node, images, default_dc, admin_dc):
    """Import manifests of initial images - images imported on head node and in the image server"""
    for image in images:
        try:
            manifest = image['manifest']

            try:
                img = Image.objects.get(uuid=manifest['uuid'])
            except Image.DoesNotExist:
                img = _save_image(manifest, default_dc, admin_dc)
        except Exception as ex:
            logger.exception(ex)
            logger.error('Could not initialize image from object: %s', image)
            continue
        else:
            logger.info('Added initial image %s (%s (%s))', img.uuid, img.name, img.version)

        try:
            ns = node.nodestorage_set.get(zpool=image['zpool'])
            ns.images.add(img)
        except Exception as ex:
            logger.exception(ex)
            logger.error('Could not associate image %s with zpool %s on node %s', img, image.get('zpool'), node)
        else:
            logger.info('Associated image %s with node storage %s', img, ns)


# noinspection PyArgumentList
def init_mgmt(head_node, images=None):  # noqa: R701
    """
    Initialize the system and create the "admin" datacenter.
    """
    from api.dc.views import dc_node, dc_settings, dc_domain
    from api.network.base.views import net_manage
    from api.dns.domain.views import dns_domain
    from api.dns.record.views import dns_record
    from api.node.vm.views import harvest_vm

    admin = settings.VMS_DC_ADMIN
    main = settings.VMS_DC_MAIN
    # Admin DC and default DC should already exist (initial_data)
    admin_dc = Dc.objects.get_by_name(admin)
    default_dc = Dc.objects.get_by_name(main)
    # We need some request with admin DC - important for all subsequent commands
    request = get_dummy_request(admin_dc, method='POST', system_user=True)
    # All api calls will use the POST method...
    api_post = partial(_api_cmd, request, 'POST')
    # ...except net_manage, dns_record and dc_settings
    api_put = partial(_api_cmd, request, 'PUT')

    # Initialize images
    if images and isinstance(images, list):
        logger.warn('Initializing %d images', len(images))
        _init_images(head_node, images, default_dc, admin_dc)
    else:
        logger.error('Could not parse initial images or empty initial images')

    # Create DNS zone for the domain set during head node installation
    try:
        admin_zone = head_node.domain_name

        if admin_zone:
            api_post(dns_domain, admin_zone, owner=settings.ADMIN_USERNAME, dc_bound=False)
    except Exception as e:
        admin_zone = None
        logger.exception(e)

    # Setup miscellaneous stuff depending on admin network info
    try:
        mgmt_ifconfig = get_local_netinfo()
        mgmt_ifconfig['vlan_id'] = head_node.vlan_id
        mgmt_ip = mgmt_ifconfig['addr']

        try:
            mgmt_net = ipaddress.ip_network(u'%(network)s/%(netmask)s' % mgmt_ifconfig)
        except Exception as exc:
            logger.exception(exc)
        else:
            try:  # Create reverse dns domain
                ptr_zone = reverse_domain_from_network(mgmt_net)
                api_post(dns_domain, ptr_zone, owner=settings.ADMIN_USERNAME, dc_bound=False)
                api_post(dc_domain, ptr_zone, dc=main)
                api_post(dc_domain, ptr_zone, dc=admin)
            except Exception as exc:
                logger.exception(exc)
            else:
                # Set PTR zone for admin network
                mgmt_ifconfig['ptr_domain'] = ptr_zone

        # Change admin network subnet according to ip/netmask/gw on this machine (mgmt01.local)
        api_put(net_manage, settings.VMS_NET_ADMIN, dns_domain=admin_zone, **mgmt_ifconfig)

        # Change SITE_LINK and SITE_SIGNATURE both datacenters (#549, #551)
        site_link = 'https://%s' % mgmt_ip
        site_signature = settings.SITE_SIGNATURE.replace(settings.SITE_LINK, site_link)
        api_put(dc_settings, main, SITE_LINK=site_link, SITE_SIGNATURE=site_signature)
        api_put(dc_settings, admin, SITE_LINK=site_link, SITE_SIGNATURE=site_signature)
        _es_api_url(site_link)
    except Exception as e:
        logger.exception(e)

    # Add head node + all its storages into admin DC
    api_post(dc_node, head_node.hostname, strategy=DcNode.SHARED, add_storage=9, dc=admin)

    logger.warning('Admin datacenter "%s" was successfully initialized', admin_dc)

    # Harvest all VMs from head node into admin DC
    while True:
        ret = api_post(harvest_vm, head_node.hostname, dc=admin)

        if status.is_success(ret.status_code):
            logger.info('POST harvest_vm(%s) has started: %s', head_node.hostname, ret.data)
            break
        else:
            logger.error('POST harvest_vm(%s) has failed; retrying in 3 seconds', head_node.hostname)
            sleep(3)

    # The harvest is performing some other tasks asynchronously during which the node must stay in online state.
    # So let's sleep for some time to give the tasks some breathing space.
    logger.info('Sleeping for 60 seconds after admin datacenter initialization')
    sleep(60)

    # Let's update the default image server after we've harvested the VMS_VM_IMG01
    try:
        if Vm.objects.filter(uuid=settings.VMS_VM_IMG01).exists():
            vm_img01_uuid = settings.VMS_VM_IMG01
        else:
            vm_img01_uuid = None

        if settings.VMS_IMAGE_VM == vm_img01_uuid:
            logger.info('The current image server (VMS_IMAGE_VM) is already set to %s', vm_img01_uuid)
        else:
            api_put(dc_settings, main, VMS_IMAGE_VM=vm_img01_uuid)
    except Exception as e:
        logger.exception(e)

    # We can change the default resolvers after we've harvested the VMS_VM_DNS01 (#chili-831)
    try:
        try:
            vm_dns01_ip = Vm.objects.get(uuid=settings.VMS_VM_DNS01).ips[0]
        except Vm.DoesNotExist:
            logger.warning('DNS VM (%s) not found - using default DNS servers', settings.VMS_VM_DNS01)
        else:
            api_put(dc_settings, main, VMS_VM_RESOLVERS_DEFAULT=[vm_dns01_ip])
            api_put(dc_settings, admin, VMS_VM_RESOLVERS_DEFAULT=[vm_dns01_ip])
            api_put(net_manage, settings.VMS_NET_ADMIN, resolvers=[vm_dns01_ip])
            api_post(dns_record, settings.DNS_MGMT_DOMAIN, 0, name=settings.DNS_NAMESERVERS[0], type='A',
                     content=vm_dns01_ip)
    except Exception as e:
        logger.exception(e)

    # Initial user group zabbix synchronization
    mon_all_groups_sync.call(sender='init_mgmt')

    return ret
