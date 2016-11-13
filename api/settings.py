"""
Default REST framework API settings.
"""
# Header encoding (see RFC5987)
HTTP_HEADER_ENCODING = 'iso-8859-1'

# Default datetime input and output formats
ISO_8601 = 'iso-8601'

DATE_FORMAT = ISO_8601
DATE_INPUT_FORMATS = (ISO_8601,)
DATETIME_FORMAT = ISO_8601
DATETIME_INPUT_FORMATS = (ISO_8601,)
TIME_FORMAT = ISO_8601
TIME_INPUT_FORMATS = (ISO_8601,)

URL_FIELD_NAME = 'url'
FORMAT_SUFFIX_KWARG = 'format'

NUM_PROXIES = None
DEFAULT_THROTTLE_RATES = {
    'anon': '30/minute',  # Can't throttle more because of FastSpring
    'user': '45/minute',
}

DEFAULT_VERSION = None
ALLOWED_VERSIONS = None
VERSION_PARAM = 'version'
