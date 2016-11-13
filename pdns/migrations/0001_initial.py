# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Domain',
            fields=[
                ('id', models.AutoField(help_text=b'This field is used to easily manage the domains with this number as an unique handle.', serialize=False, primary_key=True)),
                ('name', models.CharField(help_text=b'This field is the actual domain name. This is the field that powerDNS matches to when it gets a request. The domain name should be in the format of: domainname.TLD.', unique=True, max_length=255, verbose_name='Name')),
                ('master', models.CharField(default=None, max_length=128, null=True, verbose_name='Master', help_text=b'This describes the master nameserver from which this domain should be slaved.')),
                ('last_check', models.IntegerField(default=None, help_text=b'Last time this domain was checked for freshness.', null=True, verbose_name='Last check')),
                ('type', models.CharField(help_text=b'Type of the domain.', max_length=6, verbose_name='Type', db_index=True, choices=[(b'MASTER', b'Master'), (b'SLAVE', b'Slave'), (b'NATIVE', b'Native'), (b'SUPERSLAVE', b'Superslave')])),
                ('notified_serial', models.IntegerField(default=None, help_text=b'The last notified serial of a master domain. This is updated from the SOA record of the domain.', null=True, verbose_name='Notified serial')),
                ('account', models.CharField(default=None, max_length=40, null=True, verbose_name='Account', help_text=b'Determine if a certain host is a supermaster for a certain domain name.')),
                ('user', models.IntegerField(default=None, help_text=b'Field representing the user ID responsible for the domain. Added by Erigones.', null=True, verbose_name='User', db_index=True)),
                ('desc', models.CharField(help_text=b'Added by Erigones.', max_length=128, verbose_name='Description', blank=True)),
                ('access', models.SmallIntegerField(default=3, help_text=b'Added by Erigones.', verbose_name='Access', choices=[(1, 'Public'), (3, 'Private')])),
                ('created', models.DateTimeField(auto_now_add=True, help_text=b'Added by Erigones.', null=True, verbose_name='Created')),
                ('changed', models.DateTimeField(auto_now=True, help_text=b'Added by Erigones.', null=True, verbose_name='Last changed')),
                ('dc_bound', models.IntegerField(default=None, help_text=b'Datacenter ID used for DC-bound DNS records. Added by Erigones.', null=True, verbose_name='Datacenter')),
            ],
            options={
                'db_table': 'domains',
                'verbose_name': 'Domain',
                'verbose_name_plural': 'Domains',
            },
        ),
        migrations.CreateModel(
            name='Record',
            fields=[
                ('id', models.AutoField(help_text=b'This field is used to easily manage the records with this number as an unique handle.', serialize=False, primary_key=True)),
                ('name', models.CharField(default=None, max_length=255, help_text=b'What URI the dns-server should pick up on. For example www.test.com.', null=True, verbose_name='Name', db_index=True)),
                ('type', models.CharField(default=None, choices=[(b'SOA', b'SOA'), (b'NS', b'NS'), (b'MX', b'MX'), (b'A', b'A'), (b'AAAA', b'AAAA'), (b'CNAME', b'CNAME'), (b'TXT', b'TXT'), (b'PTR', b'PTR'), (b'SRV', b'SRV'), (b'SPF', b'SPF'), (b'HINFO', b'HINFO'), (b'NAPTR', b'NAPTR'), (b'SSHFP', b'SSHFP'), (b'RP', b'RP'), (b'LOC', b'LOC'), (b'KEY', b'KEY'), (b'CERT', b'CERT'), (b'TLSA', b'TLSA')], max_length=6, help_text=b'The ASCII representation of the qtype of this record.', null=True, verbose_name='Type')),
                ('content', models.CharField(default=None, max_length=65535, null=True, verbose_name='Content', help_text=b'Is the answer of the DNS-query and the content depend on the type field.')),
                ('ttl', models.IntegerField(default=None, help_text=b'How long the DNS-client are allowed to remember this record. Also known as Time To Live (TTL) This value is in seconds.', null=True, verbose_name='TTL')),
                ('prio', models.IntegerField(default=None, help_text=b'This field sets the priority of an MX-field.', null=True, verbose_name='Priority')),
                ('change_date', models.IntegerField(default=None, help_text=b'Timestamp for the last update.', null=True, verbose_name='Changed')),
                ('disabled', models.BooleanField(default=False, help_text=b'If set to true, this record is hidden from DNS clients, but can still be modified from the REST API.', verbose_name='Disabled?')),
                ('ordername', models.CharField(default=None, max_length=255, null=True, verbose_name='Ordername')),
                ('auth', models.BooleanField(default=True, verbose_name='Auth')),
                ('domain', models.ForeignKey(db_constraint=False, db_column=b'domain_id', default=None, to='pdns.Domain', help_text=b'This field binds the current record to the unique handle(the id-field) in the domains-table.', null=True)),
            ],
            options={
                'db_table': 'records',
                'verbose_name': 'Record',
                'verbose_name_plural': 'Records',
            },
        ),
        migrations.AlterIndexTogether(
            name='record',
            index_together=set([('name', 'type')]),
        ),

        # Update domains table
        migrations.RunSQL("""
    ALTER TABLE domains ADD CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = lower((name)::TEXT)));
    ALTER TABLE domains ALTER COLUMN "access" SET DEFAULT 3;
    ALTER TABLE domains ALTER COLUMN "desc" SET DEFAULT '';
    ALTER TABLE domains ALTER COLUMN "user" SET DEFAULT 1;
    GRANT ALL ON domains TO pdns;
    GRANT ALL ON domains_id_seq TO pdns;
            """),

        # Update records table
        migrations.RunSQL("""
    ALTER TABLE records ADD CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = lower((name)::TEXT)));
    ALTER TABLE records ADD CONSTRAINT domain_exists FOREIGN KEY(domain_id) REFERENCES domains(id) ON DELETE CASCADE;
    ALTER TABLE records ALTER COLUMN "disabled" SET DEFAULT false;
    ALTER TABLE records ALTER COLUMN "auth" SET DEFAULT false;
    CREATE INDEX recordorder ON records (domain_id, ordername text_pattern_ops);
    GRANT ALL ON records TO pdns;
    GRANT ALL ON records_id_seq TO pdns;
        """),

        # Create other PowerDNS tables
        migrations.RunSQL("""
    CREATE TABLE supermasters (
      ip                    INET NOT NULL,
      nameserver            VARCHAR(255) NOT NULL,
      account               VARCHAR(40) NOT NULL,
      PRIMARY KEY(ip, nameserver)
    );

    GRANT ALL ON supermasters TO pdns;


    CREATE TABLE comments (
      id                    SERIAL PRIMARY KEY,
      domain_id             INT NOT NULL,
      name                  VARCHAR(255) NOT NULL,
      type                  VARCHAR(10) NOT NULL,
      modified_at           INT NOT NULL,
      account               VARCHAR(40) DEFAULT NULL,
      comment               VARCHAR(65535) NOT NULL,
      CONSTRAINT domain_exists
      FOREIGN KEY(domain_id) REFERENCES domains(id)
      ON DELETE CASCADE,
      CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
    );

    CREATE INDEX comments_domain_id_idx ON comments (domain_id);
    CREATE INDEX comments_name_type_idx ON comments (name, type);
    CREATE INDEX comments_order_idx ON comments (domain_id, modified_at);

    GRANT ALL ON comments TO pdns;
    GRANT ALL ON comments_id_seq TO pdns;


    CREATE TABLE domainmetadata (
      id                    SERIAL PRIMARY KEY,
      domain_id             INT REFERENCES domains(id) ON DELETE CASCADE,
      kind                  VARCHAR(32),
      content               TEXT
    );

    CREATE INDEX domainidmetaindex ON domainmetadata(domain_id);

    GRANT ALL ON domainmetadata TO pdns;
    GRANT ALL ON domainmetadata_id_seq TO pdns;


    CREATE TABLE cryptokeys (
      id                    SERIAL PRIMARY KEY,
      domain_id             INT REFERENCES domains(id) ON DELETE CASCADE,
      flags                 INT NOT NULL,
      active                BOOL,
      content               TEXT
    );

    CREATE INDEX domainidindex ON cryptokeys(domain_id);

    GRANT ALL ON cryptokeys TO pdns;
    GRANT ALL ON cryptokeys_id_seq TO pdns;


    CREATE TABLE tsigkeys (
      id                    SERIAL PRIMARY KEY,
      name                  VARCHAR(255),
      algorithm             VARCHAR(50),
      secret                VARCHAR(255),
      CONSTRAINT c_lowercase_name CHECK (((name)::TEXT = LOWER((name)::TEXT)))
    );

    CREATE UNIQUE INDEX namealgoindex ON tsigkeys(name, algorithm);

    GRANT ALL ON tsigkeys TO pdns;
    GRANT ALL ON tsigkeys_id_seq TO pdns;
        """),
    ]
