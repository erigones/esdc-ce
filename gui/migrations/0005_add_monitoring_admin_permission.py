# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def insert_monitoring_admin_permission(apps, schema_editor):
    Permission = apps.get_model('gui', 'Permission')
    monitoring_admin = Permission(name='monitoring_admin', alias='MonitoringAdmin')
    monitoring_admin.save()


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0004_alerting_fields_initialization'),
    ]

    operations = [
        migrations.RunPython(insert_monitoring_admin_permission),
    ]
