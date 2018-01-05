from django.contrib.gis.geoip import GeoIP
from django.utils.translation import get_language
from django.core.cache import cache

from logging import getLogger
# noinspection PyProtectedMember
from phonenumbers.data import _COUNTRY_CODE_TO_REGION_CODE
from pytz import country_timezones

logger = getLogger(__name__)


def get_client_ip(request):
    """
    http://stackoverflow.com/questions/4581789/how-do-i-get-user-ip-address-in-django
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')

    return ip


def get_geoip(request):
    """
    Return GeoIP.country dictionary, queried by request IP address.
    """
    ip = get_client_ip(request)
    geoip = GeoIP()

    if ip:
        ret = geoip.country(ip)
        logger.debug('GeoIP detection on IP: %s with result: %s', ip, ret)
        return ret
    else:
        return {'country_code': None, 'country_name': None}


def get_time_zone(country_code):
    """
    Return time zone for country.
    """
    try:
        return country_timezones[country_code][0]
    except KeyError:
        return None


def get_phone_prefix(country_code):
    """
    Return international phone country prefix.
    """
    # noinspection PyCompatibility
    for prefix, countries in _COUNTRY_CODE_TO_REGION_CODE.iteritems():
        if country_code in countries:
            return '+%d' % prefix

    return ''


def get_initial_data(request):
    """Initial data for registration page"""
    dc_settings = request.dc.settings

    initial = {
        'language': get_language(),
        'country': dc_settings.PROFILE_COUNTRY_CODE_DEFAULT,
        'phone': dc_settings.PROFILE_PHONE_PREFIX_DEFAULT,
        'time_zone': dc_settings.PROFILE_TIME_ZONE_DEFAULT,
    }

    # This code should be bullet proof. We don't want to fail a registration because of some geo detection.
    try:
        country = get_geoip(request)['country_code']
        if not country:
            country = dc_settings.PROFILE_COUNTRY_CODE_DEFAULT

        phone = get_phone_prefix(country)
        if not phone:
            phone = dc_settings.PROFILE_PHONE_PREFIX_DEFAULT

        time_zone = get_time_zone(country)
        if not time_zone:
            time_zone = dc_settings.PROFILE_TIME_ZONE_DEFAULT
    except Exception as ex:
        logger.error('Registration GEO detection problem')
        logger.exception(ex)
    else:
        initial['phone'] = phone
        initial['country'] = country
        initial['timezone'] = time_zone

    return initial


def generate_key(request, key, view_type):
    """
    Generate key from username unique per type, and return default timeout in seconds
    """
    if view_type == 'login':
        return 'delay_login__' + get_client_ip(request) + '_' + key, 45
    elif view_type == 'forgot':
        return 'delay_forgot_password__' + get_client_ip(request) + '_' + key, 150
    else:
        return 'delay_generic__' + get_client_ip(request) + '_' + key, 60


def get_attempts_from_cache(key):
    attempts = cache.get(key)
    if attempts:
        return int(attempts)
    return 0


def set_attempts_to_cache(key, timeout=30):
    attempts = get_attempts_from_cache(key) + 1
    timeout *= attempts
    cache.set(key, attempts, timeout)
    return attempts, timeout


def clear_attempts_cache(request, key):
    gen_key, timeout = generate_key(request, key, 'login')
    cache.delete(gen_key)
    gen_key, timeout = generate_key(request, key, 'forgot')
    cache.delete(gen_key)
