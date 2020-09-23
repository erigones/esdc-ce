# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

# LINUX = 1
# SUNOS = 2
# BSD = 3
# WINDOWS = 4
# SUNOS_ZONE = 5
# LINUX_ZONE = 6
hvm_ostypes = [1, 2, 3, 4]
hypervisor_kvm = 1
hypervisor_none = 3


def update_existing_rows_vm(apps, schema_editor):
    Vm = apps.get_model('vms', 'Vm')
    for vm in Vm.objects.all().iterator():
        # we set all HVM VMs to KVM brand because no BHYVE brands exist yet (we are adding support for it now)
        vm.hvm_type = hypervisor_kvm if vm.ostype in hvm_ostypes else hypervisor_none
        vm.save()


def update_existing_rows_vmtemplate(apps, schema_editor):
    VmTemplate = apps.get_model('vms', 'VmTemplate')
    for vmt in VmTemplate.objects.all().iterator():
        # we set all HVM VMs to KVM brand because no BHYVE brands exist yet (we are adding support for it now)
        if vmt.ostype:
            vmt.hvm_type = hypervisor_kvm if vmt.ostype in hvm_ostypes else hypervisor_none
            vmt.save()


class Migration(migrations.Migration):
    dependencies = [
        ('vms', '0007_tasklogentry_content_type_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='vm',
            name='hvm_type',
            field=models.SmallIntegerField(null=True, verbose_name='Hypervisor type', choices=[(1, 'KVM hypervisor'),
                                                                                               (2, 'BHYVE hypervisor'),
                                                                                               (3, 'NO hypervisor')]),
            preserve_default=False,
        ),
        migrations.RunPython(update_existing_rows_vm, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='vm',
            name='hvm_type',
            field=models.SmallIntegerField(verbose_name='Hypervisor type', choices=[(1, 'KVM hypervisor'),
                                                                                    (2, 'BHYVE hypervisor'),
                                                                                    (3, 'NO hypervisor')]),
        ),

        migrations.AddField(
            model_name='vmtemplate',
            name='hvm_type',
            field=models.SmallIntegerField(blank=True, null=True, verbose_name='Hypervisor type',
                                           choices=[(1, 'KVM hypervisor'),
                                                    (2, 'BHYVE hypervisor'),
                                                    (3, 'NO hypervisor')]),
            preserve_default=False,
        ),
        migrations.RunPython(update_existing_rows_vmtemplate, migrations.RunPython.noop),
    ]


