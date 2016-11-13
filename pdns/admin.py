from django.contrib import admin
from django.db.models import BLANK_CHOICE_DASH
from django import forms

from pdns.models import Domain, Record
from gui.models import User


class DomainAdminForm(forms.ModelForm):
    class Meta:
        model = Domain
        exclude = ()

    def __init__(self, *args, **kwargs):
        super(DomainAdminForm, self).__init__(*args, **kwargs)
        self.fields['master'].required = False
        self.fields['user'].required = False
        self.fields['user'].widget = forms.Select(
            choices=BLANK_CHOICE_DASH + [(i.id, i.username) for i in User.objects.all()]
        )


class RecordAdminForm(forms.ModelForm):
    class Meta:
        model = Record
        exclude = ()

    def __init__(self, *args, **kwargs):
        super(RecordAdminForm, self).__init__(*args, **kwargs)
        self.fields['prio'].initial = Record.PRIO
        self.fields['ttl'].initial = Record.TTL
        self.fields['ordername'].required = False


class DomainAdmin(admin.ModelAdmin):
    form = DomainAdminForm
    list_display = ('name', 'type', 'master')
    readonly_fields = ('account', 'last_check', 'notified_serial')


class RecordAdmin(admin.ModelAdmin):
    form = RecordAdminForm
    list_display = ('name', 'type', 'content', 'domain')
    readonly_fields = ('change_date',)


admin.site.register(Domain, DomainAdmin)
admin.site.register(Record, RecordAdmin)
