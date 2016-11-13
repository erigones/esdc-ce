def _color(code):
    # noinspection PyUnusedLocal
    def inner(self, text, bold=False):
        c = code
        if bold:
            c = '1;%s' % c
        return '\033[%sm%s\033[0m' % (c, text)
    return inner


class NoColor(object):
    """
    Dummy color function.
    """
    # noinspection PyUnusedLocal
    def __getattr__(self, item):
        return lambda text: text


class ShellColor(object):
    """
    Bash colors.
    """
    red = _color(31)
    green = _color(32)
    yellow = _color(33)
    blue = _color(34)
    magenta = _color(35)
    cyan = _color(36)
    white = _color(37)
    reset = _color(0)


no_color = NoColor()
shell_color = ShellColor()
