from .build import Command as BuildCommand
from ._base import CommandOption


class Command(BuildCommand):
    help = 'Install and build the whole application, and prepare the database for an initial start.'

    options = BuildCommand.options + (
        CommandOption('-u', '--update', action='store_true', dest='update', default=False,
                      help='Perform update of the application.'),
    )

    def handle(self, que_only=False, update=False, **options):
        self.build(que_only=que_only)

        if que_only:
            if update:
                self.display('You can now restart the erigonesd service (svcadm restart svc:/application/erigonesd:*)')
            else:
                self.display('You can now import the erigonesd SMF manifest (doc/init.d/erigonesd.xml)')
        else:
            if update:
                self.ctlsh('db_sync', '--force')
                self.ctlsh('post_update')
                self.display('You can now restart all Danube Cloud services:\n'
                             '\tsystemctl restart erigonesd.service\n'
                             '\tsystemctl restart esdc@gunicorn-api.service\n'
                             '\tsystemctl restart esdc@gunicorn-gui.service\n'
                             '\tsystemctl restart esdc@gunicorn-sio.service\n'
                )
            else:
                self.ctlsh('secret_key')
                self.ctlsh('db_sync', '--init', '--force')
                cmd = self.CTLSH
                self.display('You can now run the development webserver: "%s runserver";\n '
                             'or the production webserver: "%s prodserver"' % (cmd, cmd))

        self.display('Success.', color='green')
