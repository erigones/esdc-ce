from api.status import HTTP_201_CREATED
from api.api_views import APIView
from api.exceptions import OperationNotSupported
from api.vm.utils import get_object
from api.accounts.user.sshkey.serializers import UserSSHKeySerializer
from api.accounts.user.utils import get_user
from api.accounts.messages import LOG_SSHKEY_CREATE, LOG_SSHKEY_DELETE
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from gui.models import UserSSHKey


class UserSshkeyView(APIView):
    serializer = UserSSHKeySerializer
    dc_bound = False
    order_by_default = order_by_fields = ('title',)

    def __init__(self, request, username, title, data, many=False):
        super(UserSshkeyView, self).__init__(request)
        self.username = username
        self.data = data
        self.many = many
        user = get_user(request, username, exists_ok=True, noexists_fail=True)

        if title:
            self.sshkey = get_object(request, UserSSHKey, {'title': title, 'user': user})
        else:
            self.sshkey = UserSSHKey.objects.filter(user=user).order_by(*self.order_by)

    def get(self):
        return self._get(self.sshkey, self.data, self.many, field_name='title')

    def post(self):
        sshkey = self.sshkey
        ser = self.serializer(self.request, sshkey, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=sshkey, dc_bound=False)

        ser.object.save()
        owner = ser.object.user

        return SuccessTaskResponse(self.request, ser.data, status=HTTP_201_CREATED, obj=owner, owner=owner,
                                   detail_dict=ser.detail_dict(), msg=LOG_SSHKEY_CREATE, dc_bound=False)

    # noinspection PyMethodMayBeStatic
    def put(self):
        # Doesnt makes sense to correct ssh key, delete and add new one if not correct
        raise OperationNotSupported

    def delete(self):
        sshkey = self.sshkey

        ser = self.serializer(self.request, sshkey)
        dd = {'title': sshkey.title}
        owner = sshkey.user

        ser.object.delete()

        return SuccessTaskResponse(self.request, None, obj=owner, owner=owner, detail_dict=dd, msg=LOG_SSHKEY_DELETE,
                                   dc_bound=False)
