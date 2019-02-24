from ._base import DanubeCloudCommand, CommandError


class Command(DanubeCloudCommand):
    help = 'Manual cleanup after a failed task.'
    args = '<API function name> [API function parameter1=value1 [parameter2=value2] ...]'
    api_view_names = frozenset([
        'vm_migrate',
    ])

    @staticmethod
    def get_vm(**params):
        from vms.models import Vm

        if 'uuid' in params:
            query = {'uuid': params['uuid']}
        elif 'hostname' in params:
            query = {'hostname': params['hostname']}
        else:
            raise CommandError('Missing "hostname" or "uuid" parameter')

        return Vm.objects.get(**query)

    @staticmethod
    def run_cleanup(api_view_name, method, obj=None, **api_view_params):
        from que.utils import generate_internal_task_id
        from api.task.cleanup import task_cleanup

        api_view_params['view'] = api_view_name
        api_view_params['method'] = method
        result = {'meta': {'apiview': api_view_params}}
        task_id = generate_internal_task_id()

        return task_cleanup(result, task_id, None, obj=obj)

    def handle(self, api_view_name, *args, **options):
        if api_view_name not in self.api_view_names:
            raise CommandError('Unsupported API function')

        params = dict(i.split('=') for i in args)

        if api_view_name.startswith('vm_'):
            obj = self.get_vm(**params)
        else:
            obj = None

        method = params.get('method', 'PUT').upper()

        self.run_cleanup(api_view_name, method, obj=obj, **params)
        self.display('Done.', color='green')
