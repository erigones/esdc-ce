from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from gui.decorators import staff_required, ajax_required
from gui.utils import collect_view_data
from gui.node.forms import NodeStatusForm
from gui.system.utils import GraphItem
from gui.system.forms import UpdateForm, NodeUpdateForm
from api.utils.views import call_api_view
from api.system.stats.api_views import SystemStatsView
from api.system.base.views import system_version
from vms.models import Node


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
    context['system'] = call_api_view(request, 'GET', system_version).data.get('result', {})
    context['node_list'] = Node.all()
    context['current_view'] = 'maintenance'
    context['status_form'] = NodeStatusForm(request, None)
    context['update_form'] = UpdateForm(request, None)
    context['node_update_form'] = NodeUpdateForm(request, None, prefix='node')

    return render(request, 'gui/system/maintenance.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def system_update_form(request):
    """
    Ajax page for running system update on mgmt VM.
    """
    form = UpdateForm(request, None, request.POST, request.FILES)

    if form.is_valid():
        if form.call_system_update() == 201:
            return redirect('system_maintenance')

    return render(request, 'gui/system/update_form.html', {'form': form})


@login_required
@staff_required
@ajax_required
@require_POST
def system_node_update_form(request):
    """
    Ajax page for running system update on selected compute nodes.
    """
    form = NodeUpdateForm(request, None, request.POST, request.FILES, prefix='node')

    if form.is_valid():
        res = [form.call_system_node_update(hostname) == 201 for hostname in form.cleaned_data['hostnames']]

        if all(res):
            return redirect('system_maintenance')

    return render(request, 'gui/system/node_update_form.html', {'form': form})
