from importlib import import_module

from django.conf import settings

# noinspection PyUnresolvedReferences
from api.system.tasks import *
# noinspection PyUnresolvedReferences
from api.task.tasks import *
# noinspection PyUnresolvedReferences
from api.vm.tasks import *
# noinspection PyUnresolvedReferences
from api.node.tasks import *
# noinspection PyUnresolvedReferences
from api.image.tasks import *
# noinspection PyUnresolvedReferences
from api.mon.tasks import *

for third_party_app in settings.THIRD_PARTY_APPS:
    # noinspection PyBroadException
    try:
        module = import_module(third_party_app + '.tasks')
        globals().update({name: module.__dict__[name] for name in module.__all__})
    except:
        pass
