from django.db.models import Q

from api.api_views import APIView
from api.fields import get_boolean_value
from api.utils.db import get_object
from api.dc.user.serializers import UserSerializer
from api.accounts.user.utils import ExcludeInternalUsers
from gui.models import User


class DcUserView(APIView):
    serializer = UserSerializer
    order_by_default = order_by_fields = ('username',)

    def __init__(self, request, username, data):
        super(DcUserView, self).__init__(request)
        self.data = data
        self.username = username
        dc = request.dc
        restrict_users = ExcludeInternalUsers

        if dc.access != dc.PUBLIC:
            restrict_users = restrict_users & (Q(id=dc.owner.id) | Q(roles__in=dc.roles.all()))

        if username:
            self.user = get_object(request, User, {'username': username}, where=restrict_users,
                                   sr=('dc_bound', 'default_dc'), exists_ok=True, noexists_fail=True)
        else:
            self.user = User.objects.distinct().filter(restrict_users)\
                                               .filter(is_active=self.active).order_by(*self.order_by)

            if self.full or self.extended:
                self.user = self.user.select_related('dc_bound', 'default_dc').prefetch_related('roles')

    def get(self, many=False):
        return self._get(self.user, many=many, field_name='username')

    def is_active(self, data):
        return self.request.method == 'GET' and get_boolean_value(data.get('active', True))

    @property
    def active(self):
        if self.data:
            return self.is_active(self.data)
        else:
            return True
