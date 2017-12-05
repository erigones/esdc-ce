# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vms', '0005_subnet_vxlan_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='subnet',
            name='mtu',
            field=models.PositiveIntegerField(default=None, null=True, verbose_name='MTU', blank=True),
        ),
    ]
