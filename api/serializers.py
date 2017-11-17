"""
Copied+modified from rest_framework.serializers, which is licensed under the BSD license:
*******************************************************************************
Copyright (c) 2011-2016, Tom Christie
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************

Serializers and ModelSerializers are similar to Forms and ModelForms.
Unlike forms, they are not constrained to dealing with HTML output, and
form encoded input.

Serialization in REST framework is a two-phase process:

1. Serializers marshal between complex types like model instances, and
python primitives.
2. The process of marshalling between python primitives and request and
response content is handled by parsers and renderers.
"""
from __future__ import unicode_literals

import copy
import datetime
import inspect
import types
from collections import OrderedDict

from decimal import Decimal
from django.apps import apps
from django.core.paginator import Page
from django.db import models
from django.forms import widgets
from django.utils import six
from django.utils.functional import cached_property
from django.utils.encoding import force_text, python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError, ObjectDoesNotExist as DjangoObjectDoesNotExist
from django.contrib.contenttypes.fields import GenericForeignKey

# Note: We do the following so that users of the framework can use this style:
#
#     example_field = serializers.CharField(...)
#
# This helps keep the separation between model fields, form fields, and
# serializer fields more explicit.
from api.relations import *  # noqa: F403
from api.fields import *  # noqa: F403
from api.fields import is_simple_callable, get_component


def _resolve_model(obj):
    """
    Resolve supplied `obj` to a Django model class.

    `obj` must be a Django model class itself, or a string
    representation of one.  Useful in situations like GH #1225 where
    Django may not have resolved a string-based reference to a model in
    another model's foreign key definition.

    String representations should have the format:
        'appname.ModelName'
    """
    if isinstance(obj, six.string_types) and len(obj.split('.')) == 2:
        app_name, model_name = obj.split('.')
        return apps.get_model(app_name, model_name)
    elif inspect.isclass(obj) and issubclass(obj, models.Model):
        return obj
    else:
        raise ValueError("{0} is not a Django model".format(obj))


def pretty_name(name):
    """Converts 'first_name' to 'First name'"""
    if not name:
        return ''
    return name.replace('_', ' ').capitalize()


def field_value(source, value):
    for component in source.split('.'):
        value = get_component(value, component)
        if value is None:
            break
    return value


@python_2_unicode_compatible
class ErrorList(list):
    """
    See ErrorList in django.forms.util.
    """
    def __str__(self):
        return str([force_text(i) for i in self])

    def __repr__(self):
        return repr([force_text(i) for i in self])

    def __iter__(self):
        return (force_text(i) for i in list.__iter__(self))


class RelationsList(list):
    _deleted = []


class APIValidationError(ValidationError):
    """
    ValidationError with api_errors property.
    """
    @property
    def api_errors(self):
        if hasattr(self, 'message'):
            return ErrorList([self.message])
        return self.messages


class ObjectDoesNotExist(ValidationError):
    """
    ValidationError with predefined text.
    """
    def __init__(self, value, field_name='name', **kwargs):
        message = _('Object with %(field)s=%(value)s does not exist.') % {'field': field_name, 'value': value}
        super(ObjectDoesNotExist, self).__init__(message, **kwargs)


class NoPermissionToModify(ValidationError):
    """
    ValidationError with predefined text.
    """
    def __init__(self, **kwargs):
        message = _('You don\'t have permission to modify this attribute.')
        super(NoPermissionToModify, self).__init__(message, **kwargs)


class NestedValidationError(ValidationError):
    """
    The default ValidationError behavior is to stringify each item in the list
    if the messages are a list of error messages.

    In the case of nested serializers, where the parent has many children,
    then the child's `serializer.errors` will be a list of dicts.  In the case
    of a single child, the `serializer.errors` will be a dict.

    We need to override the default behavior to get properly nested error dicts.
    """

    def __init__(self, message):
        if isinstance(message, dict):
            self._messages = [message]
        else:
            self._messages = message

    @property
    def messages(self):
        return self._messages


class DictWithMetadata(dict):
    """
    A dict-like object, that can have additional properties attached.
    """
    def __getstate__(self):
        """
        Used by pickle (e.g., caching).
        Overridden to remove the metadata from the dict, since it shouldn't be
        pickled and may in some instances be unpickleable.
        """
        return dict(self)


class SortedDictWithMetadata(OrderedDict):
    """
    A sorted dict-like object, that can have additional properties attached.
    """
    def __reduce__(self):
        """
        Used by pickle (e.g., caching) if OrderedDict is used instead of SortedDict
        Overridden to remove the metadata from the dict, since it shouldn't be
        pickle and may in some instances be unpickleable.
        """
        return self.__class__, (OrderedDict(self), )

    def __getstate__(self):
        """
        Used by pickle (e.g., caching) in SortedDict
        Overridden to remove the metadata from the dict, since it shouldn't be
        pickle and may in some instances be unpickleable.
        """
        return OrderedDict(self).__dict__


def _is_protected_type(obj):
    """
    True if the object is a native data type that does not need to be serialized further.
    """
    return isinstance(obj, six.string_types + six.integer_types + (
        types.NoneType,
        datetime.datetime, datetime.date, datetime.time,
        float, Decimal,
    ))


