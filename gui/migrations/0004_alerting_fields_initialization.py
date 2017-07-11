# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models, transaction


# noinspection PyUnusedLocal
def initialize_alerting_fields(apps, schema_editor):
    former_user_profile = apps.get_model('gui', 'UserProfile')
    if former_user_profile.objects.count() > 10000:
        warning_text = "\n It looks like there is a lot of users in your database and " \
                       "it would take a lot of time to update their profiles. This migration is therefore skipped. " \
                       "If you need to, perform this operation manually."
        Warning(warning_text)
        # Migrate command does not print warnings to the stdout
        print(warning_text)
    else:
        with transaction.atomic():
            # Cannot user F() expressions to joined tables
            for user_profile in former_user_profile.objects.select_related('user__email').iterator():
                user_profile.alerting_email = user_profile.user.email
                user_profile.alerting_phone = user_profile.phone
                user_profile.alerting_jabber = user_profile.jabber
                user_profile.save()


class Migration(migrations.Migration):
    dependencies = [
        ('gui', '0003_add_alerting_user_fields'),
    ]

    operations = [
        migrations.RunPython(initialize_alerting_fields, reverse_code=lambda x, y: None)
    ]
