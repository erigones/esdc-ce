from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render, Http404
from django.views.decorators.http import require_POST

from gui.decorators import staff_required, ajax_required, admin_required, profile_required, permission_required
from gui.utils import collect_view_data, reverse, redirect, get_query_string, get_order_by, get_pager
from gui.models.permission import DnsAdminPermission
from gui.dc.dns.forms import DcDomainForm, AdminDomainForm, DnsRecordFilterForm, DnsRecordForm, MultiDnsRecordForm
from gui.dc.dns.utils import get_domain
from api.decorators import setting_required
from api.dns.domain.utils import prefetch_domain_owner, prefetch_domain_dcs
from api.dns.record.api_views import RecordView
from pdns.models import Domain, Record


@login_required
@admin_required
@profile_required
@setting_required('DNS_ENABLED')
def dc_domain_list(request):
    """
    DNS Domain/Record <-> Dc management.
    """
    user, dc = request.user, request.dc
    domains = Domain.objects.order_by('name')
    dc_domain_ids = list(request.dc.domaindc_set.values_list('domain_id', flat=True))
    context = collect_view_data(request, 'dc_domain_list')
    context['is_staff'] = is_staff = user.is_staff
    context['can_edit'] = can_edit = is_staff or user.has_permission(request, DnsAdminPermission.name)
    context['all'] = _all = is_staff and request.GET.get('all', False)
    context['deleted'] = _deleted = can_edit and request.GET.get('deleted', False)
    qs = get_query_string(request, all=_all, deleted=_deleted)
    qs.pop('domain', None)
    context['qs'] = qs = qs.urlencode()

    if _deleted:
        domains = domains.exclude(access=Domain.INTERNAL)
    else:
        domains = domains.exclude(access__in=Domain.INVISIBLE)

    if can_edit:
        domains = domains.annotate(records=Count('record', distinct=True))

    if _all:
        context['domains'] = prefetch_domain_dcs(prefetch_domain_owner(domains))
    else:
        context['domains'] = prefetch_domain_owner(domains.filter(id__in=dc_domain_ids))

    if is_staff:
        if _all:  # Uses set() because of optimized membership ("in") checking
            context['can_add'] = set(Domain.objects.exclude(id__in=dc_domain_ids).values_list('id', flat=True))
        else:
            context['can_add'] = Domain.objects.exclude(id__in=dc_domain_ids).count()

        # Only SuperAdmins can create and edit domains
        context['form_dc'] = DcDomainForm(request, domains)
        context['form_admin'] = AdminDomainForm(request, None, prefix='adm', initial={'owner': user.username,
                                                                                      'access': Domain.PRIVATE,
                                                                                      'dc_bound': True})
        context['url_form_dc'] = reverse('dc_domain_form', query_string=qs)
        context['url_form_admin'] = reverse('admin_domain_form', query_string=qs)

    return render(request, 'gui/dc/domain_list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
@setting_required('DNS_ENABLED')
def dc_domain_form(request):
    """
    Ajax page for attaching and detaching DNS domains.
    """
    if 'adm-name' in request.POST:
        prefix = 'adm'
    else:
        prefix = None

    form = DcDomainForm(request, Domain.objects.all().order_by('name'), request.POST, prefix=prefix)

    if form.is_valid():
        status = form.save(args=(form.cleaned_data['name'],))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('dc_domain_list', query_string=request.GET)

    # An error occurred when attaching or detaching object
    if prefix:
        # The displayed form was an admin form, so we need to return the admin form back
        # But with errors from the attach/detach form
        try:
            domain = Domain.objects.get(name=request.POST['adm-name'])
        except Domain.DoesNotExist:
            domain = None

        form_admin = AdminDomainForm(request, domain, request.POST, prefix=prefix)
        # noinspection PyProtectedMember
        form_admin._errors = form._errors
        form = form_admin
        template = 'gui/dc/domain_admin_form.html'
    else:
        template = 'gui/dc/domain_dc_form.html'

    return render(request, template, {'form': form})


@login_required
@admin_required  # SuperAdmin or DCAdmin+DnsAdmin
@permission_required(DnsAdminPermission)
@ajax_required
@require_POST
@setting_required('DNS_ENABLED')
def admin_domain_form(request):
    """
    Ajax page for updating, removing and adding DNS domains.
    """
    qs = request.GET.copy()
    nodc = request.GET.get('nodc', '')

    if request.POST['action'] == 'create':
        domain = None
    else:
        domain = get_domain(request, request.POST['adm-name'])

    form = AdminDomainForm(request, domain, request.POST, prefix='adm')

    if form.is_valid():
        args = (form.cleaned_data['name'],)
        status = form.save(args=args)

        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            if form.action == 'create' and not form.cleaned_data.get('dc_bound'):
                qs['all'] = 1  # Show all items if adding new item and not attaching

            return redirect('dc_domain_list', query_string=qs)

    return render(request, 'gui/dc/domain_admin_form.html', {'form': form, 'nodc': nodc})


@login_required
@admin_required  # SuperAdmin or DCAdmin+DnsAdmin
@permission_required(DnsAdminPermission)
@setting_required('DNS_ENABLED')
def dc_domain_record_list(request):
    """
    List/filter DNS records for a DNS domain (domain parameter in querystring).
    """
    context = collect_view_data(request, 'dc_domain_list', dc_dns_only=True)
    context['is_staff'] = is_staff = request.user.is_staff
    qs = request.GET.copy()
    name = qs.get('flt-domain', None)
    context['all'] = _all = is_staff and request.GET.get('all', request.GET.get('flt-all', False))
    qs['flt-all'] = '1' if _all else ''

    if not name:
        raise PermissionDenied

    context['domain'] = domain = get_domain(request, name)
    context['filters'] = filter_form = DnsRecordFilterForm(request, qs, _all=_all, prefix='flt')
    context['qs'] = qs.urlencode()
    context['order_by'], order_by = get_order_by(request, api_view=RecordView, db_default=('-id',),
                                                 user_default=('-id',))
    records = domain.record_set.order_by(*order_by)

    if filter_form.is_valid() and filter_form.has_changed():
        q = filter_form.get_filters()

        if q:
            records = records.filter(q)

    context['records'] = context['pager'] = get_pager(request, records, per_page=50)
    context['form_record'] = DnsRecordForm(request, domain, None, initial={'prio': Record.PRIO, 'ttl': Record.TTL,
                                                                           'type': Record.A, 'id': 0,
                                                                           'disabled': False,
                                                                           'name': '.%s' % domain.name})
    context['form_records'] = MultiDnsRecordForm(request, domain, None)
    context['url_form_record'] = reverse('domain_record_form', name, query_string=qs)

    return render(request, 'gui/dc/domain_record_list.html', context)


@login_required
@admin_required  # SuperAdmin or DCAdmin+DnsAdmin
@permission_required(DnsAdminPermission)
@ajax_required
@require_POST
@setting_required('DNS_ENABLED')
def domain_record_form(request, name):
    """
    Ajax page for updating, removing and adding DNS records.
    """
    domain = get_domain(request, name)
    form_class = DnsRecordForm

    if request.POST['action'] == 'update':
        try:
            record = Record.objects.get(domain=domain, id=request.POST.get('id'))
        except Record.DoesNotExist:
            raise Http404
    else:
        record = None
        if request.POST.get('records', False):
            form_class = MultiDnsRecordForm

    form = form_class(request, domain, record, request.POST)

    if form.is_valid():
        status = form.save(args=form.api_call_args(domain.name))

        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            assert request.GET['flt-domain'] == domain.name
            return redirect('dc_domain_record_list', query_string=request.GET)

    return render(request, form.template, {'form': form, 'domain': domain})
