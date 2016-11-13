from django.db.models.signals import pre_delete, pre_save, post_save

from gui.models.user import User
from gui.models.userprofile import UserProfile
from gui.models.usersshkey import UserSSHKey
from gui.models.permission import Permission, AdminPermission, SuperAdminPermission
from gui.models.role import Role


post_save.connect(User.post_save, sender=User, dispatch_uid='post_save_user')
pre_save.connect(User.pre_save, sender=User, dispatch_uid='pre_save_user')
pre_delete.connect(User.pre_delete, sender=User, dispatch_uid='pre_delete_user')
