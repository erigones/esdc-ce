from datetime import date, timedelta
from django import forms
from django.utils.translation import ugettext_lazy as _
from frozendict import frozendict

from api.task.serializers import TASK_STATES, TASK_OBJECT_TYPES, TaskLogFilterSerializer


class BaseTaskLogFilterForm(forms.Form):
    DEFAULT_DATE_FROM = frozendict({'days': 15})

    _ser = None
    status = forms.ChoiceField(label=_('Status'), required=False, choices=TASK_STATES,
                               widget=forms.Select(attrs={'class': 'fill-up input-navigation select-transparent'}))
    show_running = forms.BooleanField(label=_('Show only running tasks'), required=False,
                                      widget=forms.CheckboxInput(attrs={'class': 'checkbox fill-up input-navigation'}))
    hide_auto = forms.BooleanField(label=_('Hide automatic tasks'), required=False,
                                   widget=forms.CheckboxInput(attrs={'class': 'checkbox fill-up input-navigation'}))
    date_from = forms.DateField(label=_('Since'), required=True, input_formats=('%Y-%m-%d',),
                                widget=forms.DateInput(format='%Y-%m-%d',
                                                       attrs={'placeholder': _('Since'),
                                                              'class': 'fill-up input-navigation input-transparent '
                                                                       'input-date'}))
    date_to = forms.DateField(label=_('Until'), required=False, input_formats=('%Y-%m-%d',),
                              widget=forms.DateInput(format='%Y-%m-%d',
                                                     attrs={'placeholder': _('Until'),
                                                            'class': 'fill-up input-navigation input-transparent '
                                                                     'input-date'}))

    def __init__(self, data, **kwargs):
        if 'date_from' not in data:
            data['date_from'] = (date.today() - timedelta(**self.DEFAULT_DATE_FROM)).strftime('%Y-%m-%d')

        super(BaseTaskLogFilterForm, self).__init__(data, **kwargs)

    def clean(self):
        cleaned_data = super(BaseTaskLogFilterForm, self).clean()

        if not self.errors:
            self._ser = ser = TaskLogFilterSerializer(data=cleaned_data)
            if not ser.is_valid():
                self._errors = ser.errors

        return cleaned_data

    def get_filters(self, pending_tasks=()):
        return self._ser.get_filters(pending_tasks=pending_tasks)


class TaskLogObjectFilterForm(forms.Form):
    object_type = forms.ChoiceField(label=_('Object type'), required=False, choices=TASK_OBJECT_TYPES,
                                    widget=forms.Select(attrs={'class': 'fill-up input-navigation select-transparent'}))
    object_name = forms.CharField(label=_('Object name'), required=False, max_length=2048,
                                  widget=forms.TextInput(attrs={
                                      'placeholder': _('Object name'),
                                      'class': 'fill-up input-navigation input-transparent'}))


class TaskLogFilterForm(TaskLogObjectFilterForm, BaseTaskLogFilterForm):
    pass
