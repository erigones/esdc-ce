from ._base import DanubeCloudCommand, CommandOption

DC_ADMIN = DanubeCloudCommand.settings.VMS_DC_ADMIN


class Command(DanubeCloudCommand):
    help = 'Generate ansible host inventory.'

    def add_arguments(self, parser):
        parser.add_argument('--vms',
                            action='store_true',
                            dest='vms',
                            default=False,
                            help='List first IP address of all virtual machines in a specific virtual datacenter.')

        parser.add_argument('--vms-primary',
                            action='store_true',
                            dest='vms_primary',
                            default=False,
                            help='List primary IP address of all virtual machines in a specific virtual datacenter.')

        parser.add_argument('--nodes',
                            action='store_true',
                            dest='nodes',
                            default=False,
                            help='List admin IP address of all compute nodes.')

        parser.add_argument('--nodes-external',
                            action='store_true',
                            dest='nodes_external',
                            default=False,
                            help='List external IP address of all compute nodes.')

        parser.add_argument('--vdc',
                            dest='virtual_dc',
                            default=DC_ADMIN,
                            help='List hosts from a specific virtual datacenter (vDC). Requires --vms. '
                                 'Defaults to "%s".' % DC_ADMIN)

        parser.add_argument('--pdc',
                            dest='physical_dc',
                            default=None,
                            help='List compute node IP addresses depending on their physical location. '
                                 'Nodes located in this datacenter will use admin network IP addresses; '
                                 'Other nodes will use external IP addresses. Requires --nodes.')

    @staticmethod
    def _list_node_hosts(external=False, dc_name=None):
        from vms.models import Node

        for node in Node.objects.all().order_by('created'):
            if dc_name is None:
                if external:
                    ip = node.address_external
                else:
                    ip = node.address_admin
            else:
                if node.dc_name == dc_name:
                    ip = node.address_admin
                else:
                    ip = node.address_external

            yield '%s ansible_ssh_host=%s ansible_python_interpreter=/opt/local/bin/python dc_name="%s"' % \
                  (node.hostname, ip, node.dc_name)

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

    def handle(self, vms=False, vms_primary=False, nodes=False, nodes_external=False, virtual_dc=None, physical_dc=None,
               **options):
        if nodes or nodes_external:
            print('[nodes]')

            for host_line in self._list_node_hosts(external=nodes_external, dc_name=physical_dc):
                print(host_line)

            print('')

        if vms or vms_primary:
            # print VMs in a specific DC
            if virtual_dc:
                print('[%s]' % virtual_dc)

            for host_line in self._list_vm_hosts(virtual_dc, primary=vms_primary):
                print(host_line)
