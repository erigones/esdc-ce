from multiprocessing import Event

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
