from celery.utils.log import get_task_logger
from django.utils.six import iteritems, string_types, integer_types, binary_type

from que.internal import InternalTask as _InternalTask
from vms.models import Dc, DefaultDc

logger = get_task_logger(__name__)

PRIMITIVES = (float, bool, type(None), binary_type) + string_types + integer_types


# noinspection PyAbstractClass
class InternalTask(_InternalTask):
    """
    Internal task, which translates parameters into primitives.
    """
    abstract = True
    setting_required = None

    def call(self, sender, **kwargs):
        # DC instance is used to fetch settings
        dc = None

        # Convert sender object to primitive
        if not isinstance(sender, PRIMITIVES):
            sender = str(sender)

        # Create primitive kwargs and get DC object if possible
        for key, val in iteritems(kwargs):
            if hasattr(val, 'pk'):
                if key == 'dc':
                    dc = val
                elif key == 'vm':
                    dc = val.dc

                obj_key = getattr(val, '_pk_key', None)

                if not obj_key:
                    # noinspection PyProtectedMember
                    obj_key = '%s_%s' % (val._meta.model_name, val._meta.pk.name)

                kwargs[obj_key] = val.pk
                del kwargs[key]

            elif key == 'dc_id':
                dc = Dc.objects.get_by_id(val)

            elif not isinstance(val, PRIMITIVES):
                logger.warning('Non-primitive is passed as a task argument to internal task: %s is of type %s',
                               val, type(val))

        # Do nothing if required setting is False
        if self.setting_required:
            if not dc:
                dc = DefaultDc()

            # noinspection PyTypeChecker
            if not getattr(dc.settings, self.setting_required, True):
                logger.debug('Ignoring internal task %s(%s, %s), because required setting "%s" is False in DC "%s"',
                             self.name, sender, kwargs, self.setting_required, dc)
                return None

        logger.info('Running internal task %s(%s, %s)', self.name, sender, kwargs)

        return super(InternalTask, self).call(sender, **kwargs)
