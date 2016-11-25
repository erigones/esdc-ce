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
from vms.models import Dc, Image, Vm

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

    return out


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


def _init_images(images, default_dc, admin_dc):
    """Import manifests of initial images"""
    for manifest in images:
        try:
            img = Image(uuid=manifest['uuid'])
            img.owner_id = settings.ADMIN_USER
            img.name = img.alias = manifest['name']
            img.version = manifest['version']
            img.ostype = Image.os_to_ostype(manifest)
            img.size = int(manifest.get('image_size', 1024))
            img.desc = manifest.get('desc', '')[:128]
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
        except Exception as ex:
            logger.exception(ex)
            logger.error('Could not initialize image from manifest: %s', manifest)
            continue
        else:
            logger.info('Added initial image %s (%s (%s))', img.uuid, img.name, img.version)
            img.dc.add(admin_dc)

            if not internal:
                img.dc.add(default_dc)


def init_mgmt(head_node, images=None):
    """
    Initialize the system and create the "admin" datacenter.
    """
    from api.dc.views import dc_node, dc_settings, dc_domain
    from api.network.base.views import net_manage
    from api.dns.domain.views import dns_domain
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
        _init_images(images, default_dc, admin_dc)
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
    api_post(dc_node, head_node.hostname, strategy=1, add_storage=9, dc=admin)

    logger.warning('Admin datacenter "%s" was successfully initialized', admin_dc)

    # Harvest all VMs from head node into admin DC
    ret = api_post(harvest_vm, head_node.hostname, dc=admin)
    # The harvest is performing some other tasks asynchronously during which the node must stay in online state.
    # So let's sleep for some time to give the tasks some breathing space.
    logger.info('Sleeping for 60 seconds after admin datacenter initialization')
    sleep(60)

    # We can change the default resolvers after we've harvested the VMS_VM_DNS01 (#831)
    try:
        vm_dns01_ip = Vm.objects.get(uuid=settings.VMS_VM_DNS01).ips[0]
        api_put(dc_settings, main, VMS_VM_RESOLVERS_DEFAULT=[vm_dns01_ip])
        api_put(dc_settings, admin, VMS_VM_RESOLVERS_DEFAULT=[vm_dns01_ip])
    except Exception as e:
        logger.exception(e)

    return ret