def _get_declared_fields(bases, attrs):
    """
    Create a list of serializer field instances from the passed in 'attrs',
    plus any fields on the base classes (in 'bases').

    Note that all fields from the base classes are used.
    """
    fields = [(field_name, attrs.pop(field_name))
              for field_name, obj in list(six.iteritems(attrs))
              if isinstance(obj, Field)]  # noqa: F405
    fields.sort(key=lambda x: x[1].creation_counter)

    # If this class is subclassing another Serializer, add that Serializer's
    # fields.  Note that we loop over the bases in *reverse*. This is necessary
    # in order to maintain the correct order of fields.
    for base in bases[::-1]:
        if hasattr(base, 'base_fields'):
            fields = list(base.base_fields.items()) + fields

    return OrderedDict(fields)


class SerializerMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        attrs['base_fields'] = _get_declared_fields(bases, attrs)
        return super(SerializerMetaclass, mcs).__new__(mcs, name, bases, attrs)


class SerializerOptions(object):
    """
    Meta class options for Serializer
    """
    def __init__(self, meta):
        self.depth = getattr(meta, 'depth', 0)
        self.fields = getattr(meta, 'fields', ())
        self.exclude = getattr(meta, 'exclude', ())


class BaseSerializer(WritableField):  # noqa: F405
    """
    This is the Serializer implementation.
    We need to implement it as `BaseSerializer` due to metaclass magic.
    """
    class Meta(object):
        pass

    _options_class = SerializerOptions
    _dict_class = SortedDictWithMetadata

    def __init__(self, instance=None, data=None, files=None, context=None, partial=False, many=False,
                 allow_add_remove=False, **kwargs):
        super(BaseSerializer, self).__init__(**kwargs)
        self.opts = self._options_class(self.Meta)
        self.parent = None
        self.root = None
        self.partial = partial
        self.many = many
        self.allow_add_remove = allow_add_remove

        self.context = context or {}

        self.init_data = data
        self.init_files = files
        self.object = instance

        self._data = None
        self._files = None
        self._errors = None

        if many and instance is not None and not hasattr(instance, '__iter__'):
            raise ValueError('instance should be a queryset or other iterable with many=True')

        if allow_add_remove and not many:
            raise ValueError('allow_add_remove should only be used for bulk updates, but you have not set many=True')

    #####
    # Methods to determine which fields to use when (de)serializing objects.

    @cached_property
    def fields(self):
        return self.get_fields()

    # noinspection PyMethodMayBeStatic
    def get_default_fields(self):
        """
        Return the complete set of default fields for the object, as a dict.
        """
        return {}

    def get_fields(self):
        """
        Returns the complete set of fields for the object as a dict.

        This will be the set of any explicitly declared fields,
        plus the set of fields returned by get_default_fields().
        """
        ret = OrderedDict()

        # Get the explicitly declared fields
        # noinspection PyUnresolvedReferences
        base_fields = copy.deepcopy(self.base_fields)
        for key, field in base_fields.items():
            ret[key] = field

        # Add in the default fields
        default_fields = self.get_default_fields()
        for key, val in default_fields.items():
            if key not in ret:
                ret[key] = val

        # If 'fields' is specified, use those fields, in that order.
        if self.opts.fields:
            assert isinstance(self.opts.fields, (list, tuple)), '`fields` must be a list or tuple'
            new = OrderedDict()
            for key in self.opts.fields:
                new[key] = ret[key]
            ret = new

        # Remove anything in 'exclude'
        if self.opts.exclude:
            assert isinstance(self.opts.exclude, (list, tuple)), '`exclude` must be a list or tuple'
            for key in self.opts.exclude:
                ret.pop(key, None)

        for key, field in ret.items():
            field.initialize(parent=self, field_name=key)

        return ret

    #####
    # Methods to convert or revert from objects <--> primitive representations.

    # noinspection PyMethodMayBeStatic
    def get_field_key(self, field_name):
        """
        Return the key that should be used for a given field.
        """
        return field_name

    def restore_fields(self, data, files):
        """
        Core of deserialization, together with `restore_object`.
        Converts a dictionary of data into a dictionary of deserialized fields.
        """
        reverted_data = {}

        if data is not None and not isinstance(data, dict):
            self._errors['non_field_errors'] = ['Invalid data']
            return None

        for field_name, field in self.fields.items():
            field.initialize(parent=self, field_name=field_name)
            try:
                field.field_from_native(data, files, field_name, reverted_data)
            except ValidationError as err:
                self._errors[field_name] = list(err.messages)

        return reverted_data

    def perform_validation(self, attrs):
        """
        Run `validate_<field_name>()` and `validate()` methods on the serializer
        """
        for field_name, field in self.fields.items():
            if field_name in self._errors:
                continue

            source = field.source or field_name
            if self.partial and source not in attrs:
                continue
            try:
                validate_method = getattr(self, 'validate_%s' % field_name, None)
                if validate_method:
                    attrs = validate_method(attrs, source)
            except ValidationError as err:
                self._errors[field_name] = self._errors.get(field_name, []) + list(err.messages)

        # If there are already errors, we don't run .validate() because
        # field-validation failed and thus `attrs` may not be complete.
        # which in turn can cause inconsistent validation errors.
        if not self._errors:
            try:
                attrs = self.validate(attrs)
            except ValidationError as err:
                if hasattr(err, 'message_dict'):
                    for field_name, error_messages in err.message_dict.items():
                        self._errors[field_name] = self._errors.get(field_name, []) + list(error_messages)
                elif hasattr(err, 'messages'):
                    self._errors['non_field_errors'] = err.messages

        return attrs

    def validate(self, attrs):
        """
        Stub method, to be overridden in Serializer subclasses
        """
        return attrs

    # noinspection PyMethodMayBeStatic
    def restore_object(self, attrs, instance=None):
        """
        Deserialize a dictionary of attributes into an object instance.
        You should override this method to control how deserialized objects
        are instantiated.
        """
        if instance is not None:
            instance.update(attrs)
            return instance
        return attrs

    def to_native(self, obj):
        """
        Serialize objects -> primitives.
        """
        ret = self._dict_class()
        ret.fields = self._dict_class()

        for field_name, field in self.fields.items():
            if field.read_only and obj is None:
                continue
            field.initialize(parent=self, field_name=field_name)
            key = self.get_field_key(field_name)
            value = field.field_to_native(obj, field_name)
            method = getattr(self, 'transform_%s' % field_name, None)
            if callable(method):
                value = method(obj, value)
            if not getattr(field, 'write_only', False):
                ret[key] = value
            ret.fields[key] = self.augment_field(field, field_name, key, value)

        return ret

    def from_native(self, data, files=None):
        """
        Deserialize primitives -> objects.
        """
        self._errors = {}

        if data is not None or files is not None:
            attrs = self.restore_fields(data, files)

            if attrs is not None:
                attrs = self.perform_validation(attrs)

            if not self._errors:
                return self.restore_object(attrs, instance=getattr(self, 'object', None))
        else:
            self._errors['non_field_errors'] = ['No input provided']

    def augment_field(self, field, field_name, key, value):
        # This horrible stuff is to manage serializers rendering to HTML
        field._errors = self._errors.get(key) if self._errors else None
        field._name = field_name
        field._value = self.init_data.get(key) if self._errors and self.init_data else value
        if not field.label:
            field.label = pretty_name(key)
        return field

    def field_to_native(self, obj, field_name):
        """
        Override default so that the serializer can be used as a nested field
        across relationships.
        """
        if self.write_only:
            return None

        if self.source == '*':
            return self.to_native(obj)

        # Get the raw field value
        try:
            source = self.source or field_name
            value = obj

            for component in source.split('.'):
                if value is None:
                    break
                value = get_component(value, component)
        except DjangoObjectDoesNotExist:
            return None

        if is_simple_callable(getattr(value, 'all', None)):
            return [self.to_native(item) for item in value.all()]

        if value is None:
            return None

        if self.many:
            return [self.to_native(item) for item in value]
        return self.to_native(value)

    def field_from_native(self, data, files, field_name, into):
        """
        Override default so that the serializer can be used as a writable
        nested field across relationships.
        """
        if self.read_only:
            return

        try:
            value = data[field_name]
        except KeyError:
            if self.default is not None and not self.partial:
                # Note: partial updates shouldn't set defaults
                value = copy.deepcopy(self.default)
            else:
                if self.required:
                    raise ValidationError(self.error_messages['required'])
                return

        if self.source == '*':
            if value:
                reverted_data = self.restore_fields(value, {})
                if not self._errors:
                    into.update(reverted_data)
        else:
            if value in (None, ''):
                into[(self.source or field_name)] = None
            else:
                # Set the serializer object if it exists
                obj = get_component(self.parent.object, self.source or field_name) if self.parent.object else None

                # If we have a model manager or similar object then we need
                # to iterate through each instance.
                if (
                    self.many and
                    not hasattr(obj, '__iter__') and
                    is_simple_callable(getattr(obj, 'all', None))
                ):
                    obj = obj.all()

                kwargs = {
                    'instance': obj,
                    'data': value,
                    'context': self.context,
                    'partial': self.partial,
                    'many': self.many,
                    'allow_add_remove': self.allow_add_remove
                }
                serializer = self.__class__(**kwargs)

                if serializer.is_valid():
                    into[self.source or field_name] = serializer.object
                else:
                    # Propagate errors up to our parent
                    raise NestedValidationError(serializer.errors)

    # noinspection PyMethodMayBeStatic
    def get_identity(self, data):
        """
        This hook is required for bulk update.
        It is used to determine the canonical identity of a given object.

        Note that the data has not been validated at this point, so we need
        to make sure that we catch any cases of incorrect data types being
        passed to this method.
        """
        try:
            return data.get('id', None)
        except AttributeError:
            return None

    @property
    def errors(self):
        """
        Run deserialization and return error data,
        setting self.object if no errors occurred.
        """
        if self._errors is None:
            data, files = self.init_data, self.init_files

            if self.many is not None:
                many = self.many
            else:
                many = hasattr(data, '__iter__') and not isinstance(data, (Page, dict, six.text_type))
                if many:
                    raise AssertionError('Implicit list/queryset serialization is deprecated. '
                                         'Use the `many=True` flag when instantiating the serializer.')

            if many:
                ret = RelationsList()
                errors = []
                update = self.object is not None

                if update:
                    # If this is a bulk update we need to map all the objects
                    # to a canonical identity so we can determine which
                    # individual object is being updated for each item in the
                    # incoming data
                    objects = self.object
                    identities = [self.get_identity(self.to_native(obj)) for obj in objects]
                    identity_to_objects = dict(zip(identities, objects))

                if hasattr(data, '__iter__') and not isinstance(data, (dict, six.text_type)):
                    for item in data:
                        if update:
                            # Determine which object we're updating
                            identity = self.get_identity(item)
                            # noinspection PyUnboundLocalVariable
                            self.object = identity_to_objects.pop(identity, None)
                            if self.object is None and not self.allow_add_remove:
                                ret.append(None)
                                errors.append({'non_field_errors': [
                                    'Cannot create a new item, only existing items may be updated.'
                                ]})
                                continue

                        ret.append(self.from_native(item, None))
                        errors.append(self._errors)

                    if update and self.allow_add_remove:
                        ret._deleted = identity_to_objects.values()

                    self._errors = any(errors) and errors or []
                else:
                    self._errors = {'non_field_errors': ['Expected a list of items.']}
            else:
                ret = self.from_native(data, files)

            if not self._errors:
                self.object = ret

        return self._errors

    def is_valid(self):
        return not self.errors

    @property
    def data(self):
        """
        Returns the serialized data on the serializer.
        """
        if self._data is None:
            obj = self.object

            if self.many is not None:
                many = self.many
            else:
                many = hasattr(obj, '__iter__') and not isinstance(obj, (Page, dict))
                if many:
                    raise AssertionError('Implicit list/queryset serialization is deprecated. '
                                         'Use the `many=True` flag when instantiating the serializer.')

            if many:
                self._data = [self.to_native(item) for item in obj]
            else:
                self._data = self.to_native(obj)

        return self._data

    # noinspection PyMethodMayBeStatic
    def save_object(self, obj, **kwargs):
        obj.save(**kwargs)

    # noinspection PyMethodMayBeStatic
    def delete_object(self, obj):
        obj.delete()

    def save(self, **kwargs):
        """
        Save the deserialized object and return it.
        """
        # Clear cached _data, which may be invalidated by `save()`
        self._data = None

        if isinstance(self.object, list):
            for item in self.object:
                self.save_object(item, **kwargs)

            # noinspection PyProtectedMember,PyUnresolvedReferences
            if self.object._deleted:
                # noinspection PyProtectedMember,PyUnresolvedReferences
                for item in self.object._deleted:
                    self.delete_object(item)
        else:
            self.save_object(self.object, **kwargs)

        return self.object

    def metadata(self):
        """
        Return a dictionary of metadata about the fields on the serializer.
        Useful for things like responding to OPTIONS requests, or generating
        API schemas for auto-documentation.
        """
        return OrderedDict(
            [
                (field_name, field.metadata())
                for field_name, field in six.iteritems(self.fields)
            ]
        )

    def detail_dict(self, force_full=False, force_update=False):
        """Return detail dict suitable for logging in response"""
        assert self._data is not None

        # noinspection PyUnresolvedReferences
        if not force_update and (self.request.method == 'POST' or force_full):
            show_data = self.data
        else:
            show_data = self.init_data

        if not show_data:
            return {}

        return dict(show_data)


