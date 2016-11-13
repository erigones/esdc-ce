# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gui', '0001_initial'),
        ('vms', '0001_initial'),
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='dc_bound',
            field=models.ForeignKey(related_name='role_dc_bound_set', on_delete=django.db.models.deletion.SET_NULL, default=None, blank=True, to='vms.Dc', null=True),
        ),
        migrations.AddField(
            model_name='role',
            name='permissions',
            field=models.ManyToManyField(to='gui.Permission', verbose_name='permissions', blank=True),
        ),
        migrations.AddField(
            model_name='user',
            name='dc_bound',
            field=models.ForeignKey(related_name='user_dc_bound_set', on_delete=django.db.models.deletion.SET_NULL, default=None, blank=True, to='vms.Dc', null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='default_dc',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_DEFAULT, default=1, to='vms.Dc', null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='groups',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Group', blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', verbose_name='groups'),
        ),
        migrations.AddField(
            model_name='user',
            name='roles',
            field=models.ManyToManyField(help_text='The groups this object belongs to. A object will get all permissions granted to each of its groups.', to='gui.Role', verbose_name='Groups', blank=True),
        ),
        migrations.AddField(
            model_name='user',
            name='user_permissions',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Permission', blank=True, help_text='Specific permissions for this user.', verbose_name='user permissions'),
        ),
        migrations.AlterUniqueTogether(
            name='usersshkey',
            unique_together=set([('user', 'fingerprint'), ('user', 'title')]),
        ),
    ]
