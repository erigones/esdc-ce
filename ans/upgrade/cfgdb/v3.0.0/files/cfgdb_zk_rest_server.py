#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import ssl
import json
import signal
import logging
import subprocess

try:
    # noinspection PyCompatibility,PyUnresolvedReferences
    import urlparse
except ImportError:
    # noinspection PyCompatibility,PyUnresolvedReferences
    from urllib import parse as urlparse

try:
    # noinspection PyCompatibility,PyUnresolvedReferences
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    # noinspection PyCompatibility,PyUnresolvedReferences
    from http.server import BaseHTTPRequestHandler, HTTPServer

PY3 = sys.version_info[0] >= 3

if PY3:
    string_types = (str,)
else:
    # noinspection PyUnresolvedReferences
    string_types = (basestring,)


logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s %(levelname)-8s %(name)s: %(message)s')
logger = logging.getLogger(__name__)


VERSION = '0.1'
DEFAULT_HTTP_ADDRESS = ''
DEFAULT_HTTP_PORT = 12181


class ValidationError(ValueError):
    def __init__(self, attr, detail, status=400):
        self.attr = attr
        self.detail = detail
        self.status = status

    @property
    def as_json(self):
        return {self.attr: self.detail}


# noinspection PyPep8Naming
class RESTRequestHandler(BaseHTTPRequestHandler):
    method = None
    _content = None

    @property
    def content(self):
        if self._content is None:
            content_length = int(self.headers.getheader('Content-Length', 0))

            if content_length:
                self._content = self.rfile.read(content_length)
            else:
                self._content = ''

        return self._content

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data))

    def parse_json_content(self):
        content = self.content

        if content:
            return json.loads(content)
        else:
            return {}

    def handle_request(self):
        raise NotImplementedError

    def _handle_request(self):
        try:
            self.handle_request()
        except ValidationError as exc:
            logger.exception(exc)
            self.send_json_response(exc.as_json, status=exc.status)
        except Exception as exc:
            logger.exception(exc)
            self.send_error(500, 'Internal Server Error')

    def do_GET(self):
        self.method = 'GET'
        self._handle_request()

    def do_POST(self):
        self.method = 'POST'
        self._handle_request()

    def do_PUT(self):
        self.method = 'PUT'
        self._handle_request()

    def do_DELETE(self):
        self.method = 'DELETE'
        self._handle_request()