class Serializer(six.with_metaclass(SerializerMetaclass, BaseSerializer)):
    pass


class ModelSerializerOptions(SerializerOptions):
    """
    Meta class options for ModelSerializer
    """
    def __init__(self, meta):
        super(ModelSerializerOptions, self).__init__(meta)
        self.model = getattr(meta, 'model', None)
        self.read_only_fields = getattr(meta, 'read_only_fields', ())
        self.write_only_fields = getattr(meta, 'write_only_fields', ())


def _get_class_mapping(mapping, obj):
    """
    Takes a dictionary with classes as keys, and an object.
    Traverses the object's inheritance hierarchy in method
    resolution order, and returns the first matching value
    from the dictionary or None.

    """
    return next(
        (mapping[cls] for cls in inspect.getmro(obj.__class__) if cls in mapping),
        None
    )


class ModelSerializer(Serializer):
    """
    A serializer that deals with model instances and querysets.
    """
    _options_class = ModelSerializerOptions

    field_mapping = {
        models.AutoField: IntegerField,  # noqa: F405
        models.FloatField: FloatField,  # noqa: F405
        models.IntegerField: IntegerField,  # noqa: F405
        models.PositiveIntegerField: IntegerField,  # noqa: F405
        models.SmallIntegerField: IntegerField,  # noqa: F405
        models.PositiveSmallIntegerField: IntegerField,  # noqa: F405
        models.DateTimeField: DateTimeField,  # noqa: F405
        models.DateField: DateField,  # noqa: F405
        models.TimeField: TimeField,  # noqa: F405
        models.DecimalField: DecimalField,  # noqa: F405
        models.EmailField: EmailField,  # noqa: F405
        models.CharField: CharField,  # noqa: F405
        models.URLField: URLField,  # noqa: F405
        models.SlugField: SlugField,  # noqa: F405
        models.TextField: CharField,  # noqa: F405
        models.CommaSeparatedIntegerField: CharField,  # noqa: F405
        models.BooleanField: BooleanField,  # noqa: F405
        models.NullBooleanField: BooleanField,  # noqa: F405
        models.FileField: FileField,  # noqa: F405
        models.ImageField: ImageField,  # noqa: F405
    }

    # noinspection PyProtectedMember,PyUnresolvedReferences
    def get_default_fields(self):  # noqa: R701
        """
        Return all the fields that should be serialized for the model.
        """
        cls = self.opts.model
        assert cls is not None, (
            "Serializer class '%s' is missing 'model' Meta option" %
            self.__class__.__name__
        )
        opts = cls._meta.concrete_model._meta
        ret = OrderedDict()
        nested = bool(self.opts.depth)

        # Deal with adding the primary key field
        pk_field = opts.pk
        while pk_field.rel and pk_field.rel.parent_link:
            # If model is a child via multi-table inheritance, use parent's pk
            pk_field = pk_field.rel.to._meta.pk

        serializer_pk_field = self.get_pk_field(pk_field)
        if serializer_pk_field:
            ret[pk_field.name] = serializer_pk_field

        # Deal with forward relationships
        forward_rels = [field for field in opts.fields if field.serialize]
        forward_rels += [field for field in opts.many_to_many if field.serialize]

        for model_field in forward_rels:
            has_through_model = False

            if model_field.rel:
                to_many = isinstance(model_field, models.fields.related.ManyToManyField)
                related_model = _resolve_model(model_field.rel.to)

                if to_many and not model_field.rel.through._meta.auto_created:
                    has_through_model = True

            if model_field.rel and nested:
                field = self.get_nested_field(model_field, related_model, to_many)
            elif model_field.rel:
                field = self.get_related_field(model_field, related_model, to_many)
            else:
                field = self.get_field(model_field)

            if field:
                if has_through_model:
                    field.read_only = True

                ret[model_field.name] = field

        # Deal with reverse relationships
        if not self.opts.fields:
            reverse_rels = []
        else:
            # Reverse relationships are only included if they are explicitly
            # present in the `fields` option on the serializer
            reverse_rels = opts.get_all_related_objects()
            reverse_rels += opts.get_all_related_many_to_many_objects()

        for relation in reverse_rels:
            accessor_name = relation.get_accessor_name()
            if not self.opts.fields or accessor_name not in self.opts.fields:
                continue
            related_model = relation.model
            to_many = relation.field.rel.multiple
            has_through_model = False
            is_m2m = isinstance(relation.field,
                                models.fields.related.ManyToManyField)

            if (is_m2m and hasattr(relation.field.rel, 'through') and
                    not relation.field.rel.through._meta.auto_created):
                has_through_model = True

            if nested:
                field = self.get_nested_field(None, related_model, to_many)
            else:
                field = self.get_related_field(None, related_model, to_many)

            if field:
                if has_through_model:
                    field.read_only = True

                ret[accessor_name] = field

        # Ensure that 'read_only_fields' is an iterable
        assert isinstance(self.opts.read_only_fields, (list, tuple)), '`read_only_fields` must be a list or tuple'

        # Add the `read_only` flag to any fields that have been specified
        # in the `read_only_fields` option
        for field_name in self.opts.read_only_fields:
            assert field_name not in self.base_fields.keys(), (
                "field '%s' on serializer '%s' specified in "
                "`read_only_fields`, but also added "
                "as an explicit field.  Remove it from `read_only_fields`." %
                (field_name, self.__class__.__name__))
            assert field_name in ret, (
                "Non-existent field '%s' specified in `read_only_fields` "
                "on serializer '%s'." %
                (field_name, self.__class__.__name__))
            ret[field_name].read_only = True

        # Ensure that 'write_only_fields' is an iterable
        assert isinstance(self.opts.write_only_fields, (list, tuple)), '`write_only_fields` must be a list or tuple'

        for field_name in self.opts.write_only_fields:
            assert field_name not in self.base_fields.keys(), (
                "field '%s' on serializer '%s' specified in "
                "`write_only_fields`, but also added "
                "as an explicit field.  Remove it from `write_only_fields`." %
                (field_name, self.__class__.__name__))
            assert field_name in ret, (
                "Non-existent field '%s' specified in `write_only_fields` "
                "on serializer '%s'." %
                (field_name, self.__class__.__name__))
            ret[field_name].write_only = True

        return ret

    def get_pk_field(self, model_field):
        """
        Returns a default instance of the pk field.
        """
        return self.get_field(model_field)

    # noinspection PyUnusedLocal
    def get_nested_field(self, model_field, related_model, to_many):
        """
        Creates a default instance of a nested relational field.

        Note that model_field will be `None` for reverse relationships.
        """
        class NestedModelSerializer(ModelSerializer):
            class Meta:
                model = related_model
                depth = self.opts.depth - 1

        return NestedModelSerializer(many=to_many)

    def get_related_field(self, model_field, related_model, to_many):
        """
        Creates a default instance of a flat relational field.

        Note that model_field will be `None` for reverse relationships.
        """
        # TODO: filter queryset using:
        # .using(db).complex_filter(self.rel.limit_choices_to)

        # noinspection PyProtectedMember
        kwargs = {
            'queryset': related_model._default_manager,
            'many': to_many
        }

        if model_field:
            kwargs['required'] = not(model_field.null or model_field.blank) and model_field.editable
            if model_field.help_text is not None:
                kwargs['help_text'] = model_field.help_text
            if model_field.verbose_name is not None:
                kwargs['label'] = model_field.verbose_name

            if not model_field.editable:
                kwargs['read_only'] = True

            if model_field.verbose_name is not None:
                kwargs['label'] = model_field.verbose_name

            if model_field.help_text is not None:
                kwargs['help_text'] = model_field.help_text

        return PrimaryKeyRelatedField(**kwargs)  # noqa: F405

    def get_field(self, model_field):
        """
        Creates a default instance of a basic non-relational field.
        """
        kwargs = {}

        if model_field.null or model_field.blank and model_field.editable:
            kwargs['required'] = False

        if isinstance(model_field, models.AutoField) or not model_field.editable:
            kwargs['read_only'] = True

        if model_field.has_default():
            kwargs['default'] = model_field.get_default()

        if issubclass(model_field.__class__, models.TextField):
            kwargs['widget'] = widgets.Textarea

        if model_field.verbose_name is not None:
            kwargs['label'] = model_field.verbose_name

        if model_field.help_text is not None:
            kwargs['help_text'] = model_field.help_text

        # TODO: TypedChoiceField?
        if model_field.flatchoices:  # This ModelField contains choices
            kwargs['choices'] = model_field.flatchoices
            if model_field.null:
                kwargs['empty'] = None
            return ChoiceField(**kwargs)  # noqa: F405

        # put this below the ChoiceField because min_value isn't a valid initializer
        if issubclass(model_field.__class__, models.PositiveIntegerField) or\
                issubclass(model_field.__class__, models.PositiveSmallIntegerField):
            kwargs['min_value'] = 0

        if model_field.null and \
                issubclass(model_field.__class__, (models.CharField, models.TextField)):
            kwargs['allow_none'] = True

        attribute_dict = {
            models.CharField: ['max_length'],
            models.CommaSeparatedIntegerField: ['max_length'],
            models.DecimalField: ['max_digits', 'decimal_places'],
            models.EmailField: ['max_length'],
            models.FileField: ['max_length'],
            models.ImageField: ['max_length'],
            models.SlugField: ['max_length'],
            models.URLField: ['max_length'],
        }

        attributes = _get_class_mapping(attribute_dict, model_field)
        if attributes:
            for attribute in attributes:
                kwargs.update({attribute: getattr(model_field, attribute)})

        serializer_field_class = _get_class_mapping(
            self.field_mapping, model_field)

        if serializer_field_class:
            return serializer_field_class(**kwargs)
        return ModelField(model_field=model_field, **kwargs)  # noqa: F405

    def get_validation_exclusions(self, instance=None):
        """
        Return a list of field names to exclude from model validation.
        """
        # noinspection PyUnresolvedReferences
        cls = self.opts.model
        # noinspection PyProtectedMember
        opts = cls._meta.concrete_model._meta
        exclusions = [field.name for field in opts.fields + opts.many_to_many]

        for field_name, field in self.fields.items():
            field_name = field.source or field_name
            if (
                field_name in exclusions and not
                field.read_only and
                (field.required or hasattr(instance, field_name)) and not
                isinstance(field, Serializer)
            ):
                exclusions.remove(field_name)
        return exclusions

    def full_clean(self, instance):
        """
        Perform Django's full_clean, and populate the `errors` dictionary
        if any validation errors occur.

        Note that we don't perform this inside the `.restore_object()` method,
        so that subclasses can override `.restore_object()`, and still get
        the full_clean validation checking.
        """
        try:
            instance.full_clean(exclude=self.get_validation_exclusions(instance))
        except ValidationError as err:
            self._errors = err.message_dict
            return None
        return instance

    # noinspection PyUnresolvedReferences
    def restore_object(self, attrs, instance=None):
        """
        Restore the model instance.
        """
        m2m_data = {}
        related_data = {}
        nested_forward_relations = {}
        # noinspection PyProtectedMember
        meta = self.opts.model._meta

        # Reverse fk or one-to-one relations
        for (obj, model) in meta.get_all_related_objects_with_model():
            field_name = obj.get_accessor_name()
            if field_name in attrs:
                related_data[field_name] = attrs.pop(field_name)

        # Reverse m2m relations
        for (obj, model) in meta.get_all_related_m2m_objects_with_model():
            field_name = obj.get_accessor_name()
            if field_name in attrs:
                m2m_data[field_name] = attrs.pop(field_name)

        # Forward m2m relations
        if issubclass(meta.many_to_many.__class__, tuple):
            temp_m2m = list(meta.many_to_many)
        else:
            temp_m2m = meta.many_to_many
        for field in temp_m2m + meta.virtual_fields:
            if isinstance(field, GenericForeignKey):
                continue
            if field.name in attrs:
                m2m_data[field.name] = attrs.pop(field.name)

        # Nested forward relations - These need to be marked so we can save
        # them before saving the parent model instance.
        for field_name in attrs.keys():
            if isinstance(self.fields.get(field_name, None), Serializer):
                nested_forward_relations[field_name] = attrs[field_name]

        # Create an empty instance of the model
        if instance is None:
            instance = self.opts.model()

        for key, val in attrs.items():
            try:
                setattr(instance, key, val)
            except ValueError:
                self._errors[key] = [self.error_messages['required']]

        # Any relations that cannot be set until we've
        # saved the model get hidden away on these
        # private attributes, so we can deal with them
        # at the point of save.
        instance._related_data = related_data
        instance._m2m_data = m2m_data
        instance._nested_forward_relations = nested_forward_relations

        return instance

    def from_native(self, data, files=None):
        """
        Override the default method to also include model field validation.
        """
        instance = super(ModelSerializer, self).from_native(data, files=files)
        if not self._errors:
            return self.full_clean(instance)

    # noinspection PyProtectedMember
    def save_object(self, obj, **kwargs):
        """
        Save the deserialized object.
        """
        if getattr(obj, '_nested_forward_relations', None):
            # Nested relationships need to be saved before we can save the
            # parent instance.
            for field_name, sub_object in obj._nested_forward_relations.items():
                if sub_object:
                    self.save_object(sub_object)
                setattr(obj, field_name, sub_object)

        obj.save(**kwargs)

        if getattr(obj, '_m2m_data', None):
            for accessor_name, object_list in obj._m2m_data.items():
                setattr(obj, accessor_name, object_list)
            del obj._m2m_data

        if getattr(obj, '_related_data', None):
            related_fields = dict([
                (field.get_accessor_name(), field)
                for field, model
                in obj._meta.get_all_related_objects_with_model()
            ])
            for accessor_name, related in obj._related_data.items():
                if isinstance(related, RelationsList):
                    # Nested reverse fk relationship
                    for related_item in related:
                        fk_field = related_fields[accessor_name].field.name
                        setattr(related_item, fk_field, obj)
                        self.save_object(related_item)

                    # Delete any removed objects
                    if related._deleted:
                        [self.delete_object(item) for item in related._deleted]

                elif isinstance(related, models.Model):
                    # Nested reverse one-one relationship
                    fk_field = obj._meta.get_field_by_name(accessor_name)[0].field.name
                    setattr(related, fk_field, obj)
                    self.save_object(related)
                else:
                    # Reverse FK or reverse one-one
                    setattr(obj, accessor_name, related)
            del obj._related_data


