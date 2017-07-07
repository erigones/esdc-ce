from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.timezone import make_aware
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import render, Http404
from django.contrib import messages
from django.http import HttpResponse

from gui.decorators import staff_required, ajax_required, admin_required, profile_required, permission_required
from gui.utils import collect_view_data, redirect, reverse, get_query_string
from gui.models.permission import ImageAdminPermission, ImageImportAdminPermission
from gui.dc.image.forms import ImageForm, AdminImageForm
from api.response import JSONResponse
from api.utils.views import call_api_view
from api.imagestore.views import imagestore_manage
from vms.models import Image, ImageVm, ImageStore


@login_required
@admin_required
@profile_required
def dc_image_list(request):
    """
    Image<->Dc management + Image management.
    """
    user, dc = request.user, request.dc
    imgs = Image.objects.order_by('name')
    context = collect_view_data(request, 'dc_image_list')
    context['is_staff'] = is_staff = user.is_staff
    context['can_edit'] = can_edit = is_staff or user.has_permission(request, ImageAdminPermission.name)
    context['can_import'] = is_staff or (can_edit and user.has_permission(request, ImageImportAdminPermission.name))
    context['all'] = _all = is_staff and request.GET.get('all', False)
    context['deleted'] = _deleted = can_edit and request.GET.get('deleted', False)
    context['qs'] = qs = get_query_string(request, all=_all, deleted=_deleted).urlencode()
    context['task_id'] = request.GET.get('task_id', '')
    context['image_vm'] = ImageVm.get_uuid()

    if _deleted:
        imgs = imgs.exclude(access=Image.INTERNAL)
    else:
        imgs = imgs.exclude(access__in=Image.INVISIBLE)

    if _all:
        context['images'] = imgs.select_related('owner', 'dc_bound').prefetch_related('dc').all()
    else:
        context['images'] = imgs.select_related('owner', 'dc_bound').filter(dc=dc)

    if is_staff:
        if _all:  # Uses set() because of optimized membership ("in") checking
            context['can_add'] = set(imgs.exclude(dc=dc).values_list('pk', flat=True))
        else:
            context['can_add'] = imgs.exclude(dc=dc).count()

        context['form_dc'] = ImageForm(request, imgs)
        context['url_form_dc'] = reverse('dc_image_form', query_string=qs)

    if can_edit:
        context['url_form_admin'] = reverse('admin_image_form', query_string=qs)
        context['form_admin'] = AdminImageForm(request, None, prefix='adm', initial={'owner': user.username,
                                                                                     'access': Image.PRIVATE,
                                                                                     'dc_bound': True})

    return render(request, 'gui/dc/image_list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def dc_image_form(request):
    """
    Ajax page for attaching and detaching images.
    """
    if 'adm-name' in request.POST:
        prefix = 'adm'
    else:
        prefix = None

    form = ImageForm(request, Image.objects.all().order_by('name'), request.POST, prefix=prefix)

    if form.is_valid():
        status = form.save(args=(form.cleaned_data['name'],))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('dc_image_list', query_string=request.GET)

    # An error occurred when attaching or detaching object
    if prefix:
        # The displayed form was an admin form, so we need to return the admin form back
        # But with errors from the attach/detach form
        try:
            img = Image.objects.select_related('owner', 'dc_bound').get(name=request.POST['adm-name'])
        except Image.DoesNotExist:
            img = None

        form_admin = AdminImageForm(request, img, request.POST, prefix=prefix)
        # noinspection PyProtectedMember
        form_admin._errors = form._errors
        form = form_admin
        template = 'gui/dc/image_admin_form.html'
    else:
        template = 'gui/dc/image_dc_form.html'

    return render(request, template, {'form': form})


@login_required
@admin_required  # SuperAdmin or DCAdmin+ImageAdmin
@permission_required(ImageAdminPermission)  # For imports the ImageImportAdmin permission is required
@ajax_required
@require_POST
def admin_image_form(request):
    """
    Ajax page for updating, removing and importing server images.
    """
    qs = request.GET.copy()

    if request.POST['action'] == 'update':
        try:
            img = Image.objects.select_related('owner', 'dc_bound').get(name=request.POST['adm-name'])
        except Image.DoesNotExist:
            raise Http404
    else:
        img = None

    form = AdminImageForm(request, img, request.POST, prefix='adm')

    if form.is_valid():
        img_name = form.cleaned_data['name']
        status = form.save(args=(img_name,))

        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            qs['task_id'] = form.task_id  # Add task ID into last task IDs array

            if form.action == 'create' and not form.cleaned_data.get('dc_bound'):
                qs['all'] = 1  # Show all items if adding new item and not attaching

            if status == 201:
                qs['last_img'] = img_name

            return redirect('dc_image_list', query_string=qs)

    return render(request, 'gui/dc/image_admin_form.html', {'form': form})


@login_required
@admin_required  # SuperAdmin or DCAdmin+ImageAdmin
@permission_required(ImageAdminPermission)
@permission_required(ImageImportAdminPermission)
def imagestore_list(request, repo=None):
    user, dc = request.user, request.dc
    context = collect_view_data(request, 'dc_image_list')
    context['image_vm'] = ImageVm.get_uuid()
    context['is_staff'] = is_staff = user.is_staff
    context['all'] = _all = is_staff and request.GET.get('all', False)
    context['qs'] = qs = get_query_string(request, all=_all).urlencode()
    context['url_form_admin'] = reverse('admin_image_form', query_string=qs)
    context['form_admin'] = AdminImageForm(request, None, prefix='adm', initial={'owner': user.username,
                                                                                 'access': Image.PRIVATE,
                                                                                 'dc_bound': True})
    qs_image_filter = request.GET.copy()
    qs_image_filter.pop('created_since', None)
    qs_image_filter.pop('last', None)
    context['qs_image_filter'] = qs_image_filter.urlencode()
    context['default_limit'] = default_limit = 30
    context['image_uuids'] = set(Image.objects.all().values_list('uuid', flat=True))

    try:
        created_since_days = int(request.GET.get('created_since', 0))
    except (ValueError, TypeError):
        created_since_days = None

    if created_since_days:
        limit = None
    else:
        created_since_days = None

        try:
            limit = int(request.GET.get('last', default_limit))
        except (ValueError, TypeError):
            limit = default_limit

    repositories = ImageStore.get_repositories(include_image_vm=request.user.is_staff)
    context['imagestores'] = imagestores = ImageStore.all(repositories)
    context['created_since'] = created_since_days
    context['limit'] = limit

    if repositories:
        if repo and repo in repositories:
            context['imagestore'] = imagestore = ImageStore(repo, url=repositories[repo])
        else:  # Choose the first one
            context['imagestore'] = imagestore = imagestores[0]

        if created_since_days:
            created_since = make_aware(datetime.now() - timedelta(days=created_since_days))
        else:
            created_since = None

        context['images'] = imagestore.images_filter(created_since=created_since, limit=limit)
    else:
        context['imagestore'] = None
        context['images'] = []

    return render(request, 'gui/dc/imagestore_list.html', context)


@login_required
@admin_required  # SuperAdmin or DCAdmin+ImageAdmin
@permission_required(ImageAdminPermission)
@permission_required(ImageImportAdminPermission)
@ajax_required
@require_POST
def imagestore_update(request, repo):
    """
    Ajax page for refreshing imagestore repositories.
    """
    if repo not in ImageStore.get_repositories(include_image_vm=request.user.is_staff):
        raise Http404

    res = call_api_view(request, 'PUT', imagestore_manage, repo, log_response=True)

    if res.status_code == 200:
        imagestore = res.data['result']
        msg = _('Downloaded metadata for %(image_count)d images from image repository %(name)s')
        messages.success(request, msg % imagestore)

        return redirect('imagestore_list_repo', repo=repo, query_string=request.GET)
    else:
        if res.data.get('result', {}).get('error', None):
            status = 200  # The error will be displayed by ImageStoreList JS
        else:
            status = res.status_code

        return JSONResponse(res.data, status=status)
