# noinspection PyMethodMayBeStatic,PyProtectedMember,PyUnusedLocal
class AppRouter(object):
    """
    https://docs.djangoproject.com/en/dev/topics/db/multi-db/#database-routers
    """
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'pdns':
            return 'pdns'
        return 'default'  # esdc

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'pdns':
            return 'pdns'
        return 'default'  # esdc

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'pdns':
            return db == 'pdns'
        else:
            return db == 'default'