class HyperlinkedModelSerializerOptions(ModelSerializerOptions):
    """
    Options for HyperlinkedModelSerializer
    """
    url_field_name = 'url'

    def __init__(self, meta):
        super(HyperlinkedModelSerializerOptions, self).__init__(meta)
        self.view_name = getattr(meta, 'view_name', None)
        self.lookup_field = getattr(meta, 'lookup_field', None)
        self.url_field_name = getattr(meta, 'url_field_name', self.url_field_name)


class HyperlinkedModelSerializer(ModelSerializer):
    """
    A subclass of ModelSerializer that uses hyperlinked relationships,
    instead of primary key relationships.
    """
    _options_class = HyperlinkedModelSerializerOptions
    _default_view_name = '%(model_name)s-detail'
    _hyperlink_field_class = HyperlinkedRelatedField  # noqa: F405
    _hyperlink_identify_field_class = HyperlinkedIdentityField  # noqa: F405

    def get_default_fields(self):
        fields = super(HyperlinkedModelSerializer, self).get_default_fields()

        if self.opts.view_name is None:
            # noinspection PyUnresolvedReferences
            self.opts.view_name = self._get_default_view_name(self.opts.model)

        # noinspection PyUnresolvedReferences
        if self.opts.url_field_name not in fields:
            # noinspection PyUnresolvedReferences
            url_field = self._hyperlink_identify_field_class(
                view_name=self.opts.view_name,
                lookup_field=self.opts.lookup_field
            )
            ret = self._dict_class()
            # noinspection PyUnresolvedReferences
            ret[self.opts.url_field_name] = url_field
            ret.update(fields)
            fields = ret

        return fields

    def get_pk_field(self, model_field):
        if self.opts.fields and model_field.name in self.opts.fields:
            return self.get_field(model_field)

    def get_related_field(self, model_field, related_model, to_many):
        """
        Creates a default instance of a flat relational field.
        """
        # TODO: filter queryset using:
        # .using(db).complex_filter(self.rel.limit_choices_to)
        # noinspection PyProtectedMember
        kwargs = {
            'queryset': related_model._default_manager,
            'view_name': self._get_default_view_name(related_model),
            'many': to_many
        }

        if model_field:
            kwargs['required'] = not(model_field.null or model_field.blank) and model_field.editable
            if model_field.help_text is not None:
                kwargs['help_text'] = model_field.help_text
            if model_field.verbose_name is not None:
                kwargs['label'] = model_field.verbose_name

        # noinspection PyUnresolvedReferences
        if self.opts.lookup_field:
            # noinspection PyUnresolvedReferences
            kwargs['lookup_field'] = self.opts.lookup_field

        return self._hyperlink_field_class(**kwargs)

    def get_identity(self, data):
        """
        This hook is required for bulk update.
        We need to override the default, to use the url as the identity.
        """
        try:
            # noinspection PyUnresolvedReferences
            return data.get(self.opts.url_field_name, None)
        except AttributeError:
            return None

    def _get_default_view_name(self, model):
        """
        Return the view name to use if 'view_name' is not specified in 'Meta'
        """
        # noinspection PyProtectedMember
        model_meta = model._meta
        format_kwargs = {
            'app_label': model_meta.app_label,
            'model_name': model_meta.object_name.lower()
        }
        return self._default_view_name % format_kwargs


