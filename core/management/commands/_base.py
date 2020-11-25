from __future__ import absolute_import
from __future__ import print_function

import os
import getpass

from optparse import Option
from subprocess import Popen, PIPE, STDOUT
from contextlib import contextmanager

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
# noinspection PyUnresolvedReferences
from django.utils.six.moves import input

from django.conf import settings

from ._color import no_color, shell_color


@contextmanager
def lcd(dirpath):
    """A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit."""
    prev_cwd = os.getcwd()
    dirpath = dirpath.replace(' ', '\ ')  # noqa: W605

    if not dirpath.startswith('/') and not dirpath.startswith('~'):
        new_cwd = os.path.join(os.path.abspath(os.getcwd()), dirpath)
    else:
        new_cwd = dirpath

    os.chdir(new_cwd)

    try:
        yield
    finally:
        os.chdir(prev_cwd)


CommandOption = Option


# noinspection PyAbstractClass
class DanubeCloudCommand(BaseCommand):
    """
    Base class for all Danube Cloud commands.
    """
    settings = settings
    DEFAULT_BRANCH = 'master'
    PROJECT_DIR = settings.PROJECT_DIR
    PROJECT_NAME = 'esdc-ce'
    CTLSH = os.path.join(PROJECT_DIR, 'bin', 'ctl.sh')

    cmd_sha = 'git log --pretty=oneline -1 | cut -d " " -f 1'
    cmd_tag = 'git symbolic-ref -q --short HEAD || git describe --tags --exact-match'

    default_verbosity = 1
    verbose = False
    strip_newline = False
    colors = shell_color
    options = ()

    _local_username = None

    def add_arguments(self, parser):
        parser.add_argument('--no-newline',
                            action='store_true',
                            dest='no_newline',
                            default=False,
                            help='Strip newlines from output')

    def get_version(self):
        """This isn't used anywhere"""
        from core.version import __version__
        return 'Danube Cloud %s' % __version__

    def get_git_version(self):
        with lcd(self.PROJECT_DIR):
            output = self.local(self.cmd_tag, capture=True)

            if isinstance(output, (bytes, bytearray)):
                output = output.decode("utf-8")

            _tag = output.strip().split('/')[-1]
            _sha = output.strip()

            return _tag, _sha

    def execute(self, *args, **options):
        """Set some default attributes before calling handle()"""
        self.verbose = int(options.get('verbosity', self.default_verbosity)) >= self.default_verbosity
        self.strip_newline = options.pop('no_newline', False)

        if options.get('no_color'):
            options['no_color'] = True
            self.colors = no_color

        return super(DanubeCloudCommand, self).execute(*args, **options)

    @staticmethod
    def confirm(question, default='yes'):
        """
        http://stackoverflow.com/questions/3041986/python-command-line-yes-no-input
        Ask a yes/no question via raw_input() and return their answer.

        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).

        The "answer" return value is one of "yes" or "no".
        """
        valid = {"yes": True, "y": True, "no": False, "n": False}

        if default is None:
            prompt = " [y/n] "
        elif default == "yes":
            prompt = " [Y/n] "
        elif default == "no":
            prompt = " [y/N] "
        else:
            raise ValueError("invalid default answer: '%s'" % default)

        while True:
            print(question + prompt, end='')
            choice = input().lower()

            if default is not None and choice == '':
                return valid[default]
            elif choice in valid:
                return valid[choice]
            else:
                print("Please respond with 'yes' or 'no' (or 'y' or 'n').")

    @staticmethod
    def _path(*args):
        """Helper method used by lot of commands"""
        return os.path.join(*args)

    @staticmethod
    def _path_exists(basepath, *args):
        """Helper method used by lot of commands"""
        return os.path.exists(os.path.join(basepath, *args))

    @property
    def local_username(self):
        """Used by the command_prompt property"""
        if self._local_username is None:
            self._local_username = getpass.getuser()
        return self._local_username

    @property
    def command_prompt(self):
        """Return command prompt: [user@localhost CWD] """
        return '%s%s:%s]' % (self.colors.reset('['), self.colors.cyan('%s@localhost' % self.local_username),
                             self.colors.blue(os.path.realpath(os.getcwd())))

    def display(self, text, stderr=False, color=None, ending=None):
        """Display message on stdout or stderr"""
        if self.strip_newline:
            text = text.strip('\n')

        if color:
            color_fun = getattr(self.colors, color, None)
        else:
            color_fun = None

        if stderr:
            self.stderr.write(text, style_func=color_fun, ending=ending)
        else:
            self.stdout.write(text, style_func=color_fun, ending=ending)

    def local(self, command, capture=False, stderr_to_stdout=True, shell=True, echo_command=None,
              raise_on_error=True):
        """Run a command on the local system."""
        if echo_command is None and self.verbose:
            echo_command = True

        if capture:
            out_stream = PIPE

            if stderr_to_stdout:
                err_stream = STDOUT
            else:
                err_stream = PIPE
        else:
            out_stream = err_stream = None

        if echo_command:
            self.display('%s %s' % (self.command_prompt, command), stderr=True)

        p = Popen(command, shell=shell, stdout=out_stream, stderr=err_stream, close_fds=True, bufsize=-1)
        stdout, stderr = p.communicate()

        if raise_on_error and p.returncode != 0:
            raise CommandError('Command "%s" returned with non-zero exit code (%d)' % (command, p.returncode))

        if capture:
            if stderr_to_stdout:
                return stdout
            else:
                return stdout, stderr

        return p.returncode

    def managepy(self, cmd, *args, **kwargs):
        """Run Django management command. WARNING: the kwargs options have usually different names
        than the command line parameters - check the source code of the specific django command for more info"""
        if kwargs.pop('echo_command', self.verbose):
            params = ' '.join(['--%s=%s' % (k, repr(v)) for k, v in kwargs.items()] + list(args))
            self.display('%s manage.py %s %s' % (self.command_prompt, cmd, params), stderr=True)

        return call_command(cmd, *args, **kwargs)

    def ctlsh(self, *cmd, **kwargs):
        """Run the ctl.sh script"""
        cmd_desc = 'ctl.sh ' + ' '.join(cmd)

        if kwargs.get('echo_command', self.verbose):
            self.display('%s %s' % (self.command_prompt, cmd_desc), stderr=True)

        cmd = (self.CTLSH,) + cmd
        p = Popen(cmd, shell=False, close_fds=True, bufsize=-1)
        p.communicate()

        if kwargs.get('raise_on_error', True) and p.returncode != 0:
            raise CommandError('Command "%s" returned with non-zero exit code (%d)' % (cmd_desc, p.returncode))

        return p.returncode
