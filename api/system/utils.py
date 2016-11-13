import netifaces
# noinspection PyCompatibility
import ipaddress


def _get_local_netinfo(iface):
    ifconfig = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]
    ifconfig['gateway'] = netifaces.gateways()['default'][netifaces.AF_INET][0]
    ip = ipaddress.ip_interface(u'%s/%s' % (ifconfig['addr'], ifconfig['netmask']))
    ifconfig['network'] = str(ip.network.network_address)
    ifconfig['iface'] = iface

    return ifconfig


def get_local_netinfo(iface=None):
    if not iface:
        try:
            iface = netifaces.gateways()['default'][netifaces.AF_INET][1]
        except (KeyError, IndexError):
            raise OSError('Main network interface was not found')

    if iface not in netifaces.interfaces():
        raise ValueError('Network interface "%s" is not available on this system' % iface)

    try:
        return _get_local_netinfo(iface)
    except (KeyError, IndexError):
        raise OSError('Network information for interface "%s" is not available' % iface)
