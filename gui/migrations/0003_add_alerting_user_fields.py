# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0002_dc_relation'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='alerting_email',
            field=models.EmailField(max_length=255, verbose_name='Email address', blank=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='alerting_jabber',
            field=models.EmailField(max_length=255, verbose_name='Jabber', blank=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='alerting_phone',
            field=models.CharField(max_length=32, verbose_name='Phone', blank=True),
        ),
    ]
