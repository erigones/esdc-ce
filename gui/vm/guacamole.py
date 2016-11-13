from django.conf import settings
from django.core.cache import caches
from django.utils.six import iteritems
from logging import getLogger

import requests
import requests.exceptions
import string
import random
import socket


logger = getLogger(__name__)


def random_password(minlength=20, maxlength=30):
    """
    Generate random string used as password.
    """
    length = random.randint(minlength, maxlength)
    letters = string.ascii_letters + string.digits
    return ''.join([random.choice(letters) for _ in range(length)])


def _test_vnc(host, port, timeout=3):
    """
    Test VNC connection.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.connect((host, port))

        if sock.recv(1024).startswith('RFB'):
            return True
    except (socket.error, socket.timeout, socket.herror, socket.gaierror) as err:
        logger.warning('Error "%s" when testing VNC on "%s:%s"', err, host, port)

    finally:
        sock.close()

    return False


class Guacamole(object):
    """
    Manipulate guacamole authorization from django.
    """

    def __init__(self, request, vm=None, username=None, password=None, save_password=False, load_password=False):
        """
        :param request: django request object.
        :param vm: vm object or list of vm objects (queryset). If it's a object
        it will be turned into a list.
        :param username: if not specified it will be set to the username
        attribute of request.user object.
        :param password: if not specified it will be auto generated.
        :param save_password: if True, then save the password in the
        request.session object.
        :param load_password: if True, then load the password from the
        request.session object.
        """
        self.auth = None
        self.tree = None
        self.request = request

        self.vm = vm
        if self.vm and not hasattr(self.vm, '__iter__'):
            self.vm = [vm]

        self.usr = username
        if not self.usr:
            self.usr = request.user.username

        self.key = settings.GUACAMOLE_KEY + self.usr

        self.pwd = password
        if not self.pwd:
            if load_password:
                self.pwd = self.request.session.get(self.key, random_password())
            else:
                self.pwd = random_password()

        if save_password:
            self.request.session[self.key] = self.pwd

    def __set_tree(self):
        self.tree = {}

    def __set_auth(self):
        self.tree['password'] = self.pwd

    def __set_vm(self):
        for i in self.vm:
            self.tree[i.hostname] = {
                'protocol': 'vnc',
                'hostname': i.node.address,
                'port': i.vnc_port
            }

    @classmethod
    def test_vnc(cls, vm, timeout=2):
        """
        Test VNC connection on VM.
        """
        return _test_vnc(vm.node.address, vm.vnc_port, timeout=timeout)

    def usermap(self):
        """
        Generate the user-mapping XML and return it along with the key string.
        """
        logger.debug('Creating guacamole user-mapping for user %s.', self.usr)
        self.__set_tree()
        self.__set_auth()

        if self.vm:
            self.__set_vm()

        return self.key, self.tree

    def login(self, save_cookie=True):
        """
        Perform a login to guacamole by issuing a POST request to /api/tokens.
        """
        logger.info('Performing guacamole login of user %s.', self.usr)
        exc = None
        r = None

        try:
            r = requests.post(
                settings.GUACAMOLE_URI + '/api/tokens',
                data={'username': self.usr, 'password': self.pwd},
                headers={'User-Agent': settings.GUACAMOLE_USERAGENT},
                timeout=settings.GUACAMOLE_TIMEOUT,
                allow_redirects=False
            )
        except requests.exceptions.RequestException as exc:
            logger.exception(exc)

        if exc is None and r and r.status_code == 200 and settings.GUACAMOLE_COOKIE in r.cookies:
            token = r.json().get('authToken', '')
            cookie = r.cookies[settings.GUACAMOLE_COOKIE]
            logger.info('User %s got guacamole cookie=%s and token=%s.', self.usr, cookie, token)

            if save_cookie:
                self.request.session[settings.GUACAMOLE_COOKIE] = cookie
                self.request.session[settings.GUACAMOLE_TOKEN] = token

            res = {
                'token': token,
                'cookie': {
                    'key': settings.GUACAMOLE_COOKIE,
                    'value': cookie,
                    'path': settings.GUACAMOLE_COOKIEPATH,
                    'domain': settings.GUACAMOLE_COOKIEDOMAIN,
                    'httponly': False
                }
            }
        else:
            logger.error('User %s could not login to guacamole, response="%r".', self.usr, exc or r.text)
            res = {}

        return res

    def logout(self):
        """
        Perform a logout from guacamole by issuing a DELETE request to /api/tokens/<token>.
        """
        session = self.request.session
        token = ''
        logger.info('Performing guacamole logout of user %s.', self.usr)

        if settings.GUACAMOLE_COOKIE in session and settings.GUACAMOLE_TOKEN in session:
            token = session[settings.GUACAMOLE_TOKEN]

            try:
                r = requests.delete(
                    settings.GUACAMOLE_URI + '/api/tokens/' + token,
                    cookies={settings.GUACAMOLE_COOKIE: session[settings.GUACAMOLE_COOKIE]},
                    headers={'User-Agent': settings.GUACAMOLE_USERAGENT},
                    timeout=settings.GUACAMOLE_TIMEOUT,
                    allow_redirects=False
                )
                r.raise_for_status()
            except requests.exceptions.RequestException as exc:
                logger.exception(exc)
                logger.error('User %s could not logout from guacamole (%r).', self.usr, exc)
        else:
            logger.info('User %s has no guacamole cookie and/or token.', self.usr)

        return {
            'token': token,
            'cookie': {
                'key': settings.GUACAMOLE_COOKIE,
                'path': settings.GUACAMOLE_COOKIEPATH,
            }
        }


class GuacamoleAuth(Guacamole):
    """
    Manipulate guacamole-auth-redis keys.
    """
    redis = caches['redis'].master_client

    def set_auth(self):
        """
        Create Guacamole usermap and store it in redis.
        """
        username, configs = self.usermap()
        pipe = self.redis.pipeline()

        pipe.hset(username, 'password', configs.pop('password', None))

        for key, cfg in iteritems(configs):
            val = '\n'.join([str(i) + '=' + str(j) for i, j in iteritems(cfg)])
            pipe.hset(username, key, val)

        return pipe.execute()

    def del_auth(self):
        """
        Remove Guacamole usermap from redis.
        """
        return self.redis.delete(self.key)
