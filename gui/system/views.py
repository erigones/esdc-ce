from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from gui.decorators import staff_required
from gui.utils import collect_view_data
from gui.system.utils import GraphItem
from api.system.stats.api_views import SystemStatsView


NODE_STATS_COLORS = {
    'maintenance': '#684688',
    'online': '#468847',
    'unreachable': '#f89406',
    'unlicensed': '#999999',
}

VM_STATS_COLORS = {
    'notcreated': '#999999',
    'stopped': '#b94a48',
    'running': '#468847',
    'frozen': '#ddffff',
    'unknown': '#333333',
}


@login_required
@staff_required
def overview(request):
    """
    Overview/stats of the whole system.
    """
    context = collect_view_data(request, 'system_overview')
    context['stats'] = stats = SystemStatsView.get_stats()
    stats['dcs'] = [GraphItem(label, data) for label, data in stats['dcs'].items()]
    stats['nodes'] = [GraphItem(label, data, color=NODE_STATS_COLORS[label]) for label, data in stats['nodes'].items()]
    stats['vms'] = [GraphItem(label, data, color=VM_STATS_COLORS[label]) for label, data in stats['vms'].items()]

    return render(request, 'gui/system/overview.html', context)


@login_required
@staff_required
def settings(request):
    """
    System settings.
    """
    context = collect_view_data(request, 'system_settings')

    return render(request, 'gui/system/settings.html', context)


@login_required
@staff_required
def maintenance(request):
    """
    System maintenance.
    """
    context = collect_view_data(request, 'system_maintenance')

    return render(request, 'gui/system/maintenance.html', context)
