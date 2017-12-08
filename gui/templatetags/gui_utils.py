from django import template
from django.conf import settings as _settings
from django.http import QueryDict
from django.utils.dateparse import parse_datetime
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from json import dumps
from datetime import datetime, timedelta

import re
import pytz
# noinspection PyCompatibility
import ipaddress
import markdown

from api.mon.backends.zabbix.base import ZabbixMediaContainer
from api.utils.encoders import JSONEncoder
from pdns.models import Record

register = template.Library()


# noinspection PyPep8Naming
@register.filter
def record_PTR(vm, ip):
    if ip and vm.dc.settings.DNS_ENABLED:
        return Record.get_record_PTR(ip)
    else:
        return None


@register.filter
def get_item(obj, item):
    return obj[item]


@register.filter
def keyvalue(dictionary, key):
    return dictionary.get(key, '')


@register.filter
def keyvalue_lower(dictionary, key):
    try:
        key = key.lower()
    except AttributeError:
        pass

    return dictionary.get(key, '')


@register.filter
def keyvalue_zero(dictionary, key):
    return dictionary.get(key, 0)


@register.filter
def dtparse(s):
    return parse_datetime(s)


@register.filter
def dttimestamp(s):
    return datetime.fromtimestamp(s)


@register.filter
def mon_get_age(s):
    delta = datetime.now() - datetime.fromtimestamp(s)
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    if days:
        return '%dd %dh %dm' % (days, hours, minutes)
    else:
        return '%dh %dm %ds' % (hours, minutes, seconds)


@register.filter
def mon_severity(s):
    return ZabbixMediaContainer.get_severity(s)


@register.filter
def timeformat(seconds):
    if seconds is None:
        return ''

    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return '%d:%02d:%02d' % (h, m, s)


@register.filter
def uptime(boottime):
    up = int(datetime.utcnow().strftime('%s')) - int(boottime)

    if up < 0:
        up = 0

    return timedelta(seconds=up)


def _iconify(icon, text):
    return '<span class="icontext"><i class="icon-%s"></i> %s</span>' % (icon, conditional_escape(text))


def _iconify_list(icon, items):
    return mark_safe(', '.join(sorted(_iconify(icon, i) for i in items)))


@register.filter
def tagify(tags):
    return _iconify_list('tag', tags.names())


@register.filter
def dcify(dcs):
    return _iconify_list('cloud', dcs)


@register.filter
def userify(users):
    return _iconify_list('user', users)


@register.filter
def groupify(groups):
    return _iconify_list('group', groups)


@register.filter
def iconify(items_list, icon):
    return _iconify_list(icon, items_list)


@register.filter
def tagclass(tags):
    return ' '.join('tag-' + str(i.id) for i in tags.all())


@register.filter
def multiply(value, arg):
    if value in (None, ''):
        return ''
    return int(value) * int(arg)


@register.filter
def divide(value, arg):
    if value in (None, ''):
        return ''
    return int(value) / int(arg)


@register.filter
def mb_to_gb(value):
    if value in (None, ''):
        return ''
    return round(float(value) / 1024, 1)


@register.filter
def b_to_mb(value):
    if value in (None, ''):
        return ''
    return round(float(value) / 1048576, 1)


@register.filter
def minus(value, arg=1):
    try:
        return int(value) - int(arg)
    except ValueError:
        return 0


@register.filter
def json(value, arg=0):
    """Unsafe json filter"""
    return dumps(value, indent=arg, cls=JSONEncoder)


def _jsondata(value):
    return mark_safe(conditional_escape(dumps(value, indent=None, cls=JSONEncoder)))


@register.filter
def jsondata(value):
    """Better json filter. Use for dict output by default"""
    return _jsondata(value)


@register.simple_tag(takes_context=True)
def form_data(context, ser_form, obj):
    """json output for SerializerForm._initial_data dict"""
    # noinspection PyProtectedMember
    return _jsondata(ser_form._initial_data(context['request'], obj))


@register.filter
def append(value, item):
    value.append(item)
    return ''


@register.assignment_tag
def empty_list():
    return []


@register.filter
def pop(value, item):
    return value.pop(item, {})


@register.filter
def urlfy(value):
    return value.replace('.', '-').lower()


@register.assignment_tag
def settings(option):
    return getattr(_settings, option, '')


@register.filter
def cidr(ipaddr, netmask):
    try:
        ip = ipaddress.ip_interface(u'%s/%s' % (ipaddr, netmask))
        return str(ip).replace('/', ' / ')
    except ValueError:
        return ipaddr + ' / ' + netmask


@register.inclusion_tag('gui/paginator.html', takes_context=True)
def paginator(context, pager=None, adjacent_pages=3):
    if not pager:
        pager = context['pager']

    cur = pager.number
    show = pager.paginator.page_range[:cur + adjacent_pages]

    if cur > adjacent_pages:
        show = show[cur - adjacent_pages - 1:]

    first = show[0]
    last = show[-1]

    qs = context['request'].GET.copy()
    qs.pop('page', None)
    qs.pop('_', None)
    qs = qs.urlencode()

    if qs:
        qs += '&'

    return {
        'pager': pager,
        'querystring': qs,
        'show_pages': show,
        'show_first': first != 1,
        'show_last': last != pager.paginator.num_pages,
        'dots_prev': first > adjacent_pages,
        'dots_next': last < pager.paginator.num_pages - 1,
    }


@register.filter
def local_schedule(schedule_or_webdata, tz_name):
    if isinstance(schedule_or_webdata, dict):
        schedule = schedule_or_webdata['schedule'].split()
        is_dict = True
    else:
        schedule = schedule_or_webdata.split()
        is_dict = False

    try:
        hour = schedule[1]
        assert '*' not in hour
    except (IndexError, AssertionError):
        return schedule_or_webdata

    try:
        tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        return schedule_or_webdata

    def to_local(match):
        num = int(match.group(0))
        now = datetime.utcnow().replace(hour=num, tzinfo=pytz.utc)
        return str(tz.normalize(now).hour)

    try:
        schedule[1] = re.sub(r'(\d+)', to_local, hour)
    except ValueError:
        return schedule_or_webdata
    else:
        new_schedule = ' '.join(schedule)

    if is_dict:
        schedule_or_webdata['schedule'] = new_schedule
        return schedule_or_webdata
    return new_schedule


@register.assignment_tag(takes_context=True)
def is_admin(context, user, dc=None):
    """Check if user is DC admin"""
    return user.is_admin(context['request'], dc=dc)


@register.filter
def img_ns_status_display(img, ns):
    img_ns_status = img.get_ns_status(ns)
    return {'status': img_ns_status, 'display': dict(img.NS_STATUS).get(img_ns_status)}


@register.filter
def qs_set(query_string, param):
    qs = QueryDict(query_string, mutable=True)
    qs[param] = 1
    return qs.urlencode()


@register.filter
def qs_del(query_string, param):
    qs = QueryDict(query_string, mutable=True)
    qs.pop(param, None)
    return qs.urlencode()


@register.filter(is_safe=True)
def markdownify(text):
    safe_text = conditional_escape(text)

    # noinspection PyBroadException
    try:
        safe_text = markdown.markdown(safe_text, extensions=('markdown.extensions.tables',
                                                             'markdown.extensions.fenced_code'))
    except Exception:
        """We want too broad exception as we don't know what can get wrong in the markdown library."""
        pass

    return mark_safe(safe_text)
