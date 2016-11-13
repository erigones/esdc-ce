"""
The APIView and TaskAPIView classes where get(), post(), put() and delete() methods should be defined.
"""
from django.utils.six import text_type

from que.tasks import execute
from vms.models import DefaultDc
from api.exceptions import InvalidInput
from api.task.response import TaskResponse, FailureTaskResponse, SuccessTaskResponse


class APIView(object):
    """
    API view helper.
    """
    _full = None
    _extended = None
    serializer = None
    data = None
    dc_bound = True
    order_by_default = ('pk',)  # Default tuple of DB fields used for sorting
    order_by_fields = ()  # Tuple of available DB fields
    order_by_field_map = None  # Should be a dictionary mapping of field name to DB field
    _order_by_available_fields = None  # Cached set of all available field names, created from order_by_* cls attributes

    def __init__(self, request, force_default_dc=False, **kwargs):
        """Always call this __init__ in descendant classes"""

        # The force_default_dc parameter is useful when directly working with APIView from GUI
        # Some api views are not bound to DCs and should always use the default DC
        # noinspection PyUnresolvedReferences
        if force_default_dc and not request.dc.is_default():
            request.dc = DefaultDc()

        # Required: HttpRequest object saving should always be done by this parent class
        self.request = request

        # Optional: Store keyword arguments as instance attributes
        self.__dict__.update(kwargs)

    @classmethod
    def _get_available_order_by_fields(cls):
        """Return cached set of all available field names, created from order_by_* class attributes"""
        if cls._order_by_available_fields is None:
            cls._order_by_available_fields = set(cls.order_by_fields)

            if cls.order_by_field_map:
                # noinspection PyUnresolvedReferences
                cls._order_by_available_fields.update(cls.order_by_field_map.keys())

        return cls._order_by_available_fields

    @classmethod
    def _get_db_field(cls, field):
        """Helper method for validating one field name used for sorting"""
        if field.startswith('-') or field.startswith('+'):
            desc = '-'
            field = field[1:]
        else:
            desc = ''

        if field in cls._get_available_order_by_fields():
            if cls.order_by_field_map:
                # noinspection PyUnresolvedReferences
                return desc + cls.order_by_field_map.get(field, field)
            else:
                return desc + field
        else:
            raise ValueError

    @classmethod
    def validate_order_by(cls, order_by):
        """Check if order_by list does contain valid values"""
        try:
            return [cls._get_db_field(f.strip()) for f in order_by]
        except (ValueError, TypeError):
            # noinspection PyTypeChecker
            raise InvalidInput('Invalid order_by; Possible sort fields are: %s' %
                               ', '.join(cls._get_available_order_by_fields()))

    @classmethod
    def get_order_by(cls, data, order_var='order_by'):
        """Return list of fields suitable for QuerySet.order_by() or raise InvalidInput exception"""
        if data:
            order = data.get(order_var, None)

            if order:
                return cls.validate_order_by(text_type(order).split(','))

        return cls.order_by_default

    @property
    def order_by(self):
        return self.get_order_by(self.data)

    def response(self, *args, **kwargs):
        fun = getattr(self, self.request.method.lower())
        return fun(*args, **kwargs)

    # noinspection PyUnusedLocal
    def _get(self, db_result, data=None, many=False, serializer=None, field_name='name'):
        if not serializer:
            serializer = self.serializer

        if many:
            if self.full or self.extended:
                if db_result:
                    res = serializer(self.request, db_result, many=True).data
                else:
                    res = []
            else:
                res = list(db_result.values_list(field_name, flat=True))
        else:
            res = serializer(self.request, db_result).data

        return SuccessTaskResponse(self.request, res, dc_bound=self.dc_bound)

    def is_full(self, data):
        return self.request.method == 'GET' and data and data.get('full', False)

    def is_extended(self, data):
        return self.request.method == 'GET' and data and data.get('extended', False)

    @property
    def full(self):
        if self._full is None:
            # noinspection PyTypeChecker
            self._full = self.is_full(self.data)
        return self._full

    @property
    def extended(self):
        if self._extended is None:
            # noinspection PyTypeChecker
            self._extended = self.is_extended(self.data)
        return self._extended


class TaskAPIView(APIView):
    """
    API view base class used for creating view helpers which call que execute() to create tasks.
    """
    msg = ''
    obj = None
    task_id = None
    error = None
    _apiview_ = None
    _detail_ = None

    def _apiview(self):
        return {'view': self.request.resolver_match.view_name, 'method': self.request.method}

    # noinspection PyMethodMayBeStatic
    def _detail(self):
        return ''

    def _meta(self):
        # noinspection PyProtectedMember
        m = {'msg': self.msg, 'apiview': self.apiview, self.obj._pk_key: self.obj.pk}
        d = self.detail
        if d:
            m['detail'] = d
        return m

    @property
    def apiview(self):
        if self._apiview_ is None:
            self._apiview_ = self._apiview()
        return self._apiview_

    @property
    def detail(self):
        if self._detail_ is None:
            self._detail_ = self._detail()
        return self._detail_

    def execute(self, *args, **kwargs):
        self.task_id, self.error = execute(self.request, self.obj.owner.id, *args, **kwargs)
        if self.error:
            return None
        return self.task_id

    @property
    def error_response(self):
        return FailureTaskResponse(self.request, self.error, obj=self.obj, dc_bound=self.dc_bound)

    @property
    def task_response(self):
        return TaskResponse(self.request, self.task_id, msg=self.msg, obj=self.obj, api_view=self.apiview,
                            detail=self.detail, data=self.data)
