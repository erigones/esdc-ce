from importlib import import_module

from django.conf import settings

# noinspection PyUnresolvedReferences
from api.system.tasks import *  # noqa: F401,F403
# noinspection PyUnresolvedReferences
from api.task.tasks import *  # noqa: F401,F403
# noinspection PyUnresolvedReferences
from api.vm.tasks import *  # noqa: F401,F403
# noinspection PyUnresolvedReferences
from api.node.tasks import *  # noqa: F401,F403
# noinspection PyUnresolvedReferences
from api.image.tasks import *  # noqa: F401,F403
# noinspection PyUnresolvedReferences
from api.mon.tasks import *  # noqa: F401,F403

for third_party_app in settings.THIRD_PARTY_APPS:
    # noinspection PyBroadException
    try:
        # noinspection PyShadowingBuiltins
        module = import_module(third_party_app + '.tasks')
        globals().update({name: module.__dict__[name] for name in module.__all__})
    except Exception:
        pass
