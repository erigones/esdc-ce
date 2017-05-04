from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from gui.decorators import profile_required, admin_required
from api.decorators import setting_required


@login_required
@admin_required
@profile_required
@setting_required('MON_ZABBIX_ENABLED')
def monitoring_server(request):
    """
    Monitoring management.
    """
    return redirect(request.dc.settings.MON_ZABBIX_SERVER)
