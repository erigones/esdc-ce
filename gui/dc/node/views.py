from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import HttpResponse, Http404

from vms.models import Node, DcNode
from gui.fields import SIZE_FIELD_MB_ADDON
from gui.decorators import staff_required, ajax_required, admin_required, profile_required
from gui.utils import collect_view_data, redirect, get_query_string
from gui.dc.node.forms import DcNodeForm
from api.dc.node.utils import get_dc_nodes


@login_required
@admin_required
@profile_required
def dc_node_list(request):
    """
    Compute node <-> Datacenter associations.
    """
    context = collect_view_data(request, 'dc_node_list', mb_addon=SIZE_FIELD_MB_ADDON)
    context['can_edit'] = can_edit = request.user.is_staff  # DC owners have read-only rights
    context['all'] = _all = can_edit and request.GET.get('all', False)
    context['qs'] = get_query_string(request, all=_all).urlencode()
    context['dc_nodes'] = get_dc_nodes(request, prefetch_dc=_all, prefetch_vms_count=True)

    if can_edit:
        context['form'] = DcNodeForm(request, None, initial={'strategy': DcNode.SHARED, 'priority': DcNode.PRIORITY})
        if _all:
            context['can_add'] = Node.objects.exclude(dc=request.dc)
        else:
            context['can_add'] = Node.objects.exclude(dc=request.dc).exists()

    return render(request, 'gui/dc/node_list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def dc_node_form(request):
    """
    Ajax page for creating or updating Compute node <-> Datacenter associations.
    """
    if request.POST['action'] == 'create':
        dc_node = None
    else:
        try:
            node = Node.objects.get(hostname=request.POST['hostname'])
            dc_node = DcNode.objects.select_related('dc', 'node').get(dc=request.dc, node=node)
        except (Node.DoesNotExist, DcNode.DoesNotExist):
            raise Http404

    form = DcNodeForm(request, dc_node, request.POST)

    if form.is_valid():
        status = form.save(args=(form.cleaned_data.get('hostname'),))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):

            return redirect('dc_node_list', query_string=request.GET)

    return render(request, 'gui/dc/node_form.html', {'form': form, 'mb_addon': SIZE_FIELD_MB_ADDON})
