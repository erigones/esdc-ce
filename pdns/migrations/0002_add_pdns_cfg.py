# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pdns', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='cfg_recursor',
            fields=[
                ('key', models.CharField(help_text=b'PowerDNS Recursor configuration parameter keys', unique=True, null=False, max_length=32, verbose_name='Config key', primary_key=True, db_index=True)),
                ('val', models.TextField(help_text=b'PowerDNS Recursor configuration parameter values', default='', verbose_name='Config value')),
            ],
            options={
                'db_table': 'cfg_recursor',
                'verbose_name': 'PowerDNS Recursor config',
                'verbose_name_plural': 'pdns recursor config',
            },
        ),

        migrations.CreateModel(
            name='cfg_pdns',
            fields=[
                ('key', models.CharField(help_text=b'PowerDNS Server configuration parameter keys', unique=True, null=False, max_length=32, verbose_name='Config key', primary_key=True, db_index=True)),
                ('val', models.TextField(help_text=b'PowerDNS Server configuration parameter values', default='', verbose_name='Config value')),
            ],
            options={
                'db_table': 'cfg_pdns',
                'verbose_name': 'PowerDNS config',
                'verbose_name_plural': 'pdns config',
            },
        ),

		# add table for PDNS config
        migrations.RunSQL("""
        create table cfg_recursor (
            key     varchar(32) NOT NULL PRIMARY KEY, 
            val     text
        );
        CREATE UNIQUE INDEX cfg_recursor_index ON cfg_recursor(key);

        create table cfg_pdns (
            key     varchar(32) NOT NULL PRIMARY KEY, 
            val     text
        );
        CREATE UNIQUE INDEX cfg_pdns_index ON cfg_pdns(key);

        create or replace function public.pdns_domains_notify() returns trigger as $BODY$
        begin
        perform pg_notify('pdns_notify', 'domains_modified');
        return new;
        end;
        $BODY$
        language 'plpgsql' volatile cost 100;

        create trigger pdns_domains_changed after insert or update or delete on public.domains execute procedure public.pdns_domains_notify();

        create or replace function public.pdns_recursor_cfg_notify() returns trigger as $BODY$
        begin
        perform pg_notify('pdns_notify', 'recursor_cfg_modified');
        return new;
        end;
        $BODY$
        language 'plpgsql' volatile cost 100;

        create trigger pdns_recursor_cfg_changed after insert or update or delete on public.cfg_recursor execute procedure public.pdns_recursor_cfg_notify();

        create or replace function public.pdns_cfg_notify() returns trigger as $BODY$
        begin
        perform pg_notify('pdns_notify', 'pdns_cfg_modified');
        return new;
        end;
        $BODY$
        language 'plpgsql' volatile cost 100;

        create trigger pdns_cfg_changed after insert or update or delete on public.cfg_pdns execute procedure public.pdns_cfg_notify();

        """,
        """
        drop table cfg_recursor;
        drop table cfg_pdns;
        drop trigger pdns_domains_changed on domains;
        drop trigger pdns_recursor_cfg_changed on domains;
        drop trigger pdns_cfg_changed on domains;
        """
        ),
    ]
