from django.db import connection
from django.utils.translation import ugettext_noop as _

from api import status
from api.api_views import APIView
from api.exceptions import PermissionDenied, PreconditionRequired
from api.mon.alerting.tasks import mon_user_group_changed
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.task.log import delete_tasklog_cached
from api.utils.db import get_object
from api.utils.views import call_api_view
from api.dc.utils import get_dc, get_dcs, remove_dc_binding_virt_object
from api.dc.base.serializers import DcSerializer, SuperDcSerializer, ExtendedDcSerializer, DefaultDcSettingsSerializer
from api.dc.messages import LOG_DC_CREATE, LOG_DC_UPDATE
from api.accounts.user.utils import remove_user_dc_binding
from api.accounts.messages import LOG_GROUP_UPDATE
from api.messages import LOG_VIRT_OBJECT_UPDATE_MESSAGES
from vms.models import Dc, DefaultDc
from gui.models import User


class DcView(APIView):
    serializer = DcSerializer
    order_by_default = order_by_fields = ('name',)
    order_by_field_map = {'created': 'id'}

    def __init__(self, request, name, data):
        super(DcView, self).__init__(request)
        self.data = data
        self.name = name

        if request.user.is_staff:
            self.serializer = SuperDcSerializer

        if self.extended:
            self.serializer = ExtendedDcSerializer
            extra = {'select': ExtendedDcSerializer.extra_select}
        else:
            extra = None

        if name:
            # Return dc from cache (this will also check user permissions for requested DC)
            # We do this because GET is available for anybody
            if request.method == 'GET':
                get_dc(request, name)
            # But we will use this fresh DC object
            self.dc = get_object(request, Dc, {'name': name}, sr=('owner',), extra=extra)
            # Update current datacenter to log tasks for this dc
            request.dc = self.dc

        else:
            # GET many is available for anybody
            if (request.user.is_staff or self.full) or self.extended:
                pr = ('roles',)
            else:
                pr = None

            self.dc = get_dcs(request, sr=('owner',), pr=pr, extra=extra, order_by=self.order_by)

    def is_extended(self, data):
        # Only SuperAdmin has access to extended stats!
        return super(DcView, self).is_extended(data) and self.request.user.is_staff

    def get(self, many=False):
        return self._get(self.dc, many=many)

    def _remove_user_dc_binding(self, task_id, owner=None, groups=None):
        dc = self.dc

        if owner:
            remove_user_dc_binding(task_id, owner, dc=dc)

        if groups:
            for user in User.objects.distinct().filter(roles__in=groups, dc_bound__isnull=False).exclude(dc_bound=dc):
                remove_user_dc_binding(task_id, user, dc=dc)

    def post(self):
        dc = self.dc
        request = self.request

        if not DefaultDc().settings.VMS_DC_ENABLED:
            raise PermissionDenied

        dc.owner = request.user  # just a default
        dc.alias = dc.name  # just a default
        ser = self.serializer(request, dc, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=dc)

        # Create default custom settings suitable for new DC (without global settings)
        default_custom_settings = DefaultDc().custom_settings.copy()
        for key in DefaultDcSettingsSerializer.get_global_settings():
            try:
                del default_custom_settings[key]
            except KeyError:
                pass

        # Copy custom settings from default DC and save new DC
        ser.object.custom_settings = default_custom_settings
        ser.save()
        connection.on_commit(lambda: mon_user_group_changed.call(request, dc_name=dc.name))

        res = SuccessTaskResponse(request, ser.data, status=status.HTTP_201_CREATED, obj=dc,
                                  detail_dict=ser.detail_dict(), msg=LOG_DC_CREATE)
        dcs = dc.settings
        task_id = res.data.get('task_id')

        # Changing DC groups affects the group.dc_bound flag
        if dc.roles.exists():
            # The groups that are added to newly created DC should not be DC-bound anymore
            for group in dc.roles.all():
                if group.dc_bound:
                    remove_dc_binding_virt_object(task_id, LOG_GROUP_UPDATE, group, user=request.user)

        # Creating new DC can affect the dc_bound flag on users (owner + users from dc.groups)
        self._remove_user_dc_binding(task_id, owner=dc.owner, groups=dc.roles.all())

        # Create association with default server domain
        if dcs.DNS_ENABLED:
            from api.dc.domain.views import dc_domain
            call_api_view(request, None, dc_domain, dcs.VMS_VM_DOMAIN_DEFAULT, data={'dc': dc}, log_response=True)

        # Create association with default rescue CD
        if dcs.VMS_ISO_RESCUECD:
            from api.dc.iso.views import dc_iso
            call_api_view(request, None, dc_iso, dcs.VMS_ISO_RESCUECD, data={'dc': dc}, log_response=True)
        return res

    def put(self):
        dc = self.dc
        request = self.request

        ser = self.serializer(request, dc, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(request, ser.errors, obj=dc)

        ser.save()
        res = SuccessTaskResponse(request, ser.data, obj=dc, detail_dict=ser.detail_dict(), msg=LOG_DC_UPDATE)
        task_id = res.data.get('task_id')
        # Changing DC groups affects the group.dc_bound flag
        if ser.groups_changed:
            # The groups that are removed or added should not be DC-bound anymore
            for group in ser.groups_changed:
                # TODO maybe it's duplicate so we don't have to do this
                connection.on_commit(lambda: mon_user_group_changed.call(request, group_name=group.name))
                if group.dc_bound:
                    remove_dc_binding_virt_object(task_id, LOG_GROUP_UPDATE, group, user=request.user)

        # After changing the DC owner or changing DC groups we have to invalidate the list of admins for this DC
        if ser.owner_changed or ser.groups_changed:
            connection.on_commit(lambda: mon_user_group_changed.call(request, dc_name=dc.name))
            User.clear_dc_admin_ids(dc)
            # Remove user.dc_bound flag for new DC owner
            # Remove user.dc_bound flag for users in new dc.groups, which are DC-bound, but not to this datacenter
            self._remove_user_dc_binding(task_id, owner=ser.owner_changed, groups=ser.groups_added)

        # When a user is removed as owner from non-default DC or groups are changed on a non-default DC
        # we have to update the current_dc on every affected user, because he could remain access to this DC
        # (this is because get_dc() uses current_dc as a shortcut)
        if not dc.is_default():
            default_dc = DefaultDc()

            if ser.owner_changed and not ser.owner_changed.is_staff:
                ser.owner_changed.current_dc = default_dc

            if ser.removed_users:
                ser.removed_users.exclude(is_staff=True).update(default_dc=default_dc)

        return res

    def delete(self):
        dc, request = self.dc, self.request

        if dc.is_default():
            raise PreconditionRequired(_('Default datacenter cannot be deleted'))
        if dc.dcnode_set.exists():
            raise PreconditionRequired(_('Datacenter has nodes'))  # also "checks" DC backups
        if dc.vm_set.exists():
            raise PreconditionRequired(_('Datacenter has VMs'))
        if dc.backup_set.exists():
            raise PreconditionRequired(_('Datacenter has backups'))  # should be checked by dcnode check above

        dc_id = dc.id
        ser = self.serializer(request, dc)
        dc_bound_objects = dc.get_bound_objects()

        # After deleting a DC the current_dc is automatically set to DefaultDc by the on_delete db field parameter
        ser.object.delete()

        # Remove cached tasklog for this DC (DB tasklog entries will be remove automatically)
        delete_tasklog_cached(dc_id)

        connection.on_commit(lambda: mon_user_group_changed.call(request, dc_name=ser.object.name))
        res = SuccessTaskResponse(request, None)  # no msg => won't be logged

        # Every DC-bound object looses their DC => becomes DC-unbound
        task_id = res.data.get('task_id')

        # Update bound virt objects to be DC-unbound after DC removal
        for model, objects in dc_bound_objects.items():
            msg = LOG_VIRT_OBJECT_UPDATE_MESSAGES.get(model, None)
            if objects and msg:
                for obj in objects:
                    if obj.dc_bound:
                        # noinspection PyUnresolvedReferences
                        remove_dc_binding_virt_object(task_id, msg, obj, user=request.user, dc_id=DefaultDc.id)

        return res
