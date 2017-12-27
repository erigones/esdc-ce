from frozendict import frozendict
from zabbix_api import ZabbixAPI

from api.mon.backends.zabbix.containers.base import ZabbixBaseContainer


class ZabbixMediaContainer(ZabbixBaseContainer):
    """
    Container class for the Zabbix HostGroup object.
    """
    ZABBIX_ID_ATTR = 'mediaid'

    SEVERITY_NOT_CLASSIFIED = 0
    SEVERITY_INFORMATION = 1
    SEVERITY_WARNING = 2
    SEVERITY_AVERAGE = 3
    SEVERITY_HIGH = 4
    SEVERITY_DISASTER = 5
    SEVERITIES = (
        SEVERITY_NOT_CLASSIFIED, SEVERITY_INFORMATION, SEVERITY_WARNING, SEVERITY_AVERAGE, SEVERITY_HIGH,
        SEVERITY_DISASTER
    )

    # TODO Time is in UTC and therefore we should adjust this for the user's timezone
    PERIOD_DEFAULT_WORKING_HOURS = '1-5,09:00-18:00'
    PERIOD_DEFAULT = '1-7,00:00-24:00'

    MEDIA_TYPES = frozendict({
        'email': 'E-mail',
        'phone': 'SMS',
        'jabber': 'Ludolph',
    })

    def __init__(self, media_type, sendto, severities=SEVERITIES, period=PERIOD_DEFAULT, enabled=True, **kwargs):
        try:
            self.media_type_desc = self.MEDIA_TYPES[media_type]
        except KeyError:
            raise ValueError('Unsupported media type')

        self.media_type = media_type
        self.sendto = sendto
        self.severities = severities
        self.period = period
        self.enabled = enabled
        super(ZabbixMediaContainer, self).__init__('{}:{}'.format(media_type, sendto), **kwargs)

    @classmethod
    def generate_media_severity(cls, active_severities):
        """
        :param active_severities: (SEVERITY_WARNING, SEVERITY_HIGH)
        :return: number to be used as input for media.severity
        """
        result = 0

        for severity in active_severities:
            assert severity in cls.SEVERITIES
            result += 2 ** severity

        return result

    @staticmethod
    def get_severity(s):
        return ZabbixAPI.get_severity(s)

    @classmethod
    def extract_sendto_from_user(cls, media_type, user):
        if media_type not in cls.MEDIA_TYPES:
            raise ValueError('Unsupported media type')

        return getattr(user.userprofile, 'alerting_' + media_type)

    @classmethod
    def fetch_media_type_id(cls, zapi, media_type_desc):
        params = dict(filter={'description': media_type_desc})
        response = cls.call_zapi(zapi, 'mediatype.get', params=params)
        media_type_id = int(cls.parse_zabbix_get_result(response, 'mediatypeid'))  # May raise RemoteObjectDoesNotExist

        return media_type_id

    def to_zabbix_data(self):
        media_type_id = self.fetch_media_type_id(self._zapi, self.media_type_desc)

        return {
            'mediatypeid': media_type_id,
            'sendto': self.sendto,
            'period': self.period,
            'severity': self.generate_media_severity(self.severities),
            'active': self.trans_bool_inverted(self.enabled),
        }
