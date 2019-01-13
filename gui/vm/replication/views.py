from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.dispatch import receiver
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from gui.decorators import ajax_required
from gui.vm.utils import get_vm
from gui.vm.replication.forms import ServerReplicaForm
from gui.signals import view_vm_details
from gui.utils import context_list_append


@login_required
@ajax_required
@require_POST
def replication_form(request, hostname):
    """
    Ajax page for managing server replication.
    """
    if not request.user.is_admin(request):  # can_edit permission
        raise PermissionDenied

    vm = get_vm(request, hostname)

    if vm.slave_vms:
        slave_vm = vm.slave_vm.select_related('master_vm', 'vm', 'vm__node').exclude(name='').first()
    else:
        slave_vm = None

    form = ServerReplicaForm(request, vm, slave_vm, request.POST, prefix='rep')

    if form.is_valid():
        status = form.save(args=(vm.hostname, form.cleaned_data['repname']))
        if status == 205:
            # The replica configuration has changed in DB, but does not affect the VM on compute node
            return redirect('vm_details', hostname=vm.hostname)
        elif 200 <= status < 400:
            return HttpResponse(None, status=204)  # Just hide the modal (socket.io callbacks will do the job)

    return render(request, 'replication/vm_details_replica_form.html', {'form': form, 'vm': vm})


# noinspection PyUnusedLocal
@receiver(view_vm_details)
def vm_details(sender, request, context, **kwargs):
    dc_settings = request.dc.settings
    context['replication_enabled'] = dc_settings.VMS_VM_REPLICATION_ENABLED

    if dc_settings.VMS_VM_REPLICATION_ENABLED and context.get('can_edit'):
        context['replicaform'] = ServerReplicaForm(request, context['vm'], context['slave_vm'], prefix='rep',
                                                   vm_nodes=context['settingsform'].vm_nodes,
                                                   initial={'repname': 'replica1', 'sleep_time': 60,
                                                            'enabled': True, 'reserve_resources':
                                                                dc_settings.VMS_VM_REPLICA_RESERVATION_DEFAULT})

        context_list_append(context, 'include_modals', 'replication/vm_details_modal.html')
        context_list_append(context, 'include_details', 'replication/vm_details_status_row.html')
        context_list_append(context, 'include_buttons', 'replication/vm_details_button.html')
