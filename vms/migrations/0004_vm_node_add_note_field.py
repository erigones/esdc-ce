# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vms', '0003_backup_manifest_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='node',
            name='note',
            field=models.TextField(verbose_name='Note', blank=True),
        ),
        migrations.AddField(
            model_name='vm',
            name='note',
            field=models.TextField(verbose_name='Note', blank=True),
        ),
    ]
