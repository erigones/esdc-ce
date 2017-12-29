# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0005_add_monitoring_admin_permission'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='language',
            field=models.CharField(default=b'en', max_length=10, verbose_name='Language', choices=[(b'en', b'English')]),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='phone',
            field=models.CharField(max_length=32, verbose_name='Phone', blank=True),
        ),
    ]
