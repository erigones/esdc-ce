from django.shortcuts import render, resolve_url
from django.contrib.auth.decorators import login_required

from gui.decorators import profile_required
from gui.utils import collect_view_data
from gui.signals import view_faq
from api.decorators import setting_required


@login_required
@profile_required
def api(request):
    """
    API Documentation view (via iframe).
    """
    context = collect_view_data(request, 'api_docs')

    return render(request, 'gui/docs/api.html', context)


@login_required
@profile_required
def user_guide(request):
    """
    User Guide view (via iframe).
    """
    context = collect_view_data(request, 'user_guide')

    return render(request, 'gui/docs/user_guide.html', context)


@login_required
@profile_required
@setting_required('FAQ_ENABLED', check_settings=False)  # FAQ must be enabled only in DC
def faq(request):
    """
    Frequently Asked Questions view.
    """
    dc_settings = request.dc.settings
    context = collect_view_data(request, 'faq')
    context['support_email'] = dc_settings.SUPPORT_EMAIL

    if dc_settings.SUPPORT_ENABLED:
        context['support_section_url'] = resolve_url('add_ticket')
    else:
        context['support_section_url'] = '#'

    view_faq.send(sender='faq', request=request, context=context)
    return render(request, 'gui/docs/faq.html', context)
