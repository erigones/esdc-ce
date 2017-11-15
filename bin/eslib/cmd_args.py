import re
import json
from argparse import ArgumentTypeError, FileType

from . import PY3

RE_ASCII = re.compile(r'^[a-zA-Z0-9:_.-]+$')
RE_UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


if PY3:
    long_int = int
else:
    long_int = long


def t_int(value):
    """Integer validator"""
    try:
        return str(long_int(value))
    except (TypeError, ValueError):
        raise ArgumentTypeError('Invalid number: "%s"' % value)


def t_ascii(value):
    """Ascii validator"""
    if RE_ASCII.match(value):
        return value

    raise ArgumentTypeError('Invalid parameter: "%s"' % value)


def t_uuid(value):
    """UUID validator"""
    if RE_UUID.match(value):
        return value

    raise ArgumentTypeError('Invalid uuid: "%s"' % value)


def t_file(value):
    fp = filter(None, value.split('/'))

    try:
        map(t_ascii, fp)
    except ArgumentTypeError:
        pass

    return value


def t_dataset(value):
    """Dataset validator"""
    ds = value.split('/')

    if len(ds) > 1:
        try:
            map(t_ascii, ds)
        except ArgumentTypeError:
            pass
        else:
            return value

    raise ArgumentTypeError('Invalid dataset: "%s"' % value)


def t_python_fun(string):
    """Return imported python function"""
    try:
        string = string.strip()
        x = string.split(':')
        mod_name, fun_name = x[0], x[1]
        fun_args = tuple(x[2:])
    except (IndexError, ValueError):
        raise ArgumentTypeError('Invalid value: "%s"' % string)

    try:
        mod = __import__(mod_name, fromlist=(fun_name,))
        fun = getattr(mod, fun_name)
    except (AttributeError, ImportError) as exc:
        raise ArgumentTypeError('Cannot import "%s": %s' % (string, exc))

    fun.orig_name = string
    fun.args = fun_args

    return fun


class JSONFileType(FileType):
    """Return loaded json from file"""
    def __call__(self, filename):
        fp = super(JSONFileType, self).__call__(filename)

        # noinspection PyBroadException
        try:
            return json.loads(fp.read())
        except (IOError, OSError):
            msg = 'Could not read file'
        except Exception:
            msg = 'Invalid json'

        raise ArgumentTypeError(msg)
