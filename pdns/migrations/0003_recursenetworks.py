# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from pdns.models import RecurseNetworks
from vms.models import Subnet


def sync_recurse_subnets(*args, **kwargs):
    [RecurseNetworks.add_or_update_entry(subnet=str(net.ip_network), net_name=net.name) for net in Subnet.objects.all()]

def noop_reverse(*args, **kwargs):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('pdns', '0002_pdns_config'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecurseNetworks',
            fields=[
                ('id', models.AutoField(help_text=b'Unique handle for network entries', serialize=False, primary_key=True)),
                ('subnet', models.CharField(help_text=b'Network subnet to allow recursion from (format: x.x.x.x/yy)', max_length=50, verbose_name='Subnet', db_index=True)),
                ('net_name', models.CharField(help_text=b'Network name in the danube networks list', max_length=50, verbose_name='Network name', db_index=True)),
                ('change_date', models.IntegerField(default=None, help_text=b'Timestamp of the last update.', null=True, verbose_name='Changed')),
            ],
            options={
                'db_table': 'recurse_networks',
                'verbose_name': 'Recursion subnet',
                'verbose_name_plural': 'Recursion subnets',
            },
        ),
        migrations.RunPython(sync_recurse_subnets, noop_reverse),
    ]
