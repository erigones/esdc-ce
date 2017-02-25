from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from gui.decorators import staff_required
from gui.utils import collect_view_data
from gui.system.utils import GraphItem
from vms.models import Dc, Node, Vm


@login_required
@staff_required
def overview(request):
    """
    Overview/stats of the whole system.
    """
    context = collect_view_data(request, 'system_overview')
    context['dc'] = (
        GraphItem('public', Dc.objects.filter(access=Dc.PUBLIC).count()),
        GraphItem('private', Dc.objects.filter(access=Dc.PRIVATE).count()),
    )
    context['dc_total'] = sum(i.data for i in context['dc'])
    context['node'] = (
        GraphItem('offline', Node.objects.filter(status=Node.OFFLINE).count(), color='#b94a48'),
        GraphItem('online', Node.objects.filter(status=Node.ONLINE).count(), color='#468847'),
        GraphItem('unreachable', Node.objects.filter(status=Node.UNREACHABLE).count(), color='#f89406'),
        GraphItem('unlicensed', Node.objects.filter(status=Node.UNLICENSED).count(), color='#999999'),
    )
    context['node_total'] = sum(i.data for i in context['node'])
    context['vm'] = (
        GraphItem('notcreated', Vm.objects.filter(status__in=(Vm.NOTCREATED,
                                                              Vm.NOTREADY_NOTCREATED,
                                                              Vm.CREATING,
                                                              Vm.DEPLOYING_START,
                                                              Vm.DEPLOYING_FINISH,
                                                              Vm.DEPLOYING_DUMMY)).count(),
                  color='#999999'),
        GraphItem('stopped', Vm.objects.filter(status__in=(Vm.STOPPED, Vm.NOTREADY_STOPPED)).count(),
                  color='#b94a48'),
        GraphItem('running', Vm.objects.filter(status__in=(Vm.RUNNING, Vm.STOPPING, Vm.NOTREADY_RUNNING)).count(),
                  color='#468847'),
        GraphItem('frozen', Vm.objects.filter(status__in=(Vm.FROZEN, Vm.NOTREADY_FROZEN)).count(),
                  color='#ddffff'),
        GraphItem('unknown', Vm.objects.filter(status__in=(Vm.NOTREADY, Vm.ERROR)).count(),
                  color='#333333'),
    )
    context['vm_total'] = sum(i.data for i in context['vm'])

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
