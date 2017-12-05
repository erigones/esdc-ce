from importlib import import_module

from django.conf import settings

# noinspection PyUnresolvedReferences
from api.vm.base.views import *  # noqa: F401,F403,F403
# noinspection PyUnresolvedReferences
from api.vm.status.views import *  # noqa: F401,F403,F403
# noinspection PyUnresolvedReferences
from api.vm.define.views import *  # noqa: F401,F403,F403
# noinspection PyUnresolvedReferences
from api.vm.snapshot.views import *  # noqa: F401,F403,F403
# noinspection PyUnresolvedReferences
from api.vm.backup.views import *  # noqa: F401,F403,F403
# noinspection PyUnresolvedReferences
from api.vm.migrate.views import *  # noqa: F401,F403,F403
# noinspection PyUnresolvedReferences
from api.vm.other.views import *  # noqa: F401,F403,F403
# noinspection PyUnresolvedReferences
from api.vm.qga.views import *  # noqa: F401,F403,F403

for third_party_app in settings.THIRD_PARTY_APPS:
    if third_party_app.startswith('api.vm.'):
        # noinspection PyBroadException
        try:
            # noinspection PyShadowingBuiltins
            module = import_module(third_party_app + '.views')
            globals().update({name: module.__dict__[name] for name in module.__all__})
        except Exception:
            pass
