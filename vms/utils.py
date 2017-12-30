import json
import re
import collections

from django.utils.datastructures import SortedDict
from django.utils.six import iteritems
from frozendict import frozendict

# shameless copy paste from json/decoder.py
FLAGS = re.VERBOSE | re.MULTILINE | re.DOTALL
WHITESPACE = re.compile(r'[ \t\n\r]*', FLAGS)


class AttrDict(dict):
    """
    Dict with class style attribute access.
    """
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class FrozenAttrDict(frozendict):
    """
    Frozendict with class style attribute access.
    """
    __getattr__ = frozendict.__getitem__


class DefAttrDict(AttrDict):
    """
    AttrDict with support for default values, which must be a AttrDict.
    """
    def __init__(self, data, defaults=None):
        super(DefAttrDict, self).__init__(data)
        if defaults is None:
            defaults = AttrDict()
        self.__defaults__ = defaults

    def __getattr__(self, key):
        try:
            return super(DefAttrDict, self).__getattr__(key)
        except KeyError:
            return getattr(self.__defaults__, key)

    def __getitem__(self, key):
        try:
            return super(DefAttrDict, self).__getitem__(key)
        except KeyError:
            return getattr(self.__defaults__, key)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except (KeyError, AttributeError):
            return default


class PickleDict(dict):
    """
    Used for vm.json or vm.json_active property.
    """
    def __unicode__(self):
        return self.dump()

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        self.__dict__ = state

    @classmethod
    def load(cls, string):
        # noinspection PyArgumentList
        pickle_dict = cls(json.loads(string))

        # Related to https://github.com/joyent/smartos-live/pull/313
        for nic in pickle_dict.get('nics', ()):
            if nic.get('allowed_ips', None) == ['']:
                nic['allowed_ips'] = []

        return pickle_dict

    def dump(self):
        return json.dumps(self, indent=4)

    def update2(self, d2):
        """
        Recursive dict.update() - http://stackoverflow.com/a/3233356
        """
        def update(d, u):
            for k, v in iteritems(u):
                if isinstance(v, collections.Mapping):
                    r = update(d.get(k, {}), v)
                    d[k] = r
                else:
                    d[k] = u[k]

            return d

        # noinspection PyMethodFirstArgAssignment,PyUnusedLocal
        self = update(self, d2)

        return None


class SortedPickleDict(SortedDict, PickleDict):
    pass


class ConcatJSONDecoder(json.JSONDecoder):
    """
    http://stackoverflow.com/a/8730674
    """
    def decode(self, s, _w=WHITESPACE.match):
        s_len = len(s)
        objs = []
        end = 0

        while end != s_len:
            obj, end = self.raw_decode(s, idx=_w(s, end).end())
            end = _w(s, end).end()
            objs.append(obj)

        return objs
