from functools import reduce
from datetime import datetime
from operator import and_

from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q, Count
from django.contrib.contenttypes.models import ContentType
from celery import states
from pytz import UTC

from vms.models import Dc, Vm, Node, NodeStorage, Subnet, Image, VmTemplate, Iso, TaskLogEntry
from pdns.models import Domain
from gui.models import User, Role
from que import TT_AUTO
from api import serializers as s
from api.task.log import get_task_types

TASK_LOG_MODELS = (Dc, Vm, Node, NodeStorage, Subnet, Image, VmTemplate, Iso, Domain, User, Role)

TASK_STATES = (
    ('', _('Status (all)')),
    (states.PENDING, _(states.PENDING)),
    (states.SUCCESS, _(states.SUCCESS)),
    (states.FAILURE, _(states.FAILURE)),
    (states.REVOKED, _(states.REVOKED)),
)

# noinspection PyProtectedMember,PyUnresolvedReferences
TASK_OBJECT_TYPES = [('', _('Object type (all)'))] + \
                    [(m._meta.model_name, m._meta.verbose_name) for m in TASK_LOG_MODELS]


class TaskLogEntrySerializer(s.ModelSerializer):
    """
    Serializes vms.models.TaskLogEntry
    """
    username = s.Field(source='get_username')
    object_name = s.Field(source='get_object_name')
    object_alias = s.Field(source='get_object_alias')
    object_type = s.Field(source='content_type.model')

    class Meta:
        model = TaskLogEntry
        fields = ('time', 'task', 'status', 'username', 'msg', 'detail',
                  'object_name', 'object_alias', 'object_type', 'flag')


class TaskCancelSerializer(s.Serializer):
    force = s.BooleanField(default=False)


class TaskLogFilterSerializer(s.Serializer):
    _content_type = None
    _object_pks = None
    status = s.ChoiceField(label=_('Status'), required=False, choices=TASK_STATES)
    object_type = s.ChoiceField(source='content_type', label=_('Object type'), required=False,
                                choices=TASK_OBJECT_TYPES)
    object_name = s.CharField(label=_('Object name'), max_length=2048, required=False)
    show_running = s.BooleanField(label=_('Show only running tasks'), required=False, default=False)
    hide_auto = s.BooleanField(label=_('Hide automatic tasks'), required=False, default=False)
    date_from = s.DateField(label=_('Since'), required=False)
    date_to = s.DateField(label=_('Until'), required=False)

    def validate(self, attrs):
        object_type = attrs.get('content_type', None)
        object_name = attrs.get('object_name', None)

        # object_name depends on object_type
        if object_name:
            if not object_type:
                self._errors['object_type'] = s.ErrorList([_('object_type attribute is required when '
                                                             'filtering by object_name.')])
                return attrs

            self._content_type = content_type = ContentType.objects.get(model=object_type)
            model_class = content_type.model_class()
            lookup_kwargs = model_class.get_log_name_lookup_kwargs(object_name)
            filter_kwargs = {key + '__icontains': val for key, val in lookup_kwargs.items()}
            self._object_pks = list(model_class.objects.filter(**filter_kwargs).values_list('pk', flat=True))

        return attrs

    def get_filters(self, pending_tasks=()):
        if self._object_pks is not None and not self._object_pks:  # Means that we want to return empty filter results
            return False

        tz = timezone.get_current_timezone()
        data = self.object
        query = []

        date_from = data.get('date_from')
        if date_from:
            date_from = datetime.combine(date_from, datetime.min.time())
            query.append(Q(time__gte=date_from.replace(tzinfo=UTC).astimezone(tz)))

        date_to = data.get('date_to')
        if date_to:
            date_to = datetime.combine(date_to, datetime.min.time())
            query.append(Q(time__lte=date_to.replace(tzinfo=UTC).astimezone(tz)))

        if self._object_pks:
            query.append(Q(object_pk__in=self._object_pks))

        status = data.get('status')
        if status:
            query.append(Q(status=status))

        if data.get('show_running'):
            query.append(Q(task__in=pending_tasks))

        object_type = data.get('object_type')
        if object_type:
            if self._content_type:
                content_type = self._content_type
            else:
                content_type = ContentType.objects.get(model=object_type)
            query.append(Q(content_type=content_type))

        if data.get('hide_auto'):
            query.append(~Q(task_type__in=get_task_types(tt=(TT_AUTO,))))

        if query:
            return reduce(and_, query)
        else:
            return None


class TaskLogReportSerializer(s.Serializer):
    """
    Display task log stats.
    """
    pending = s.IntegerField(read_only=True)
    revoked = s.IntegerField(read_only=True)
    succeeded = s.IntegerField(read_only=True)
    failed = s.IntegerField(read_only=True)

    @classmethod
    def get_report(cls, basequery):
        def get_count(status):
            return basequery.filter(status=status).aggregate(count=Count('id')).get('count', 0)

        return {
            'pending': get_count(states.PENDING),
            'revoked': get_count(states.REVOKED),
            'succeeded': get_count(states.SUCCESS),
            'failed': get_count(states.FAILURE),
        }
