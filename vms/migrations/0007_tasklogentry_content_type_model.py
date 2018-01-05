# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vms', '0006_subnet_mtu'),
    ]

    operations = [
        migrations.AddField(
            model_name='tasklogentry',
            name='content_type_model',
            field=models.CharField(max_length=32, verbose_name='object type', blank=True),
        ),
    ]
