from ._base import DanubeCloudCommand, CommandOption

DC_ADMIN = DanubeCloudCommand.settings.VMS_DC_ADMIN


class Command(DanubeCloudCommand):
    help = 'Generate ansible host inventory.'
    options = (
        CommandOption('--dc', dest='dc', default=DC_ADMIN,
                      help='List hosts from a specific virtual datacenter. Defaults to "%s".' % DC_ADMIN),
        CommandOption('--include-nodes', action='store_true', dest='include_nodes', default=False,
                      help='Include also list of physical nodes.'),
    )

    def handle(self, dc=None, include_nodes=False, **options):
        from vms.models import Vm, Node

        qs = Vm.objects

        if dc:
            qs = qs.filter(dc__name=dc)
        else:
            qs = qs.all()

        # print VMs in admin DC
		if dc != '':
			print('[%s]' % dc)

        for vm in qs:
            try:
                ip = vm.ips[0]
            except IndexError:
                continue

            line = [vm.alias, 'ansible_ssh_host=%s' % ip]

            if not vm.is_kvm():
                line.append('ansible_python_interpreter=/opt/local/bin/python')

            print(' '.join(line))

        if include_nodes:
            # print all nodes
            print('')
            print('[nodes]')
            nodes = Node.objects.all()

            for node in nodes:
                line = [
					node.hostname,
					'ansible_ssh_host=%s' % node.ip_address.ip,
					'ansible_python_interpreter=/opt/local/bin/python'
				]
                print(' '.join(line))

