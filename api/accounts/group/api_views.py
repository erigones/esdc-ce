from api.status import HTTP_201_CREATED, HTTP_200_OK
from api.api_views import APIView
from api.utils.db import get_virt_object
from api.accounts.group.serializers import GroupSerializer, ExtendedGroupSerializer
from api.accounts.user.utils import remove_user_dc_binding
from api.accounts.messages import LOG_GROUP_CREATE, LOG_GROUP_UPDATE, LOG_GROUP_DELETE, LOG_USER_UPDATE
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.task.utils import task_log_success
from api.dc.utils import attach_dc_virt_object
from api.dc.messages import LOG_GROUP_ATTACH
from gui.models import User, Role
from vms.models import DefaultDc
from api.mon.alerting.tasks import mon_user_group_changed


class GroupView(APIView):
    """
    Although this API view behaves like a classic DC-mixed view, the api_view permissions restrict this view to
    SuperAdmins for read-write views. GET views are available to UserAdmins for viewing dc-bound groups.
    Otherwise the UserAdmin could easily give himself SuperAdmin privileges.
    """
    serializer = GroupSerializer
    dc_bound = False
    order_by_default = order_by_fields = ('name',)

    def __init__(self, request, name, data, many=False):
        super(GroupView, self).__init__(request)
        self.name = name
        self.data = data
        self.many = many
        sr = ('dc_bound',)

        if self.extended:
            self.serializer = ExtendedGroupSerializer

        if name:
            self.group = get_virt_object(request, Role, data=data, sr=sr, name=name)
        else:
            if self.full or self.extended:
                pr = ['permissions', 'user_set']

                if self.extended:
                    pr.append('dc_set')
            else:
                sr = ()
                pr = ()

            self.group = get_virt_object(request, Role, data=data, sr=sr, pr=pr, many=True)

    # noinspection PyProtectedMember
    def group_modify(self, update=False):
        group = self.group
        request = self.request

        if update:
            # We are deleting users that are not assigned to group any more, so we have to store all of them before
            # deleting because we have to update task log for user so he can see he was removed from group
            original_group_users = set(group.user_set.select_related('dc_bound').all())
        else:
            group.alias = group.name  # just a default
            original_group_users = set()

        ser = self.serializer(request, group, data=self.data, partial=update)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=group, dc_bound=False)

        ser.save()
        mon_user_group_changed.call(request, group_name=ser.object.name)
        if update:
            msg = LOG_GROUP_UPDATE
            status = HTTP_200_OK
        else:
            msg = LOG_GROUP_CREATE
            status = HTTP_201_CREATED

        res = SuccessTaskResponse(request, ser.data, status=status, obj=group, msg=msg,
                                  detail_dict=ser.detail_dict(), dc_bound=False)

        # let's get the task_id so we use the same one for each log message
        task_id = res.data.get('task_id')
        removed_users = None

        if group.dc_bound and not update:
            attach_dc_virt_object(res.data.get('task_id'), LOG_GROUP_ATTACH, group, group.dc_bound, user=request.user)

        if ser.object._users_to_save is not None:
            # Update Users log that are attached to group
            current_users = set(ser.object._users_to_save)
            added_users = current_users - original_group_users
            removed_users = original_group_users - current_users
            affected_users = current_users.symmetric_difference(original_group_users)

            # Remove user.dc_bound flag for newly added users if group is attached to multiple DCs or
            #                                                          to one DC that is different from user.dc_bound
            if added_users:
                group_dcs_count = group.dc_set.count()

                if group_dcs_count >= 1:
                    if group_dcs_count == 1:
                        dc = group.dc_set.get()
                    else:
                        dc = None

                    for user in added_users:
                        remove_user_dc_binding(task_id, user, dc=dc)

            # Update Users that were removed from group or added to group
            for user in affected_users:
                detail = "groups='%s'" % ','.join(user.roles.all().values_list('name', flat=True))
                task_log_success(task_id, LOG_USER_UPDATE, obj=user, owner=user, update_user_tasks=False, detail=detail)

        # Permission or users for this group were changed, which may affect the cached list of DC admins for DCs which
        # are attached to this group. So we need to clear the list of admins cached for each affected DC
        if ser.object._permissions_to_save is not None or ser.object._users_to_save is not None:
            for dc in group.dc_set.all():
                User.clear_dc_admin_ids(dc)

            # Users were removed from this group and may loose access to DCs which are attached to this group
            # So we better set all users current_dc to default_dc
            if removed_users:
                default_dc = DefaultDc()
                for user in removed_users:
                    user.current_dc = default_dc

        return res

    def get(self):
        return self._get(self.group, self.data, self.many)

    def post(self):
        if not self.request.user.is_staff and self.data:
            self.data.pop('dc_bound', None)  # default DC binding cannot be changed when creating object

        return self.group_modify(update=False)

    def put(self):
        return self.group_modify(update=True)

    def delete(self):
        group = self.group
        dd = {'permissions': list(group.permissions.all().values_list('name', flat=True))}
        group.delete()
        mon_user_group_changed.call(self.request, group_name=group.name)
        return SuccessTaskResponse(self.request, None, obj=group, msg=LOG_GROUP_DELETE, detail_dict=dd, dc_bound=False)
