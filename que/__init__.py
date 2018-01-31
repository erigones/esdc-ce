from logging import addLevelName
from multiprocessing import Event

# Our custom log severity. We need this because we want to see some special messages and on node the default log level
# of workers is set to WARNING (INFO would be too much noise). These messages are not errors nor warnings, but can help
# in some situations (e.g. tracing tasks).
IMPORTANT = 45
addLevelName(IMPORTANT, 'IMPORTANT')

# Que events
E_SHUTDOWN = Event()

# Task queues
Q_FAST = 'fast'
Q_SLOW = 'slow'
Q_MGMT = 'mgmt'
Q_BACKUP = 'backup'
Q_IMAGE = 'image'

# Task types
TT_DUMMY = 'd'
TT_EXEC = 'e'
TT_AUTO = 'a'
TT_MGMT = 'm'
TT_INTERNAL = 'i'
TT_ERROR = 'f'
TT = (TT_DUMMY, TT_EXEC, TT_AUTO, TT_MGMT, TT_INTERNAL, TT_ERROR)

# Task groups
TG_DC_BOUND = 'd'
TG_DC_UNBOUND = 'u'
TG = (TG_DC_BOUND, TG_DC_UNBOUND)
