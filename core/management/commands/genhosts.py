from ._base import DanubeCloudCommand, CommandOption

DC_ADMIN = DanubeCloudCommand.settings.VMS_DC_ADMIN


class Command(DanubeCloudCommand):
    help = 'Generate ansible host inventory.'
    options = (
        CommandOption('--dc', dest='dc', default=DC_ADMIN,
                      help='List hosts from a specific virtual datacenter. Defaults to "%s".' % DC_ADMIN),
        CommandOption('--vms', action='store_true', dest='vms', default=False,
                      help='List first IP address of all virtual machines in a specific virtual datacenter.'),
        CommandOption('--vms-primary', action='store_true', dest='vms_primary', default=False,
                      help='List primary IP address of all virtual machines in a specific virtual datacenter.'),
        CommandOption('--nodes', action='store_true', dest='nodes', default=False,
                      help='List admin IP address of all compute nodes.'),
        CommandOption('--nodes-external', action='store_true', dest='nodes_external', default=False,
                      help='List external IP address of all compute nodes.'),
    )

    @staticmethod
    def _list_node_hosts(external=False):
        from vms.models import Node

        for node in Node.objects.all().order_by('created'):
            if external:
                ip = node.address_external
            else:
                ip = node.address_admin

            yield '%s ansible_ssh_host=%s ansible_python_interpreter=/opt/local/bin/python' % (node.hostname, ip)

    @staticmethod
    def _list_vm_hosts(dc, primary=False):
        from vms.models import Vm

        qs = Vm.objects.order_by('created')

        if dc:
            qs = qs.filter(dc__name=dc)
        else:
            qs = qs.all()

        for vm in qs:
            try:
                if primary:
                    ip = vm.primary_ip_active
                else:
                    ip = vm.ips_active[0]
            except LookupError:
                continue

            line = [vm.alias, 'ansible_ssh_host=%s' % ip]

            if not vm.is_kvm():
                line.append('ansible_python_interpreter=/opt/local/bin/python')

            yield ' '.join(line)

    def handle(self, dc=None, vms=False, vms_primary=False, nodes=False, nodes_external=False, **options):
        if nodes or nodes_external:
            print('[nodes]')

            for host_line in self._list_node_hosts(external=nodes_external):
                print(host_line)

            print('')

        if vms or vms_primary:
            # print VMs in a specific DC
            if dc:
                print('[%s]' % dc)

            for host_line in self._list_vm_hosts(dc, primary=vms_primary):
                print(host_line)
