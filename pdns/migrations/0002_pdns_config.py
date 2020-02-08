# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import pdns.models.pdns_config


class Migration(migrations.Migration):

    dependencies = [
        ('pdns', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PdnsCfg',
            fields=[
                ('key', models.CharField(primary_key=True, serialize=False, max_length=32, help_text=b'PowerDNS configuration parameter keys', unique=True, null=False, verbose_name='Key', db_index=True)),
                ('val', models.TextField(default=None, help_text=b'PowerDNS configuration parameter values', null=True, verbose_name='Value')),
                ('change_date', models.IntegerField(default=None, help_text=b'Timestamp for the last update.', null=True, verbose_name='Changed')),
            ],
            options={
                'db_table': 'cfg_pdns',
                'verbose_name': 'PowerDNS config entry',
                'verbose_name_plural': 'PowerDNS config entries',
            },
            bases=(models.Model, pdns.models.pdns_config.DummyPdnsCfg),
        ),
        migrations.CreateModel(
            name='PdnsRecursorCfg',
            fields=[
                ('key', models.CharField(primary_key=True, serialize=False, max_length=32, help_text=b'PowerDNS Recursor configuration parameter keys', unique=True, null=False, verbose_name='Key', db_index=True)),
                ('val', models.TextField(default=None, help_text=b'PowerDNS Recursor configuration parameter values', null=True, verbose_name='Value')),
                ('change_date', models.IntegerField(default=None, help_text=b'Timestamp for the last update.', null=True, verbose_name='Changed')),
            ],
            options={
                'db_table': 'cfg_recursor',
                'verbose_name': 'PowerDNS recursor cfg entry',
                'verbose_name_plural': 'PowerDNS recursor config entries',
            },
            bases=(models.Model, pdns.models.pdns_config.DummyPdnsCfg),
        ),
        migrations.RunSQL([
            "GRANT select ON cfg_recursor TO pdns",
            "GRANT select ON cfg_pdns TO pdns"
			], [
            "REVOKE select ON cfg_recursor TO pdns",
            "REVOKE select ON cfg_pdns TO pdns"
			]
        ),
    ]
