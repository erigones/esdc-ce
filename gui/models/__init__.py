from django.db.models.signals import pre_delete, pre_save, post_save

from gui.models.user import User  # noqa: F401
from gui.models.userprofile import UserProfile  # noqa: F401
from gui.models.usersshkey import UserSSHKey  # noqa: F401
from gui.models.permission import Permission, AdminPermission, SuperAdminPermission  # noqa: F401
from gui.models.role import Role  # noqa: F401


post_save.connect(User.post_save, sender=User, dispatch_uid='post_save_user')
pre_save.connect(User.pre_save, sender=User, dispatch_uid='pre_save_user')
pre_delete.connect(User.pre_delete, sender=User, dispatch_uid='pre_delete_user')
