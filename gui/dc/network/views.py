from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.shortcuts import render, Http404
from django.http import HttpResponse
from django.db.models import Q
from functools import reduce
from operator import and_

from gui.decorators import staff_required, ajax_required, admin_required, profile_required, permission_required
from gui.utils import collect_view_data, reverse, redirect, get_order_by, get_pager, get_query_string
from gui.models.permission import NetworkAdminPermission
from gui.dc.network.forms import DcNetworkForm, AdminNetworkForm, NetworkIPForm, MultiNetworkIPForm
from api.network.ip.api_views import NetworkIPView, NetworkIPPlanView
from api.network.base.serializers import ExtendedNetworkSerializer
from vms.models import Subnet, IPAddress


@login_required
@admin_required
@profile_required
def dc_network_list(request):
    """
    Network/IP<->Dc management and Network management.
    """
    user, dc = request.user, request.dc
    nets = Subnet.objects.order_by('name')
    context = collect_view_data(request, 'dc_network_list')
    context['is_staff'] = is_staff = user.is_staff
    context['can_edit'] = can_edit = is_staff or user.has_permission(request, NetworkAdminPermission.name)
    context['all'] = _all = is_staff and request.GET.get('all', False)
    context['deleted'] = _deleted = can_edit and request.GET.get('deleted', False)
    context['qs'] = qs = get_query_string(request, all=_all, deleted=_deleted).urlencode()

    if _deleted:
        nets = nets.exclude(access=Subnet.INTERNAL)
    else:
        nets = nets.exclude(access__in=Subnet.INVISIBLE)

    if _all:
        _nets = nets.select_related('owner', 'dc_bound').prefetch_related('dc').all()
    else:
        _nets = nets.select_related('owner', 'dc_bound').filter(dc=dc)

    context['networks'] = _nets.extra(select=ExtendedNetworkSerializer.extra_select)

    if is_staff:
        if _all:  # Uses set() because of optimized membership ("in") checking
            context['can_add'] = set(nets.exclude(dc=dc).values_list('pk', flat=True))
        else:
            context['can_add'] = nets.exclude(dc=dc).count()

        context['form_dc'] = DcNetworkForm(request, nets)
        context['url_form_dc'] = reverse('dc_network_form', query_string=qs)

    if can_edit:
        context['url_form_admin'] = reverse('admin_network_form', query_string=qs)
        context['form_admin'] = AdminNetworkForm(request, None, prefix='adm', initial={'owner': user.username,
                                                                                       'access': Subnet.PRIVATE,
                                                                                       'dc_bound': not is_staff})

    return render(request, 'gui/dc/network_list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def dc_network_form(request):
    """
    Ajax page for attaching and detaching networks.
    """
    if 'adm-name' in request.POST:
        prefix = 'adm'
    else:
        prefix = None

    form = DcNetworkForm(request, Subnet.objects.all().order_by('name'),
                         request.POST, prefix=prefix)

    if form.is_valid():
        status = form.save(args=(form.cleaned_data['name'],))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect(request.build_absolute_uri(reverse('dc_network_list',
                                                               kwargs={'query_string': request.GET})))

    # An error occurred when attaching or detaching object
    if prefix:
        # The displayed form was an admin form, so we need to return the admin form back
        # But with errors from the attach/detach form
        try:
            net = Subnet.objects.select_related('owner', 'dc_bound').get(name=request.POST['adm-name'])
        except Subnet.DoesNotExist:
            net = None

        form_admin = AdminNetworkForm(request, net, request.POST, prefix=prefix)
        # noinspection PyProtectedMember
        form_admin._errors = form._errors
        form = form_admin
        template = 'gui/dc/network_admin_form.html'
    else:
        template = 'gui/dc/network_dc_form.html'

    return render(request, template, {'form': form})


@login_required
@admin_required  # SuperAdmin or DCAdmin+NetworkAdmin
@permission_required(NetworkAdminPermission)
@ajax_required
@require_POST
def admin_network_form(request):
    """
    Ajax page for updating, removing and adding networks.
    """
    qs = request.GET.copy()

    if request.POST['action'] == 'update':
        try:
            net = Subnet.objects.select_related('owner', 'dc_bound').get(name=request.POST['adm-name'])
        except Subnet.DoesNotExist:
            raise Http404
    else:
        net = None

    form = AdminNetworkForm(request, net, request.POST, prefix='adm')

    if form.is_valid():
        args = (form.cleaned_data['name'],)
        status = form.save(args=args)

        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            if form.action == 'create' and not form.cleaned_data.get('dc_bound'):
                qs['all'] = 1  # Show all items if adding new item and not attaching

            # Redirect to ip list or network list depending on ips parameter
            if request.GET.get('ips', False):
                redir_view = 'dc_network_ip_list'
                redir_args = (net.name,)
            else:
                redir_view = 'dc_network_list'
                redir_args = ()

            return redirect(request.build_absolute_uri(reverse(redir_view, *redir_args, kwargs={'query_string': qs})))

    return render(request, 'gui/dc/network_admin_form.html', {'form': form, 'nodc': request.GET.get('ips', '')})


@login_required
@admin_required
@profile_required
def dc_network_ip_list(request, name):
    """
    List IP addresses in network.
    DC admin can only see server IP addresses of VMs used in current DC.
    SuperAdmin user is able to see all IP addresses, including not used and reserved for other devices.
    """
    context = collect_view_data(request, 'dc_network_list')
    context['is_staff'] = is_staff = request.user.is_staff
    net_filter = {'name': name}
    dc = request.dc

    if not is_staff:
        net_filter['dc'] = dc

    try:
        context['net'] = net = Subnet.objects.select_related('owner', 'dc_bound').get(**net_filter)
    except Subnet.DoesNotExist:
        raise Http404

    context['networks'] = Subnet.objects.filter(network=net.network, netmask=net.netmask, vlan_id=net.vlan_id).count()

    context['can_edit'] = can_edit = is_staff or (net.dc_bound and
                                                  request.user.has_permission(request, NetworkAdminPermission.name))
    context['all'] = _all = can_edit and request.GET.get('all', False)
    qs = get_query_string(request, all=_all, used=can_edit)
    qs['ips'] = 1
    context['qs'] = qs.urlencode()
    ips_used = Q(usage__in=[IPAddress.VM, IPAddress.VM_REAL])
    ips_vm = (Q(vm__isnull=False) | ~Q(vms=None))
    ips_vm_dc = (Q(vm__dc=dc) | Q(vms__dc=dc))

    if can_edit:
        if is_staff:
            ips_other = Q(usage__in=[IPAddress.OTHER, IPAddress.NODE])
        else:
            ips_other = Q(usage=IPAddress.OTHER)

        ips_node = Q(usage=IPAddress.NODE)
        ip_filter = [Q(subnet=net)]
        context['used'] = used = bool(request.GET.get('used', False))

        if _all:
            if used:
                ip_filter.append((ips_used & ips_vm) | ips_other)
            elif not is_staff:
                ip_filter.append(~ips_node)
        else:
            if used:
                ip_filter.append((ips_used & ips_vm & ips_vm_dc) | ips_other)
            else:
                ip_filter.append(ips_vm_dc)

        context['netinfo'] = netinfo = net.ip_network_hostinfo
        context['form_ip'] = NetworkIPForm(request, net, None, initial={'usage': IPAddress.VM, 'count': 1,
                                                                        'ip': netinfo['min']})
        context['form_ips'] = MultiNetworkIPForm(request, net, None)
        context['form_admin'] = AdminNetworkForm(request, None, prefix='adm', initial=net.web_data_admin)
        context['url_form_admin'] = reverse('admin_network_form', query_string=qs)
        context['url_form_ip'] = reverse('network_ip_form', name, query_string=qs)
        context['colspan'] = 8
        # Complex query according to user filter
        ip_filter = reduce(and_, ip_filter)

    else:
        context['colspan'] = 6
        # No manual filtering - we have to display only DC related objects and only VMs have a DC relationship
        ip_filter = Q(subnet=net) & ips_vm_dc & ips_used & ips_vm

    context['order_by'], order_by = get_order_by(request, api_view=NetworkIPView, db_default=('ip',))
    ips = IPAddress.objects.select_related('vm', 'vm__dc', 'subnet')\
                           .prefetch_related('vms')\
                           .filter(ip_filter)\
                           .order_by(*order_by).distinct()
    context['ips'] = context['pager'] = pager = get_pager(request, ips, per_page=50)
    context['free'] = net.ipaddress_set.filter(usage=IPAddress.VM, vm__isnull=True, vms=None).count()

    if can_edit:
        context['total'] = net.ipaddress_set.count()
    else:
        context['total'] = pager.paginator.count + context['free']

    return render(request, 'gui/dc/network_ip_list.html', context)


@login_required
@admin_required  # SuperAdmin or DCAdmin+NetworkAdmin
@permission_required(NetworkAdminPermission)
@ajax_required
@require_POST
def network_ip_form(request, name):
    """
    Ajax page for updating, removing and adding network IP address(es).
    """
    try:
        net = Subnet.objects.get(name=name)
    except Subnet.DoesNotExist:
        raise Http404

    form_class = NetworkIPForm

    if request.POST['action'] == 'update':
        try:
            ip = IPAddress.objects.get(subnet=net, ip=request.POST.get('ip'))
        except IPAddress.DoesNotExist:
            raise Http404
    else:
        ip = None
        if request.POST.get('ips', False):
            form_class = MultiNetworkIPForm

    form = form_class(request, net, ip, request.POST)

    if form.is_valid():
        status = form.save(args=form.api_call_args(name))

        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            messages.success(request, form.get_action_message())
            return redirect(request.build_absolute_uri(reverse('dc_network_ip_list', net.name,
                                                               kwargs={'query_string': request.GET})))

    return render(request, form.template, {'form': form, 'net': {'name': name}})


@login_required
@staff_required
@profile_required
def dc_subnet_ip_list(request, network, netmask, vlan_id):
    context = collect_view_data(request, 'dc_network_list')
    context['is_staff'] = request.user.is_staff

    try:
        context['ip_network'] = ip_network = Subnet.get_ip_network(network, netmask)  # Invalid IPv4 network
        context['vlan_id'] = int(vlan_id)
    except ValueError:
        raise Http404

    network, netmask = ip_network.with_netmask.split('/')
    context['netinfo'] = Subnet.get_ip_network_hostinfo(ip_network)
    nets = Subnet.objects.filter(network=network, netmask=netmask, vlan_id=vlan_id)
    context['num_networks'] = num_networks = nets.count()

    if not num_networks:
        raise Http404  # Invalid user input - made-up IPv4network

    context['order_by'], order_by = get_order_by(request, api_view=NetworkIPPlanView)
    ips = IPAddress.objects.select_related('vm', 'vm__dc', 'subnet')\
                           .prefetch_related('vms')\
                           .filter(subnet__in=nets)\
                           .order_by(*order_by).distinct()
    context['ips'] = context['pager'] = pager = get_pager(request, ips, per_page=50)
    context['total'] = pager.paginator.count
    context['free'] = ips.filter(usage=IPAddress.VM, vm__isnull=True, vms=None).count()

    return render(request, 'gui/dc/subnet_ip_list.html', context)
