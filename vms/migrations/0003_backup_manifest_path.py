# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vms', '0002_ipaddress_vms'),
    ]

    operations = [
        migrations.AddField(
            model_name='backup',
            name='manifest_path',
            field=models.CharField(max_length=255, verbose_name='Manifest path', blank=True),
        ),
    ]
