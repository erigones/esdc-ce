from api.api_views import APIView
from api.exceptions import OperationNotSupported
from api.accounts.user.profile.serializers import UserProfileSerializer
from api.accounts.user.utils import get_user, get_user_profiles
from api.accounts.messages import LOG_PROFILE_UPDATE
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.mon.alerting.tasks import mon_user_changed


class UserProfileView(APIView):
    serializer = UserProfileSerializer
    dc_bound = False
    order_by_default = ('user__username',)
    order_by_field_map = {'created': 'user_id', 'username': 'user__username'}

    def __init__(self, request, username, data, many=False):
        super(UserProfileView, self).__init__(request)
        self.username = username
        self.data = data
        self.many = many

        if username:
            self.user = get_user(request, username, sr=('userprofile',), exists_ok=True, noexists_fail=True)
            self.profile = self.user.userprofile
        else:
            self._full = True
            self.profile = get_user_profiles(request, data=data, sr=('user',), pr=(), order_by=self.order_by)

    def get(self):
        return self._get(self.profile, self.data, self.many, field_name='user__username')

    # noinspection PyMethodMayBeStatic
    def post(self):
        # Profile is created automatically with user record so no need for this function
        raise OperationNotSupported

    def put(self):
        profile = self.profile
        ser = self.serializer(self.request, profile, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=profile, dc_bound=False)

        ser.save()
        response = SuccessTaskResponse(self.request, ser.data, obj=self.user, detail_dict=ser.detail_dict(),
                                       owner=ser.object.user, msg=LOG_PROFILE_UPDATE, dc_bound=False)
        mon_user_changed.call(self.request, user_name=ser.object.user.username)
        return response

    # noinspection PyMethodMayBeStatic
    def delete(self):
        # We do not allow profile removal, because it is an essential part of the user record (wont work without it)
        raise OperationNotSupported
