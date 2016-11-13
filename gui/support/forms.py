from django import forms
from django.utils.translation import ugettext_lazy as _

from gui.vm.utils import get_vms

REQUIRED = {'required': 'required'}


class AddTicketForm(forms.Form):
    """
    Form for adding support ticket.
    """
    SEVERITY = (
        ('', _('Severity')),
        ('CRITICAL', _('Critical')),
        ('MAJOR', _('Major')),
        ('MINOR', _('Minor')),
        ('COSMETIC', _('Cosmetic')),
    )
    TICKET_TYPE = (
        ('', _('Ticket type')),
        ('USABILITY', _('Usability issue')),
        ('BUG', _('Bug Report')),
        ('FEATURE', _('Feature request')),
        ('OPERATIONAL', _('Operational problem')),
        ('SALES', _('Sales and payments'))
    )

    vm = forms.ChoiceField(
        label=_('Select Server'),
        choices=[],
        required=False)
    severity = forms.ChoiceField(
        label=_('Problem severity'),
        choices=SEVERITY,
        required=True,  # Django validation
        widget=forms.Select(attrs=REQUIRED))  # HTML5 validation
    ticket_type = forms.ChoiceField(
        label=_('Ticket type'),
        choices=TICKET_TYPE,
        required=True,
        widget=forms.Select(attrs=REQUIRED))  # HTML5 validation
    summary = forms.CharField(
        label=_('Summary'),
        required=True,
        widget=forms.TextInput(attrs={
            'required': 'required',  # HTML5 validation
            'placeholder': _('Summary'),
        }))
    desc = forms.CharField(
        label=_('Problem description'),
        required=True,
        widget=forms.widgets.Textarea(attrs={
            'required': 'required',  # HTML5 validation
            'placeholder': _('Problem description')
        }))
    repro = forms.CharField(
        label=_('Steps to Reproduce'),
        required=False,
        widget=forms.widgets.Textarea(attrs={
            'placeholder': _('Steps to Reproduce'),
        }))

    def __init__(self, request, *args, **kwargs):
        super(AddTicketForm, self).__init__(*args, **kwargs)
        self.fields['vm'].choices = [('', _('Select Server'))] + \
            list(get_vms(request, prefetch_tags=False).values_list('hostname', 'alias'))
