from django.conf import settings

from api import serializers as s
from api.vm.utils import get_iso_images
from vms.models import Vm, Node, Iso


class VmStatusSerializer(s.Serializer):
    hostname = s.CharField(read_only=True)
    uuid = s.CharField(read_only=True)
    alias = s.CharField(read_only=True)
    status = s.DisplayChoiceField(choices=Vm.STATUS, read_only=True)
    status_change = s.DateTimeField(read_only=True)
    node_status = s.DisplayChoiceField(source='node.status', choices=Node.STATUS_DB, read_only=True)
    tasks = s.CharField(source='tasks', read_only=True)
    uptime = s.IntegerField(source='uptime_actual', read_only=True)


class VmStatusActionIsoSerializer(s.Serializer):
    iso = None
    iso2 = None
    cdimage = s.CharField(required=False)
    cdimage2 = s.CharField(required=False)
    cdimage_once = s.BooleanField(default=True)

    def __init__(self, request, vm, *args, **kwargs):
        self.request = request
        self.vm = vm
        super(VmStatusActionIsoSerializer, self).__init__(*args, **kwargs)

    def validate_iso(self, value):
        try:
            return get_iso_images(self.request, self.vm.ostype).get(name=value)
        except Iso.DoesNotExist:
            msg = s.ChoiceField.default_error_messages['invalid_choice']
            raise s.ValidationError(msg % {'value': value})

    def validate_cdimage(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if value:
                self.iso = self.validate_iso(value)

        return attrs

    def validate_cdimage2(self, attrs, source):
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if value:
                self.iso2 = self.validate_iso(value)

        return attrs


class VmStatusFreezeSerializer(s.Serializer):
    freeze = s.BooleanField(default=False)
    unfreeze = s.BooleanField(default=False)


class VmStatusUpdateJSONSerializer(s.Serializer):
    update = s.BooleanField(default=True)

    def __init__(self, *args, **kwargs):
        update_default = kwargs.get('default', False)
        super(VmStatusUpdateJSONSerializer, self).__init__(*args, **kwargs)
        self.fields['update'].default = update_default


class VmStatusStopSerializer(s.Serializer):
    timeout = s.IntegerField(default=settings.VMS_VM_STOP_TIMEOUT_DEFAULT)
    force = s.BooleanField(default=False)

    def __init__(self, request, vm, *args, **kwargs):
        super(VmStatusStopSerializer, self).__init__(*args, **kwargs)
        dc_settings = request.dc.settings

        if vm.ostype == vm.WINDOWS:
            self.fields['timeout'].default = dc_settings.VMS_VM_STOP_WIN_TIMEOUT_DEFAULT
        else:
            self.fields['timeout'].default = dc_settings.VMS_VM_STOP_TIMEOUT_DEFAULT
