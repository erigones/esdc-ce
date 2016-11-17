# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vms', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ipaddress',
            name='vms',
            field=models.ManyToManyField(related_name='allowed_ips', verbose_name='Servers', to='vms.Vm', blank=True),
        ),
    ]