class ForceSerializer(Serializer):
    """
    Often used serializer with one boolean attribute, which should be used to confirm harmful api operations, e.g.
    deleting all VM snapshots or VM factory reset.

    Use it like this::

        data = {'force': True}  # Incoming request data
        force = ForceSerializer(data=data, default=False)
        print force.is_true()
        True

    Or like this::

        data = {'force': 0}  # Incoming request data
        if ForceSerializer(data=data, default=False):
            print 'Using force'
        else:
            print 'No force'
        No force

    """
    force = BooleanField(default=False)  # noqa: F405

    def __init__(self, *args, **kwargs):
        self.default_force = bool(kwargs.pop('default', False))
        super(ForceSerializer, self).__init__(*args, **kwargs)
        self.fields['force'].default = self.default_force

    def is_true(self):
        if not self.is_valid():
            return self.default_force
        return self.data['force']

    def __nonzero__(self):
        return self.is_true()
    __bool__ = __nonzero__


class InstanceSerializer(Serializer):
    """
    Serializer used to update only some attributes of model instances.
    """
    _model_ = NotImplemented
    _update_fields_ = ()
    _default_fields_ = ()
    _default_function_ = None  # Should return a dict {field_name: default_value}. Takes serializer instance as argument
    _blank_fields_ = frozenset(['desc', 'note'])
    _null_fields_ = frozenset()
    _delayed_data = None

    def __init__(self, request, instance, *args, **kwargs):
        self.request = request
        super(InstanceSerializer, self).__init__(instance, *args, **kwargs)

        if not kwargs.get('many', False):
            if isinstance(instance, self._model_) and (not instance.pk or getattr(instance, 'new', False)):
                # Set defaults from existing instance or function
                for field_name in self._default_fields_:
                    source = self.fields[field_name].source or field_name
                    self.fields[field_name].default = field_value(source, instance)
                # Set default from custom function
                if self._default_function_:
                    # noinspection PyCallingNonCallable
                    for field_name, value in six.iteritems(self._default_function_()):
                        self.fields[field_name].default = value

    @staticmethod
    def _blank(value):
        """Return empty string instead of None"""
        if not value:
            return ''
        return value

    @staticmethod
    def _null(value):
        """Return None instead of empty string"""
        if not value and value is not 0:
            return None
        return value

    def _normalize(self, attr, value):
        """Normalize value - use before updating model instance"""
        if attr in self._blank_fields_:
            return self._blank(value)
        if attr in self._null_fields_:
            return self._null(value)
        return value

    # noinspection PyMethodMayBeStatic
    def _setattr(self, instance, source, value):
        """Set value to instance source"""
        if '.' in source:
            attr_names = source.split('.')
            source = attr_names[-1]

            for name in attr_names[:-1]:
                instance = getattr(instance, name)

        setattr(instance, source, value)

    # noinspection PyMethodOverriding
    def restore_object(self, attrs, instance):
        """Instance always present"""
        self._delayed_data = {}

        for attr in self._update_fields_:
            field = self.fields[attr]
            source = field.source or attr

            if source in attrs:
                setattr_data = (instance, source, self._normalize(attr, attrs[source]))

                if isinstance(field, RelatedField) and field.many:  # noqa: F405
                    # field is represents a M2N relation a we have to delay setting the attribute after save
                    # this is mainly because M2N attributes can be set only after the object exists in DB
                    self._delayed_data[attr] = setattr_data
                else:
                    self._setattr(*setattr_data)

        return instance

    def detail_dict(self, force_full=False, force_update=False):
        """Return detail dict suitable for logging in response"""
        assert self._data is not None

        if not force_update and (self.request.method == 'POST' or force_full):
            show_data = self.data
        else:
            show_data = self.init_data

        if not show_data:
            return {}

        update_fields = set(self._update_fields_)

        return {k: v for k, v in six.iteritems(show_data) if k in update_fields}

    def reload(self):
        """Reload instance from DB and refresh serializer"""
        obj = self.object.__class__.objects.get(pk=self.object.pk)
        self.__init__(self.request, obj, data=self.init_data or {})

        return obj

    def save(self, **kwargs):
        self.object.save(**kwargs)

        if self._delayed_data:
            for attr, setattr_data in self._delayed_data.items():
                self._setattr(*setattr_data)

        # noinspection PyAttributeOutsideInit
        self._data = None
        # noinspection PyAttributeOutsideInit
        self._delayed_data = None

        return self.object

    @property
    def _model_verbose_name(self):
        # noinspection PyProtectedMember 2x
        return self._model_._meta.verbose_name


