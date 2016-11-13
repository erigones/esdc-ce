from gui.models.user import User
from django.shortcuts import Http404


def get_edited_user(request, username, sr=('dc_bound',)):
    """SuperAdmin get edit any user. Other (UserAdmins) can edit only dc_bound users"""
    get_attrs = {'username': username}

    if not request.user.is_staff:
        get_attrs['dc_bound'] = request.dc

    try:
        return User.objects.select_related(*sr).get(**get_attrs)
    except User.DoesNotExist:
        raise Http404
