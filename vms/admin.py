from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from vms.models import (Dc, Iso, VmTemplate, Image, Node, DcNode, Storage, NodeStorage, Vm, Subnet, IPAddress,
                        SnapshotDefine, Snapshot, BackupDefine, Backup)
from vms.admin_forms import DcAdminForm, VmTemplateAdminForm, ImageAdminForm, NodeAdminForm, VmAdminForm


class DcAdmin(admin.ModelAdmin):
    form = DcAdminForm
    list_display = ('name', 'alias', 'owner', 'access')
    list_filter = ('access',)

    def save_model(self, request, obj, form, change):
        obj.json = form.cleaned_data['json']
        return super(DcAdmin, self).save_model(request, obj, form, change)


class IsoAdmin(admin.ModelAdmin):
    list_display = ('name', 'alias', 'owner', 'access', 'ostype')
    list_filter = ('access', 'dc')


class VmTemplateAdmin(admin.ModelAdmin):
    form = VmTemplateAdminForm
    list_display = ('name', 'alias', 'owner', 'access', 'ostype')
    list_filter = ('access', 'dc')

    def save_model(self, request, obj, form, change):
        obj.json = form.cleaned_data['json']
        return super(VmTemplateAdmin, self).save_model(request, obj, form, change)


class ImageAdmin(admin.ModelAdmin):
    form = ImageAdminForm
    list_display = ('name', 'alias', 'owner', 'access', 'ostype')
    list_filter = ('access', 'dc')
    fieldsets = (
        (None, {
            'fields': ('uuid', 'name', 'alias', 'dc', 'version', 'size', 'ostype',
                       'status', 'desc', 'access', 'owner', 'deploy', 'resize', 'dc_bound'),
        }),
        (_('JSON'), {
            'fields': ('json', ),
            'classes': ('collapse', ),
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.json = form.cleaned_data['json']
        return super(ImageAdmin, self).save_model(request, obj, form, change)


class DcNodeInline(admin.TabularInline):
    model = DcNode
    extra = 0


class NodeAdmin(admin.ModelAdmin):
    inlines = (DcNodeInline, )
    form = NodeAdminForm
    list_display = ('uuid', 'hostname', 'status', 'status_change')
    fieldsets = (
        (None, {
            'fields': ('uuid', 'hostname', 'address', 'status', 'owner', 'is_compute', 'is_backup', 'is_head')
        }),
        (_('Resources'), {
            'fields': ('cpu', 'ram', 'cpu_coef', 'ram_coef', 'cpu_free', 'ram_free')
        }),
        (_('Info'), {
            'fields': ('status_change', 'created', 'changed'),
            'classes': ('collapse', )
        }),
        (_('JSON'), {
            'fields': ('json', 'config'),
            'classes': ('collapse', ),
        }),
    )
    readonly_fields = ('status_change', 'created', 'changed', 'cpu_free', 'ram_free')
    list_filter = ('status', 'status_change', 'created', 'dc')
    search_fields = ('hostname', 'uuid', 'address')

    def save_model(self, request, obj, form, change):
        obj.json = form.cleaned_data['json']
        return super(NodeAdmin, self).save_model(request, obj, form, change)


class InlineNodeStorageAdmin(admin.StackedInline):
    model = NodeStorage
    extra = 0
    max_num = 1


class StorageAdmin(admin.ModelAdmin):
    inlines = (InlineNodeStorageAdmin, )
    list_display = ('name', 'alias', 'owner', 'access', 'type')
    list_filter = ('access', 'type')
    readonly_fields = ('created', 'changed', 'size_free')


class VmAdmin(admin.ModelAdmin):
    form = VmAdminForm

    list_display = ('hostname', 'ostype', 'node', 'owner', 'template', 'status', 'status_change', 'dc')
    fieldsets = (
        (None, {
            'fields': ('uuid', 'hostname', 'alias', 'dc', 'ostype', 'hvm_type', 'node', 'owner',
                       'template', 'status', 'vnc_port', 'tags')
        }),
        (_('Status information'), {
            'fields': ('status_change', 'created', 'changed', 'uptime', 'uptime_changed'),
        }),
        (_('VM information'), {
            'fields': ('info', ),
            'classes': ('collapse', )
        }),
        (_('JSON'), {
            'fields': ('json', ),
            'classes': ('collapse', )
        }),
        (_('Active JSON'), {
            'fields': ('json_active', ),
            'classes': ('collapse', )
        }),
        (_('Replication'), {
            'fields': ('slave_vms',),
            'classes': ('collapse', )
        }),
    )
    readonly_fields = ('status_change', 'created', 'changed', 'uptime', 'uptime_changed')
    list_filter = ('status', 'status_change', 'created', 'dc')
    search_fields = ('alias', 'hostname', 'uuid')

    def save_model(self, request, obj, form, change):
        obj.json = form.cleaned_data['json']
        new = not change
        obj.sync_json(sync_template=new, sync_defaults=new)
        return super(VmAdmin, self).save_model(request, obj, form, change)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['SOCKETIO_URL'] = settings.SOCKETIO_URL
        return super(VmAdmin, self).change_view(request, object_id, form_url, extra_context=extra_context)


class IPAddressInline(admin.TabularInline):
    model = IPAddress
    can_delete = False
    extra = 0
    readonly_fields = ('vm', 'vms')

    # noinspection PyClassHasNoInit
    class Media:
        js = ('vms/js/ipaddress-admin.js', )


class SubnetAdmin(admin.ModelAdmin):
    list_display = ('name', 'alias', 'owner', 'access', 'vlan_id', 'nic_tag')
    list_filter = ('access', 'dc')
    inlines = (IPAddressInline,)


class IPAddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'ip', 'subnet', 'vm')
    list_filter = ('subnet__name',)
    search_fields = ('id', 'ip', 'subnet__name', 'vm__alias', 'vm__hostname', 'vm__uuid')


class SnapshotDefineAdmin(admin.ModelAdmin):
    list_display = ('id', 'vm', 'name', 'disk_id', 'active')
    search_fields = ('id', 'name', 'vm__alias', 'vm__hostname', 'vm__uuid')

    def queryset(self, request):
        return super(SnapshotDefineAdmin, self).queryset(request).select_related('periodic_task')


class SnapshotAdmin(admin.ModelAdmin):
    list_display = ('id', 'vm', 'name', 'disk_id', 'type', 'status', 'define')
    list_filter = ('type', 'status', 'vm__dc')
    search_fields = ('id', 'name', 'vm__alias', 'vm__hostname', 'vm__uuid')


class BackupDefineAdmin(admin.ModelAdmin):
    list_display = ('id', 'vm', 'name', 'disk_id', 'active', 'node')
    search_fields = ('id', 'name', 'vm__alias', 'vm__hostname', 'vm__uuid', 'node__hostname', 'node__uuid')

    def queryset(self, request):
        return super(BackupDefineAdmin, self).queryset(request).select_related('periodic_task')


class BackupAdmin(admin.ModelAdmin):
    list_display = ('id', 'vm', 'name', 'disk_id', 'status', 'node', 'define')
    list_filter = ('status', 'dc')
    search_fields = ('id', 'name', 'vm__alias', 'vm__hostname', 'vm__uuid', 'node__hostname', 'node__uuid')


class TaskLogEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'time', 'task', 'status', 'get_username', 'content_type', 'get_object_name', 'msg', 'dc')
    list_filter = ('status', 'dc')

    def queryset(self, request):
        return super(TaskLogEntryAdmin, self).queryset(request).select_related('content_type')


admin.site.register(Dc, DcAdmin)
admin.site.register(Iso, IsoAdmin)
admin.site.register(VmTemplate, VmTemplateAdmin)
admin.site.register(Image, ImageAdmin)
admin.site.register(Node, NodeAdmin)
admin.site.register(Storage, StorageAdmin)
admin.site.register(Vm, VmAdmin)
admin.site.register(Subnet, SubnetAdmin)
admin.site.register(IPAddress, IPAddressAdmin)
admin.site.register(SnapshotDefine, SnapshotDefineAdmin)
admin.site.register(Snapshot, SnapshotAdmin)
admin.site.register(BackupDefine, BackupDefineAdmin)
admin.site.register(Backup, BackupAdmin)
# admin.site.register(TaskLogEntry, TaskLogEntryAdmin)  # Does not support entries from multiple databases
