from ._base import DanubeCloudCommand, CommandOption

DC_ADMIN = DanubeCloudCommand.settings.VMS_DC_ADMIN


class Command(DanubeCloudCommand):
    help = 'Generate ansible host inventory.'
    options = (
        CommandOption('--dc', dest='dc', default=DC_ADMIN,
                      help='List hosts from a specific virtual datacenter. Defaults to "%s".' % DC_ADMIN),
    )

    def handle(self, dc=None, **options):
        from vms.models import Vm

        qs = Vm.objects

        if dc:
            qs = qs.filter(dc__name=dc)
        else:
            qs = qs.all()

        for vm in qs:
            try:
                ip = vm.ips[0]
            except IndexError:
                continue

            line = [vm.alias, 'ansible_ssh_host=%s' % ip]

            if not vm.is_kvm():
                line.append('ansible_python_interpreter=/opt/local/bin/python')

            print(' '.join(line))
