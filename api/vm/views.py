from importlib import import_module

from django.conf import settings

# noinspection PyUnresolvedReferences
from api.vm.base.views import *
# noinspection PyUnresolvedReferences
from api.vm.status.views import *
# noinspection PyUnresolvedReferences
from api.vm.define.views import *
# noinspection PyUnresolvedReferences
from api.vm.snapshot.views import *
# noinspection PyUnresolvedReferences
from api.vm.backup.views import *
# noinspection PyUnresolvedReferences
from api.vm.migrate.views import *
# noinspection PyUnresolvedReferences
from api.vm.other.views import *
# noinspection PyUnresolvedReferences
from api.vm.qga.views import *

for third_party_app in settings.THIRD_PARTY_APPS:
    if third_party_app.startswith('api.vm.'):
        try:
            import_module(third_party_app + '.views', '*')
        except ImportError:
            pass