class ZKRESTRequestHandler(RESTRequestHandler):
    default_string_max_length = 4019
    zk_data_size_limit = 2097152
    zk_commands = frozenset((
        'exists',
        'get',
        'ls',
        'lsr',
        'create',
        'creater',
        'set',
        'delete',
        'rm',
        'deleter',
        'rmr',
        'getacl',
        'setacl'
    ))
    method_to_zk_command = {
        'GET': 'get',
        'POST': 'create',
        'PUT': 'set',
        'DELETE': 'delete',
    }
    zk_servers = os.environ.get('ZK_REST_ZK_SERVERS', '127.0.0.1')
    zk_base_cmd = (os.environ.get('ZK_REST_ZK_CLI', 'zookeepercli'), '-servers', zk_servers)

    def version_string(self):
        return 'ZooKeeper REST Service / ' + VERSION

    @classmethod
    def validate_string_input(cls, attr, value, max_length=default_string_max_length):
        if not isinstance(value, string_types):
            raise ValidationError(attr, 'Invalid value.')

        if max_length and len(value) > max_length:
            raise ValidationError(attr, 'Too large.', status=413)

        return value

    def run_zk_cmd(self, command, node, data=None, force=False, username=None, password=None):
        cmd = list(self.zk_base_cmd)

        if force:
            cmd.append('-force')

        if username is not None:
            cmd.extend(('-auth_usr', self.validate_string_input('username', username)))

        if password is not None:
            cmd.extend(('-auth_pwd', self.validate_string_input('password', password)))

        cmd.extend(('-c', command, self.validate_string_input('node', node)))

        if data is not None:
            cmd.append(self.validate_string_input('data', data, max_length=self.zk_data_size_limit))

        logger.debug('Running command: %s', cmd)
        exc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        stdout, stderr = exc.communicate()
        res = {'returncode': exc.returncode, 'stdout': stdout.strip(), 'stderr': stderr.strip()}
        logger.info('Command "%s" finished with %s', cmd, res)

        return res

    def handle_request(self):
        url = urlparse.urlparse(self.path)
        qs = urlparse.parse_qs(url.query)
        zk_cmd = qs.get('cmd', None)

        if zk_cmd:
            zk_cmd = zk_cmd[0]
        else:
            zk_cmd = self.method_to_zk_command.get(self.method, None)

        logger.info('Got request: [%s %s]', zk_cmd, url.path)

        if not zk_cmd or zk_cmd not in self.zk_commands:
            logger.error('Request [%s %s] command is invalid', zk_cmd, url.path)
            self.send_json_response({'detail': 'Invalid command'}, status=400)
            return

        try:
            data = self.parse_json_content()

            if not isinstance(data, dict):
                raise TypeError
        except (TypeError, ValueError):
            logger.error('Request [%s %s] has invalid JSON content: "%s"', zk_cmd, url.path, self.content)
            self.send_json_response('Malformed request', status=400)
            return
        else:
            logger.debug('Request [%s %s] has JSON content: "%s"', zk_cmd, url.path, data)

        res = self.run_zk_cmd(
            zk_cmd,
            url.path,
            data=data.get('data', None),
            force=bool(data.get('force', False)),
            username=self.headers.get('zk-username', None),
            password=self.headers.get('zk-password', None)
        )

        if res['returncode'] == 0:
            status = 200
        else:
            if 'node does not exist' in res['stderr']:
                status = 404
            elif 'node already exists' in res['stderr']:
                status = 406
            else:
                status = 400

        logger.info('Request [%s %s] response: "%s"', zk_cmd, url.path, res)
        self.send_json_response(res, status=status)

    # noinspection PyPep8Naming
    def do_HEAD(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
        else:
            self.send_error(501, 'Unsupported method')


class ESDCZKRESTRequestHandler(ZKRESTRequestHandler):
    def version_string(self):
        return 'ESDC ' + ZKRESTRequestHandler.version_string(self)

    def handle_request(self):
        if self.path.startswith('/esdc'):
            ZKRESTRequestHandler.handle_request(self)
        else:
            self.send_json_response({'detail': 'Permission Denied'}, status=403)


def run_server(address=DEFAULT_HTTP_ADDRESS, port=DEFAULT_HTTP_PORT, ssl_cert=None, ssl_key=None, ca_certs=None,
               request_handler=ESDCZKRESTRequestHandler):
    http_server = HTTPServer((address, port), request_handler)

    if ssl_cert:
        http_server.socket = ssl.wrap_socket(http_server.socket, keyfile=ssl_key, certfile=ssl_cert, ca_certs=ca_certs,
                                             server_side=True)

    # noinspection PyUnusedLocal
    def stop_server(signum, frame):
        logger.info('Stopping HTTP server with signal %s', signum)
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, stop_server)
    signal.signal(signal.SIGTERM, stop_server)
    logger.info('Starting HTTP [ssl=%s] server at %s:%s', ssl_cert, address, port)

    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        http_server.shutdown()

    logger.info('Stopped HTTP server')
    http_server.server_close()


def main():
    run_server(
        address=os.environ.get('ZK_REST_HTTP_ADDRESS', DEFAULT_HTTP_ADDRESS),
        port=os.environ.get('ZK_REST_HTTP_PORT', DEFAULT_HTTP_PORT),
        ssl_cert=os.environ.get('ZK_REST_HTTP_SSL_CERT', None),
        ssl_key=os.environ.get('ZK_REST_HTTP_SSL_KEY', None),
        ca_certs=os.environ.get('ZK_REST_HTTP_CA_CERTS', None),
    )


if __name__ == '__main__':
    main()
