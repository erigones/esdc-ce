from logging import getLogger

from django import forms
from django.forms.forms import NON_FIELD_ERRORS
from django.utils.translation import ugettext
from django.utils.six import iteritems, text_type
from frozendict import frozendict

from gui.widgets import NumberInput, ByteSizeInput, ArrayWidget, DictWidget
from gui.fields import ArrayField, IntegerArrayField, DictField
from api import fields
from api.relations import RelatedField
from api.utils.views import call_api_view

logger = getLogger(__name__)


class SerializerForm(forms.Form):
    """
    Sync api serializer form errors to django form errors.
    """
    task_id = None
    action = None
    _serializer = None
    _api_method = frozendict({'create': 'POST', 'update': 'PUT', 'delete': 'DELETE', 'get': 'GET'})
    _api_call = NotImplemented  # Set in descendant class
    _api_response = None
    _exclude_fields = frozenset()
    _custom_fields = frozendict()
    _custom_field_opts = frozendict()
    _custom_widgets = frozendict()
    _custom_widget_attrs = frozendict()
    _ignore_empty_fields = frozenset()
    _field_text_class = 'narrow input-transparent'
    _field_checkbox_class = 'normal-check'
    _field_select_class = 'narrow input-select2'
    _field_readonly_class = 'uneditable-input'

    def __init__(self, request, obj, *args, **kwargs):
        self._request = request
        self._obj = obj
        self._read_only_fields = set()
        init = kwargs.pop('init', False)

        # Initial data are useful only for updates, or enabled manually by param
        if (obj and request.POST.get('action', None) == 'update') or init:
            kwargs['initial'] = self._initial_data(request, obj)

        # Parent constructor
        super(SerializerForm, self).__init__(*args, **kwargs)

        # Copy serializer fields
        if self._serializer:
            for name, field in iteritems(self._serializer.base_fields):
                field_not_defined = name not in self.fields
                field_not_excluded = name not in self._exclude_fields
                if field_not_defined and field_not_excluded:
                    self.fields[name] = self._serializer_field(name, field)

        # Set fancy placeholder
        for key, field in self.fields.items():
            field.widget.attrs['placeholder'] = self._get_placeholder(field, key)

    def _get_placeholder(self, field, field_name, default=''):
        # Python circular imports
        from gui.utils import tags_to_string

        try:
            value = self.initial[field_name]
        except KeyError:
            value = field.widget.attrs.get('placeholder', default)
        else:
            if isinstance(value, (list, tuple)):
                value = tags_to_string(value)
            if value is None:
                return ''

        return text_type(value).replace('\r\n', ' ').replace('\n', ' ')

    # noinspection PyMethodMayBeStatic
    def _build_field(self, name, serializer_field, form_field_class, **form_field_options):
        """Process converted field information and returns form field.
        Suitable for overriding in descendant classes.
        """
        return form_field_class(**form_field_options)

    def _serializer_field(self, name, field):
        """
        Convert serializer field to django form field.
        """
        opts = {
            'label': field.label,
            'help_text': field.help_text,
            'required': field.required,
        }

        if isinstance(field, (fields.ChoiceField, fields.IntegerChoiceField, RelatedField)):
            field_class = forms.ChoiceField
            widget_class = forms.Select
            widget_attrs = {'class': self._field_select_class}
            opts['required'] = False
            try:
                opts['choices'] = field.choices
            except AttributeError:
                pass

            try:
                if isinstance(field, fields.IntegerChoiceField) or isinstance(opts['choices'][0][0], int):
                    field_class = forms.TypedChoiceField
                    opts['coerce'] = int
                    opts['empty_value'] = None
            except (KeyError, IndexError, TypeError):
                pass

        elif isinstance(field, fields.BooleanField):
            field_class = forms.BooleanField
            widget_class = forms.CheckboxInput
            widget_attrs = {'class': self._field_checkbox_class}
            opts['required'] = False

        else:
            widget_class = forms.TextInput
            widget_attrs = {'class': self._field_text_class}
            field_class = forms.CharField

            if isinstance(field, fields.IntegerField):
                field_class = forms.IntegerField
                widget_class = NumberInput

                if field.help_text and '(MB)' in field.help_text:
                    widget_class = ByteSizeInput
                    widget_attrs['class'] += ' ' + 'input-mbytes'

            elif isinstance(field, fields.BaseArrayField):
                if isinstance(field, fields.IntegerArrayField):
                    field_class = IntegerArrayField
                else:
                    field_class = ArrayField
                widget_class = ArrayWidget
            elif isinstance(field, fields.BaseDictField):
                field_class = DictField
                widget_class = DictWidget

            if field.read_only:
                widget_attrs['class'] += ' ' + self._field_readonly_class

        if opts['required']:
            widget_attrs['required'] = 'required'

        if field.read_only:
            widget_attrs['disabled'] = 'disabled'
            self._read_only_fields.add(name)

        field_class = self._custom_fields.get(name, field_class)
        widget_class = self._custom_widgets.get(name, widget_class)
        widget_attrs.update(self._custom_widget_attrs.get(name, {}))
        opts.update(self._custom_field_opts.get(name, {}))
        opts['widget'] = widget_class(attrs=widget_attrs)

        return self._build_field(name, field, field_class, **opts)

    @staticmethod
    def _blank(value):
        """Return empty string instead of None"""
        if not value:
            return ''
        return value

    @staticmethod
    def _null(value):
        """Return None instead of empty string"""
        if not value:
            return None
        return value

    def _initial_data(self, request, obj):
        """Data initialized from DB model object"""
        if self._serializer:
            if hasattr(self._serializer, '_model_'):  # InstanceSerializer(request, instance)
                # noinspection PyCallingNonCallable
                return self._serializer(self._request, obj).data
            else:  # class Serializer(instance)
                # noinspection PyCallingNonCallable
                return self._serializer(obj).data
        return {}

    def _input_data(self):
        """Data collected from form"""
        return self.cleaned_data

    def _final_data(self, data=None):
        """Data that are send to API for validation (in create _input_data, in update _has_changed data)"""
        if data is None:
            data = self._input_data()
        return data

    def _has_changed(self):
        """Parse _input_data from form and compare with _initial_data from DB and return data that has changed"""
        ret = {}

        for key, val in self._input_data().items():
            if key in self._read_only_fields:
                continue

            if key in self._ignore_empty_fields and not val:
                logger.debug('SerializerForm._has_changed [%s]: %s (%s) is empty and will be ignored',
                             key, val, type(val))
                continue

            try:
                initial_val = self.initial[key]
            except KeyError:
                ret[key] = val
                logger.debug('SerializerForm._has_changed [%s]: %s (%s) is missing in initial data',
                             key, val, type(val))
            else:
                if initial_val != val:
                    ret[key] = val
                    logger.debug('SerializerForm._has_changed [%s]: %s (%s) != %s (%s)',
                                 key, initial_val, type(initial_val), val, type(val))

        return ret

    def _set_api_task_id(self, data):
        """Set task_id from TaskResponse"""
        # noinspection PyBroadException
        try:
            self.task_id = data['task_id']
        except:
            pass

    def _set_custom_api_errors(self, errors):
        pass

    def _add_error(self, field_name, error):
        if field_name not in self._errors:
            self._errors[field_name] = self.error_class()

        if isinstance(error, (list, tuple)):
            self._errors[field_name].extend(error)
        else:
            self._errors[field_name].append(error)

    def _set_api_errors(self, data):
        # errors is a dict error output from API
        if not data or not isinstance(data, dict):
            return None

        errors = data.get('result', data)

        if isinstance(errors, dict):  # Classic serializer error task output
            # Pair API errors to Django form errors
            for field in self.fields:
                if field in errors:
                    self._add_error(field, errors.pop(field))  # should be lazy
                    try:
                        del self.cleaned_data[field]
                    except KeyError:
                        pass

            if 'non_field_errors' in errors:
                self._add_error(NON_FIELD_ERRORS, errors['non_field_errors'])  # should be lazy
            elif 'detail' in errors:
                self._add_error(NON_FIELD_ERRORS, ugettext(errors['detail']))  # should be noop
            elif 'message' in errors:
                self._add_error(NON_FIELD_ERRORS, ugettext(errors['message']))  # should be noop

        else:  # More serious api error
            if isinstance(errors, list):  # Maybe we have errors from multiple serializers
                for err in errors:
                    self._set_api_errors(err)
            elif errors:
                self._add_error(NON_FIELD_ERRORS, errors)

        self._set_custom_api_errors(errors)

    # noinspection PyUnusedLocal
    @classmethod
    def api_call(cls, action, obj, request, args=(), data=()):
        method = cls._api_method[action]
        logger.info('Calling API view %s %s(%s, data=%s) by user %s in DC %s',
                    method, cls._api_call.__name__, args, data, request.user, request.dc)
        return call_api_view(request, method, cls._api_call.__func__, *args, data=dict(data), log_response=True)

    def save(self, action=None, args=()):
        # For security reasons you can limit action from view
        if not action:
            action = self.data.get('action')

        # Save action
        self.action = action

        # For security reasons data must have only cleaned_data for this form
        if action == 'update':
            data = self._final_data(self._has_changed())
            if not data:  # Nothing changed
                return 204
        else:
            data = self._final_data()

        # Saving socket.io session ID. Used when sending messages about hostname change, so we don't send useless
        # message to this user
        self._request.siosid = self.data.get('siosid', None)

        # Call API function (also updates tasklog)
        res = self.api_call(action, self._obj, self._request, args=args, data=data)
        self._api_response = res.data

        if res.status_code in (200, 201):
            self._set_api_task_id(res.data)
        else:
            self._set_api_errors(res.data)

        return res.status_code

    def set_error(self, key, value):
        """Set custom error"""
        if self._errors is None:
            self._errors = {}

        self._add_error(key, value)
