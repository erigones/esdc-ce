from django.db import connection

from api import status
from api.api_views import APIView
from api.exceptions import ObjectAlreadyExists, ObjectNotFound
from api.signals import group_relationship_changed
from api.utils.db import get_object
from api.dc.utils import remove_dc_binding_virt_object
from api.dc.group.serializers import GroupSerializer
from api.accounts.user.utils import remove_user_dc_binding
from api.accounts.messages import LOG_GROUP_UPDATE
from api.dc.messages import LOG_GROUP_ATTACH, LOG_GROUP_DETACH
from api.task.response import SuccessTaskResponse
from gui.models import Role


class DcGroupView(APIView):
    serializer = GroupSerializer
    order_by_default = order_by_fields = ('name',)

    def __init__(self, request, name, data):
        super(DcGroupView, self).__init__(request)
        self.data = data
        self.name = name
        self.dc = request.dc

        if name:
            attrs = {'name': name}

            if request.method != 'POST':
                attrs['dc'] = request.dc

            roles = get_object(request, Role, attrs, sr=('dc_bound',), exists_ok=True, noexists_fail=True)
        else:
            roles = self.dc.roles.all().order_by(*self.order_by)

            if self.full or self.extended:
                roles = roles.select_related('dc_bound', ).prefetch_related('permissions', 'user_set')

        self.role = roles

    def get(self, many=False):
        return self._get(self.role, many=many, field_name='name')

    def _remove_dc_binding(self, res):
        if self.role.dc_bound:
            remove_dc_binding_virt_object(res.data.get('task_id'), LOG_GROUP_UPDATE, self.role, user=self.request.user)

    def _remove_user_dc_binding(self, res):
        """This makes sense only for attaching group into DC"""
        task_id = res.data.get('task_id')

        # Remove user.dc_bound flag for users in this group, which are DC-bound, but not to this datacenter
        for user in self.role.user_set.filter(dc_bound__isnull=False).exclude(dc_bound=self.dc):
            remove_user_dc_binding(task_id, user)

    def post(self):
        dc, group = self.dc, self.role

        if group.dc_set.filter(id=dc.id).exists():
            raise ObjectAlreadyExists(model=Role)

        ser = self.serializer(self.request, group)
        group.dc_set.add(dc)

        connection.on_commit(lambda: group_relationship_changed.send(group_name=group.name,
                                                                     dc_name=dc.name))
        res = SuccessTaskResponse(self.request, ser.data, obj=group, status=status.HTTP_201_CREATED,
                                  detail_dict=ser.detail_dict(), msg=LOG_GROUP_ATTACH)
        self._remove_dc_binding(res)
        self._remove_user_dc_binding(res)

        return res

    def delete(self):
        dc, group = self.dc, self.role

        if not group.dc_set.filter(id=dc.id).exists():
            raise ObjectNotFound(model=Role)

        ser = self.serializer(self.request, group)
        group.dc_set.remove(self.request.dc)
        connection.on_commit(lambda: group_relationship_changed.send(group_name=group.name, dc_name=dc.name))
        res = SuccessTaskResponse(self.request, None, obj=group, detail_dict=ser.detail_dict(), msg=LOG_GROUP_DETACH)
        self._remove_dc_binding(res)

        return res
