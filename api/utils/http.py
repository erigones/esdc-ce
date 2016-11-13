from contextlib import closing
from requests import request
from requests.exceptions import InvalidURL, RequestException

from core.version import __version__

__all__ = ('HttpClientException', 'TooLarge', 'InvalidURL', 'HttpClient')

CHUNK_SIZE = 24
TIMEOUT = 5

HttpClientException = RequestException


class TooLarge(RequestException):
    pass


class HttpClient(object):
    """
    HTTP downloader.
    """
    USER_AGENT = 'esdc/%s' % __version__

    def __init__(self, url, validate_url=True):
        self.url = url

        if validate_url and not self.is_valid():
            raise InvalidURL('Invalid URL')

    def _request(self, method='get', timeout=TIMEOUT, max_size=None, **kwargs):
        headers = kwargs.pop('headers', {})
        headers['User-Agent'] = self.USER_AGENT

        if max_size:
            kwargs['stream'] = True

        if max_size:
            data_size = 0

            with closing(request(method, self.url, timeout=timeout, headers=headers, **kwargs)) as res:
                res.raise_for_status()
                content = []

                for chunk in res.iter_content(CHUNK_SIZE):
                    content.append(chunk)
                    data_size += CHUNK_SIZE

                    if data_size > max_size:
                        raise TooLarge('Response is too large')

                res._content = bytes().join(content)

        else:
            res = request(method, self.url, timeout=timeout, **kwargs)
            res.raise_for_status()

        return res

    def is_valid(self):
        url = self.url

        if not (url and (url.startswith('http://') or url.startswith('https://'))):
            return False

        return True

    def get(self, **kwargs):
        kwargs['method'] = 'get'

        return self._request(**kwargs)

    def head(self, **kwargs):
        kwargs['method'] = 'head'

        return self._request(**kwargs)
