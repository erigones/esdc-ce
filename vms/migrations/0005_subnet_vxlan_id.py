# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vms', '0004_vm_node_add_note_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='subnet',
            name='vxlan_id',
            field=models.PositiveIntegerField(default=None, null=True, verbose_name='VXLAN segment ID', blank=True),
        ),
    ]
