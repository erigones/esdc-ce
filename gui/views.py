from django.shortcuts import redirect
from django.views.i18n import javascript_catalog
from django.views.decorators.http import last_modified
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from api.decorators import setting_required
from gui.decorators import profile_required, admin_required


last_modified_date = timezone.now()


@last_modified(lambda req, **kw: last_modified_date)
def cached_javascript_catalog(request, domain='djangojs', packages=None):
    """
    https://docs.djangoproject.com/en/1.5/topics/i18n/translation/#note-on-performance
    """
    return javascript_catalog(request, domain, packages)


@login_required
@admin_required
@profile_required
@setting_required('MON_ZABBIX_ENABLED')
def monitoring(request):
    """
    Monitoring management.
    """
    return redirect(request.dc.settings.MON_ZABBIX_SERVER)
