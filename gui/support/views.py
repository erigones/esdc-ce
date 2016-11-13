from django.shortcuts import render, redirect
from django.utils.translation import ugettext_lazy as _
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from gui.support.forms import AddTicketForm
from gui.decorators import ajax_required, profile_required
from gui.utils import collect_view_data
from api.decorators import setting_required
from api.email import sendmail


@login_required
@profile_required
@setting_required('SUPPORT_ENABLED')
def add_ticket(request):
    """
    Page with form for sending tickets.
    """
    context = collect_view_data(request, 'add_ticket')
    context['ticketform'] = AddTicketForm(request)

    return render(request, 'gui/support/add_ticket.html', context)


@login_required
@profile_required
@ajax_required
@require_POST
@setting_required('SUPPORT_ENABLED')
def add_ticket_submit(request):
    """
    Ajax submit ticket form.
    """
    ticketform = AddTicketForm(request, request.POST)
    dc_settings = request.dc.settings

    if ticketform.is_valid():
        # Send mail to SUPPORT_EMAIL
        sendmail(None, 'gui/support/add_ticket_subject.txt', 'gui/support/add_ticket_email.txt',
                 recipient_list=[dc_settings.SUPPORT_EMAIL], from_email=request.user.email, dc=request.dc,
                 extra_context={
                     'first_name': request.user.first_name,
                     'last_name': request.user.last_name,
                     'company': request.user.userprofile.company,
                     'email': request.user.email,
                     'phone': request.user.userprofile.phone,
                     'severity': ticketform.cleaned_data['severity'],
                     'ticket_type': ticketform.cleaned_data['ticket_type'],
                     'vm': ticketform.cleaned_data['vm'],
                     'summary': ticketform.cleaned_data['summary'],
                     'desc': ticketform.cleaned_data['desc'],
                     'repro': ticketform.cleaned_data['repro'],
                     'dc': request.dc,
                 })

        # Send mail to user
        if dc_settings.SUPPORT_USER_CONFIRMATION:
            sendmail(request.user, 'gui/support/add_ticket_user_subject.txt', 'gui/support/add_ticket_user_email.txt',
                     from_email=dc_settings.SUPPORT_EMAIL, dc=request.dc,
                     extra_context={
                         'summary': ticketform.cleaned_data['summary'],
                         'severity': ticketform.cleaned_data['severity'],
                         'ticket_type': ticketform.cleaned_data['ticket_type'],
                         'vm': ticketform.cleaned_data['vm'],
                     })

        # Notify and redirect
        messages.success(request, _('Your ticket has been submitted.'))
        if ticketform.cleaned_data.get('vm', None):
            return redirect('vm_details', hostname=ticketform.cleaned_data['vm'])
        else:
            return redirect('vm_list')

    else:
        return render(request, 'gui/support/add_ticket_form.html', {
            'ticketform': ticketform,
        })
