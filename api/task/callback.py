from django.core.cache import cache
import requests

from que.tasks import get_task_logger
from api import serializers
from api.permissions import generate_random_security_hash, generate_security_hash
from core.version import __version__

logger = get_task_logger(__name__)

REQUEST_METHODS = (
    ('POST', 'POST'),
    ('GET', 'GET'),
    ('PUT', 'PUT'),
    ('DELETE', 'DELETE')
)

REQUEST_HEADERS = {
    'User-Agent': 'DanubeCloud/' + __version__,
}


class CallbackSerializer(serializers.Serializer):
    """
    User callback serializer.
    """
    cb_url = serializers.URLField()
    cb_method = serializers.ChoiceField(choices=REQUEST_METHODS, default='POST')


class UserCallback(object):
    """
    User callback associated with task ID.
    The callback is a dict with cb_method and cb_url keys (+optionally cb_log).
    """
    def __init__(self, task_id):
        self.task_id = task_id

    def save(self, callback, cb_log=True):
        callback['cb_log'] = cb_log
        cache.set(self.task_id, callback)

    def load(self):
        return cache.get(self.task_id)

    @staticmethod
    def generate_tokens(callback_key):
        """
        Function to generate security token
        """
        random_hash = generate_random_security_hash()

        return generate_security_hash(random_hash, callback_key), random_hash

    def request(self, callback, callback_key, payload):
        method, url = callback['cb_method'], callback['cb_url']
        payload['security_token'], payload['random_token'] = self.generate_tokens(callback_key)

        logger.info('UserCallback[%s] %s request to %s with payload %s', self.task_id, method, url, payload)
        r = requests.request(method, url, headers=REQUEST_HEADERS, json=payload)

        logger.info('UserCallback[%s] response %s: %s', self.task_id, r.status_code, r.reason)
        logger.debug('UserCallback[%s] response body: %s', self.task_id, r.text)
        r.raise_for_status()

        return r
