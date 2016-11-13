from api.api_views import APIView
from api.exceptions import OperationNotSupported
from api.vm.utils import get_object
from api.accounts.permission.serializers import PermissionSerializer
from gui.models import Permission


class PermissionView(APIView):
    serializer = PermissionSerializer
    dc_bound = False
    order_by_default = order_by_fields = ('name',)

    def __init__(self, request, name, data, many=False):
        super(PermissionView, self).__init__(request)
        self.name = name
        self.data = data
        self.many = many

        if name:
            self.permission = get_object(request, Permission, {'name': name})
        else:
            self.permission = Permission.objects.all().order_by(*self.order_by)

    def get(self):
        return self._get(self.permission, self.data, self.many)

    # noinspection PyMethodMayBeStatic
    def post(self):
        raise OperationNotSupported

    # noinspection PyMethodMayBeStatic
    def put(self):
        raise OperationNotSupported

    # noinspection PyMethodMayBeStatic
    def delete(self):
        raise OperationNotSupported