class ConditionalDCBoundSerializer(InstanceSerializer):
    """This serializer handles the common logic when a model is being bound to a datacenter."""
    _dc_bound = None
    dc_bound = BooleanField(source='dc_bound_bool', default=True)  # noqa: F405

    def _validate_dc_bound(self, value):
        if value:
            if hasattr(self.object, 'get_related_dcs'):
                dcs = self.object.get_related_dcs()
            elif hasattr(self.object, 'dc'):
                dcs = self.object.dc.all()
            else:
                raise AssertionError(
                    '%s has to implement either get_dcs method or have a dc relation.' % self._model_verbose_name)
            dcs_len = len(dcs)

            if dcs_len == 1:
                return dcs[0]
            else:
                err = {'model': self._model_verbose_name}

                if dcs_len > 1:
                    raise ValidationError(_('%(model)s is attached into more than one datacenter.') % err)
                elif dcs_len == 0:
                    raise ValidationError(_('%(model)s is not attached into any datacenters.') % err)
        else:
            return None

    def validate_dc_bound(self, attrs, source):
        try:
            value = bool(attrs[source])
        except KeyError:
            pass
        else:
            if value != self.object.dc_bound_bool:
                if not self.request.user.is_staff:
                    raise NoPermissionToModify
                self._dc_bound = self._validate_dc_bound(value)

        return attrs

    def validate(self, attrs):
        if (self.request.method == 'POST'
                and attrs.get('dc_bound_bool', self.object.dc_bound_bool)
                and not self.init_data.get('dc', None)):
            err = {'model': self._model_verbose_name.lower()}
            self._errors['dc_bound'] = self._errors['dc'] = ErrorList([
                _('You have to specify to which datacenter shall the %(model)s be bound. '
                  'Either use the "dc" parameter or set the "dc_bound" parameter to false.') % err
            ])

        return super(ConditionalDCBoundSerializer, self).validate(attrs)
