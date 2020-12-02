from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as _UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.utils.translation import ugettext_lazy as _
from django.urls import path, re_path
from django.shortcuts import get_object_or_404
from django.conf import settings

from gui.models import User, Role, Permission, UserProfile, UserSSHKey
from gui.profile.utils import impersonate_user, impersonate_cancel

admin.site.unregister(Group)


class UserSSHKeyInline(admin.StackedInline):
    model = UserSSHKey
    can_delete = True
    verbose_name_plural = _('SSH Keys')
    max_num = settings.PROFILE_SSH_KEY_LIMIT
    extra = 0
    readonly_fields = ('fingerprint',)


class UserAdminCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User

    def clean_username(self):
        # Since User.username is unique, this check is redundant,
        # but it sets a nicer error message than the ORM. See #13147.
        username = self.cleaned_data['username']
        try:
            # noinspection PyProtectedMember
            User._default_manager.get(username=username)
        except User.DoesNotExist:
            return username
        raise forms.ValidationError(self.error_messages['duplicate_username'])


class UserAdminChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


# Define an inline admin descriptor for UserProfile model
# which acts a bit like a singleton
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = _('Profile')

    fieldsets = (
        (None, {
            'fields': ('phone',),
        }),
        (_('User Settings'), {
            'fields': ('newsletter_tech', 'newsletter_buss', 'usertype', 'language', 'timezone', 'currency')
        }),
        (_('Verification'), {
            'fields': ('tos_acceptation', 'email_verified', 'phone_verified', 'phone2_verified')
        }),
        (_('Verification tokens'), {
            'fields': ('email_token', 'phone_token', 'phone2_token'),
            'classes': ('collapse',)
        }),
        (_('Contact details'), {
            'fields': ('title', 'middle_name', 'phone2', 'email2', 'website', 'jabber'),
            'classes': ('collapse',)
        }),
        (_('Company details'), {
            'fields': ('company', 'companyid', 'taxid', 'vatid', 'bankid'),
            'classes': ('collapse',),
        }),
        (_('Primary address details'), {
            'fields': ('street_1', 'street_2', 'city', 'postcode', 'state', 'country'),
            'classes': ('collapse',),
        }),
        (_('Billing address details'), {
            'fields': ('different_billing', 'street2_1', 'street2_2', 'city2', 'postcode2', 'state2', 'country2'),
            'classes': ('collapse',),
        }),
    )


class GroupUsersInline(admin.TabularInline):
    model = User.roles.through
    extra = 1


class GroupAdmin(admin.ModelAdmin):
    model = Role
    verbose_name_plural = _('group',)
    readonly_fields = ('created', 'changed')
    fieldsets = (
        (None, {
            'fields': ('name', 'alias', 'permissions', 'dc_bound')
        }),
        (_('Info'), {
            'fields': ('created', 'changed'),
            'classes': ('collapse',),
        }),
    )
    inlines = (GroupUsersInline,)


admin.site.register(Role, GroupAdmin)


class PermissionGroupsInline(admin.TabularInline):
    model = Role.permissions.through
    extra = 1


class PermissionAdmin(admin.ModelAdmin):
    model = Permission
    verbose_name_plural = _('permission')
    inlines = (PermissionGroupsInline,)


admin.site.register(Permission, PermissionAdmin)


# Define a new User admin
class UserAdmin(_UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm  # http://stackoverflow.com/a/16953303
    list_display = ('username', 'first_name', 'last_name', 'is_active', 'is_staff', 'api_access', 'last_login')
    readonly_fields = ('last_login', 'date_joined')
    list_filter = ('is_active', 'api_access', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    # inlines = (UserProfileInline, UserSSHKeyInline)

    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        (_('Basic info'), {
            'fields': ('first_name', 'last_name', 'email')
        }),
        (_('Settings'), {
            'fields': ('default_dc', 'dc_bound', 'is_active', 'api_access', 'is_staff'),
        }),
        (_('Groups & Keys'), {
            'fields': ('is_superuser', 'roles', 'api_key', 'callback_key'),
            'classes': ('collapse',),
        }),
        (_('Info'), {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )

    def get_inline_instances(self, request, obj=None):
        if obj:
            self.inlines = (UserProfileInline, UserSSHKeyInline)
        else:
            self.inlines = ()
        return super(UserAdmin, self).get_inline_instances(request, obj=obj)

    def get_urls(self):
        urls = [
            path('cancel_impersonation/', self.admin_site.admin_view(self.stop_impersonation),
                 name='stop_impersonation'),
            path('<int:user_id>/impersonate/', self.admin_site.admin_view(self.start_impersonation),
                 name='start_impersonation'),
        ]
        return urls + super(UserAdmin, self).get_urls()

    def start_impersonation(self, request, user_id):
        user = get_object_or_404(self.model, id=user_id)

        return impersonate_user(request, user.id)

    # noinspection PyMethodMayBeStatic
    def stop_impersonation(self, request):
        return impersonate_cancel(request)


admin.site.register(User, UserAdmin)
